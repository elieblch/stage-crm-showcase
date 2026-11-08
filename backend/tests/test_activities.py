"""Tests de la timeline d'activité : contraintes de schéma + endpoints + sync.

- Contrainte CHECK « exactement un parent » (offre XOR contact).
- CASCADE à la suppression d'une offre / d'un contact ; SET NULL du document.
- Synchronisation last_action_date = max(event_date) des activités « action ».
- Quick actions (mark-relanced) qui journalisent un événement + relance correcte.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.models.models import Activity, Contact, Document, Offer

pytestmark = pytest.mark.asyncio


# ─── Contrainte CHECK : exactement un FK ──────────────────
async def test_check_rejects_two_parents(db_session):
    offer = Offer(title="A", company="X")
    contact = Contact(name="C")
    db_session.add_all([offer, contact])
    await db_session.flush()

    db_session.add(
        Activity(
            offer_id=offer.id,
            contact_id=contact.id,
            activity_type="note",
            event_date=date.today(),
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


async def test_check_rejects_no_parent(db_session):
    db_session.add(Activity(activity_type="note", event_date=date.today()))
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


async def test_check_accepts_single_parent(db_session):
    offer = Offer(title="A", company="X")
    db_session.add(offer)
    await db_session.flush()
    db_session.add(
        Activity(offer_id=offer.id, activity_type="applied", event_date=date.today())
    )
    await db_session.flush()  # ne doit pas lever


# ─── CASCADE / SET NULL ───────────────────────────────────
async def _count_activities(db_session) -> int:
    return (await db_session.execute(select(func.count()).select_from(Activity))).scalar_one()


async def test_cascade_delete_offer_removes_activities(db_session):
    offer = Offer(title="A", company="X")
    db_session.add(offer)
    await db_session.flush()
    db_session.add_all(
        [
            Activity(offer_id=offer.id, activity_type="applied", event_date=date.today()),
            Activity(offer_id=offer.id, activity_type="note", event_date=date.today()),
        ]
    )
    await db_session.commit()
    assert await _count_activities(db_session) == 2

    await db_session.delete(offer)
    await db_session.flush()
    assert await _count_activities(db_session) == 0


async def test_cascade_delete_contact_removes_activities(db_session):
    contact = Contact(name="C")
    db_session.add(contact)
    await db_session.flush()
    db_session.add(
        Activity(contact_id=contact.id, activity_type="contacted", event_date=date.today())
    )
    await db_session.commit()
    assert await _count_activities(db_session) == 1

    await db_session.delete(contact)
    await db_session.flush()
    assert await _count_activities(db_session) == 0


async def test_delete_document_sets_activity_document_null(db_session):
    doc = Document(
        doc_type="cv",
        label="CV",
        original_filename="cv.pdf",
        file_path="/tmp/cv.pdf",
        file_size=1,
    )
    contact = Contact(name="C")
    db_session.add_all([doc, contact])
    await db_session.flush()
    act = Activity(
        contact_id=contact.id,
        activity_type="applied",
        event_date=date.today(),
        document_id=doc.id,
    )
    db_session.add(act)
    await db_session.commit()

    await db_session.delete(doc)
    await db_session.flush()
    await db_session.refresh(act)
    assert act.document_id is None
    # L'activité survit à la suppression du document.
    assert await _count_activities(db_session) == 1


# ─── Endpoints REST ───────────────────────────────────────
async def test_create_list_and_delete_offer_activity(client):
    oid = (await client.post("/offers", json={"title": "A", "company": "X"})).json()["id"]

    r = await client.post(
        f"/offers/{oid}/activities",
        json={"activity_type": "applied", "event_date": "2026-06-01", "note": "Envoyé"},
    )
    assert r.status_code == 201
    aid = r.json()["id"]
    assert r.json()["offer_id"] == oid
    assert r.json()["contact_id"] is None

    # Tri event_date desc.
    await client.post(
        f"/offers/{oid}/activities",
        json={"activity_type": "note", "event_date": "2026-06-10"},
    )
    lst = (await client.get(f"/offers/{oid}/activities")).json()
    assert [a["event_date"] for a in lst] == ["2026-06-10", "2026-06-01"]

    assert (await client.delete(f"/activities/{aid}")).status_code == 204
    lst2 = (await client.get(f"/offers/{oid}/activities")).json()
    assert len(lst2) == 1


async def test_activity_on_unknown_parent_404(client):
    r = await client.post(
        "/offers/99999/activities",
        json={"activity_type": "note", "event_date": "2026-06-01"},
    )
    assert r.status_code == 404


async def test_activity_rejects_unknown_document(client):
    oid = (await client.post("/offers", json={"title": "A", "company": "X"})).json()["id"]
    r = await client.post(
        f"/offers/{oid}/activities",
        json={"activity_type": "applied", "event_date": "2026-06-01", "document_id": 4242},
    )
    assert r.status_code == 400


# ─── Synchronisation last_action_date ─────────────────────
async def test_last_action_date_is_max_event_date(client):
    cid = (
        await client.post(
            "/contacts", json={"name": "C", "status": "contacte", "date_first_contact": "2026-01-01"}
        )
    ).json()["id"]

    # Premier événement action → last_action_date = son event_date.
    await client.post(
        f"/contacts/{cid}/activities",
        json={"activity_type": "contacted", "event_date": "2026-05-01"},
    )
    assert (await client.get(f"/contacts/{cid}")).json()["last_action_date"] == "2026-05-01"

    # Événement action plus récent → last_action_date avance.
    await client.post(
        f"/contacts/{cid}/activities",
        json={"activity_type": "replied", "event_date": "2026-06-01"},
    )
    assert (await client.get(f"/contacts/{cid}")).json()["last_action_date"] == "2026-06-01"

    # Une simple `note` (non-action), même postérieure, ne bouge PAS last_action_date.
    await client.post(
        f"/contacts/{cid}/activities",
        json={"activity_type": "note", "event_date": "2026-12-01"},
    )
    assert (await client.get(f"/contacts/{cid}")).json()["last_action_date"] == "2026-06-01"


# ─── Quick actions journalisées + relance toujours correcte ─
async def test_mark_contact_relanced_logs_activity_and_clears_relance(client):
    old = (date.today() - timedelta(days=60)).isoformat()
    cid = (
        await client.post(
            "/contacts",
            json={"name": "C", "status": "contacte", "date_first_contact": old},
        )
    ).json()["id"]

    r = await client.post(f"/contacts/{cid}/mark-relanced")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "relance"
    assert body["last_action_date"] == date.today().isoformat()
    # Après relance aujourd'hui, plus de relance due (délai par défaut 10 j).
    assert body["needs_relance"] is False

    acts = (await client.get(f"/contacts/{cid}/activities")).json()
    assert any(
        a["activity_type"] == "relance" and a["event_date"] == date.today().isoformat()
        for a in acts
    )


async def test_mark_offer_relanced_logs_activity(client):
    oid = (
        await client.post("/offers", json={"title": "A", "company": "X", "status": "postule"})
    ).json()["id"]
    r = await client.post(f"/offers/{oid}/mark-relanced")
    assert r.status_code == 200
    assert r.json()["status"] == "relance"
    acts = (await client.get(f"/offers/{oid}/activities")).json()
    assert any(a["activity_type"] == "relance" for a in acts)
