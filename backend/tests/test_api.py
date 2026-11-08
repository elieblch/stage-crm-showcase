"""Tests d'intégration des endpoints REST."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

pytestmark = pytest.mark.asyncio


# ─── Offers CRUD ──────────────────────────────────────────
async def test_create_and_get_offer(client):
    r = await client.post("/offers", json={"title": "Stage M&A", "company": "Lazard"})
    assert r.status_code == 201
    offer = r.json()
    assert offer["id"] > 0
    assert offer["status"] == "a_postuler"
    assert offer["priority"] == "moyenne"
    assert offer["date_added"] == offer["last_action_date"]
    assert offer["needs_relance"] is False

    r2 = await client.get(f"/offers/{offer['id']}")
    assert r2.status_code == 200
    assert r2.json()["title"] == "Stage M&A"


async def test_list_offers_filters(client):
    await client.post("/offers", json={"title": "A", "company": "X", "priority": "haute"})
    await client.post("/offers", json={"title": "B", "company": "Y", "status": "postule"})

    r = await client.get("/offers", params={"priority": "haute"})
    assert len(r.json()) == 1
    assert r.json()[0]["title"] == "A"

    r = await client.get("/offers", params={"status": "postule"})
    assert len(r.json()) == 1
    assert r.json()[0]["title"] == "B"


async def test_update_offer_status_resets_last_action(client):
    r = await client.post(
        "/offers",
        json={"title": "A", "company": "X", "date_added": "2026-01-01"},
    )
    oid = r.json()["id"]
    assert r.json()["last_action_date"] == "2026-01-01"

    r2 = await client.put(f"/offers/{oid}", json={"status": "postule"})
    assert r2.status_code == 200
    # Changement de statut → last_action_date repassée à aujourd'hui.
    assert r2.json()["last_action_date"] == date.today().isoformat()


async def test_delete_offer(client):
    r = await client.post("/offers", json={"title": "A", "company": "X"})
    oid = r.json()["id"]
    assert (await client.delete(f"/offers/{oid}")).status_code == 204
    assert (await client.get(f"/offers/{oid}")).status_code == 404


async def test_get_missing_offer_404(client):
    assert (await client.get("/offers/9999")).status_code == 404


# ─── needs_relance flag dans la liste ─────────────────────
async def test_offer_needs_relance_flag(client):
    old = (date.today() - timedelta(days=20)).isoformat()
    r = await client.post(
        "/offers",
        json={"title": "A", "company": "X", "status": "postule", "date_added": old},
    )
    oid = r.json()["id"]
    # date_added ancienne → last_action_date ancienne → relance due (délai défaut 10j).
    got = (await client.get(f"/offers/{oid}")).json()
    assert got["needs_relance"] is True
    assert got["days_overdue"] == 10

    r2 = await client.get("/offers", params={"needs_relance": "true"})
    assert len(r2.json()) == 1
    r3 = await client.get("/offers", params={"needs_relance": "false"})
    assert len(r3.json()) == 0


async def test_mark_offer_relanced(client):
    old = (date.today() - timedelta(days=20)).isoformat()
    r = await client.post(
        "/offers",
        json={"title": "A", "company": "X", "status": "postule", "date_added": old},
    )
    oid = r.json()["id"]
    r2 = await client.post(f"/offers/{oid}/mark-relanced")
    body = r2.json()
    assert body["status"] == "relance"
    assert body["last_action_date"] == date.today().isoformat()
    assert body["next_relance_date"] is None
    assert body["needs_relance"] is False


# ─── Contacts ─────────────────────────────────────────────
async def test_contact_crud_and_offer_link(client):
    o = (await client.post("/offers", json={"title": "A", "company": "X"})).json()
    r = await client.post(
        "/contacts",
        json={"name": "Jean Dupont", "company": "X", "offer_id": o["id"], "status": "contacte"},
    )
    assert r.status_code == 201
    cid = r.json()["id"]

    # Contacts liés à l'offre.
    linked = (await client.get(f"/offers/{o['id']}/contacts")).json()
    assert len(linked) == 1 and linked[0]["id"] == cid

    # Filtre par offer_id.
    r2 = await client.get("/contacts", params={"offer_id": o["id"]})
    assert len(r2.json()) == 1


async def test_contact_invalid_offer_id_400(client):
    r = await client.post("/contacts", json={"name": "Jean", "offer_id": 4242})
    assert r.status_code == 400


async def test_contact_offer_set_null_on_offer_delete(client):
    o = (await client.post("/offers", json={"title": "A", "company": "X"})).json()
    c = (await client.post("/contacts", json={"name": "Jean", "offer_id": o["id"]})).json()
    await client.delete(f"/offers/{o['id']}")
    got = (await client.get(f"/contacts/{c['id']}")).json()
    assert got["offer_id"] is None


async def test_mark_contact_relanced(client):
    old = (date.today() - timedelta(days=20)).isoformat()
    c = (await client.post("/contacts", json={"name": "Jean", "status": "contacte"})).json()
    r = await client.post(f"/contacts/{c['id']}/mark-relanced")
    assert r.json()["status"] == "relance"


# ─── Stories ──────────────────────────────────────────────
async def test_story_crud_and_tag_filter(client):
    s = {
        "title": "Restructuration",
        "situation": "s",
        "task": "t",
        "action": "a",
        "result": "r",
        "tags": ["finance", "leadership"],
    }
    r = await client.post("/stories", json=s)
    assert r.status_code == 201
    sid = r.json()["id"]

    await client.post(
        "/stories",
        json={**s, "title": "Autre", "tags": ["teamwork"]},
    )

    # Filtre par tag.
    r2 = await client.get("/stories", params={"tags": "finance"})
    assert len(r2.json()) == 1 and r2.json()[0]["id"] == sid

    # Update.
    r3 = await client.put(f"/stories/{sid}", json={"title": "Maj"})
    assert r3.json()["title"] == "Maj"

    # Delete.
    assert (await client.delete(f"/stories/{sid}")).status_code == 204


# ─── Settings ─────────────────────────────────────────────
async def test_settings_default_and_update(client):
    r = await client.get("/settings")
    assert r.json()["relance_delay_days"] == 10

    r2 = await client.put("/settings", json={"relance_delay_days": 5})
    assert r2.json()["relance_delay_days"] == 5

    # Le nouveau délai change le calcul de relance.
    old = (date.today() - timedelta(days=6)).isoformat()
    o = await client.post(
        "/offers",
        json={"title": "A", "company": "X", "status": "postule", "date_added": old},
    )
    assert o.json()["needs_relance"] is True  # 6 jours > délai 5


async def test_settings_reject_negative(client):
    assert (await client.put("/settings", json={"relance_delay_days": -1})).status_code == 400


# ─── Relances endpoint ────────────────────────────────────
async def test_relances_endpoint(client):
    old = (date.today() - timedelta(days=30)).isoformat()
    recent = (date.today() - timedelta(days=15)).isoformat()
    # Offre en retard de 20 jours.
    await client.post(
        "/offers",
        json={"title": "Retard", "company": "X", "status": "postule", "date_added": old},
    )
    # Offre en retard de 5 jours.
    await client.post(
        "/offers",
        json={"title": "Moins", "company": "Y", "status": "postule", "date_added": recent},
    )
    # Contact en retard.
    await client.post(
        "/contacts",
        json={"name": "Jean", "status": "contacte", "next_relance_date": old},
    )
    # Deadline proche.
    soon = (date.today() + timedelta(days=2)).isoformat()
    await client.post(
        "/offers",
        json={"title": "Deadline", "company": "Z", "deadline": soon},
    )

    r = await client.get("/relances")
    body = r.json()
    assert len(body["relances"]) == 3
    # Tri par urgence décroissante.
    overdue = [x["days_overdue"] for x in body["relances"]]
    assert overdue == sorted(overdue, reverse=True)
    assert len(body["deadlines"]) == 1
    assert body["deadlines"][0]["days_left"] == 2


# ─── Dashboard ────────────────────────────────────────────
async def test_dashboard(client):
    old = (date.today() - timedelta(days=30)).isoformat()
    await client.post("/offers", json={"title": "A", "company": "X", "status": "postule", "date_added": old})
    await client.post("/offers", json={"title": "B", "company": "Y"})
    await client.post("/contacts", json={"name": "Jean", "status": "a_contacter"})

    r = await client.get("/dashboard")
    d = r.json()
    assert d["offers_total"] == 2
    assert d["contacts_total"] == 1
    assert d["offers_by_status"]["postule"] == 1
    assert d["offers_by_status"]["a_postuler"] == 1
    assert d["relances_due"] == 1
