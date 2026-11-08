"""Tests de l'agenda : sélection des échéances + validité de l'export .ics."""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

pytestmark = pytest.mark.asyncio

TODAY = date.today()


def _d(offset: int) -> str:
    return (TODAY + timedelta(days=offset)).isoformat()


async def _offer(client, **kw) -> int:
    r = await client.post("/offers", json={"title": "T", "company": "Corp", **kw})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _contact(client, **kw) -> int:
    r = await client.post("/contacts", json={"name": "Jean", **kw})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _act(client, kind: str, pid: int, activity_type: str, event_date: str):
    r = await client.post(
        f"/{kind}s/{pid}/activities",
        json={"activity_type": activity_type, "event_date": event_date},
    )
    assert r.status_code == 201, r.text


async def _agenda(client, days: int = 30):
    r = await client.get("/agenda", params={"days": days})
    assert r.status_code == 200, r.text
    return r.json()["items"]


def _by_kind(items, kind):
    return [i for i in items if i["kind"] == kind]


# ─── Relances : due / overdue / exclusions ────────────────
async def test_relance_selection_and_overdue_flag(client):
    over = await _offer(client, status="postule", date_added=_d(-60))  # due = -50 → overdue
    soon = await _offer(client, status="postule", date_added=_d(0), next_relance_date=_d(3))
    await _offer(client, status="postule", date_added=_d(-60), no_relance=True)  # exclu
    await _offer(client, status="refuse", date_added=_d(-60))  # statut terminal → exclu
    await _offer(client, status="a_postuler", date_added=_d(-60))  # pas « en attente » → exclu

    relances = _by_kind(await _agenda(client, days=30), "relance")
    ids = {(i["entity_type"], i["entity_id"]) for i in relances}
    assert ("offer", over) in ids
    assert ("offer", soon) in ids
    assert len(relances) == 2  # seuls over + soon

    over_item = next(i for i in relances if i["entity_id"] == over)
    soon_item = next(i for i in relances if i["entity_id"] == soon)
    assert over_item["overdue"] is True
    assert soon_item["overdue"] is False


async def test_next_relance_date_takes_priority(client):
    # last_action = today → +delay(10) = today+10 ; mais next_relance_date = today+2 prioritaire.
    oid = await _offer(client, status="postule", date_added=_d(0), next_relance_date=_d(2))
    item = next(i for i in await _agenda(client, days=30) if i["entity_id"] == oid)
    assert item["date"] == _d(2)


async def test_relance_outside_window_excluded(client):
    # due = today+10 ; fenêtre 7 j → exclu ; fenêtre 30 j → inclus.
    oid = await _offer(client, status="postule", date_added=_d(0))
    assert not any(i["entity_id"] == oid for i in _by_kind(await _agenda(client, days=7), "relance"))
    assert any(i["entity_id"] == oid for i in _by_kind(await _agenda(client, days=30), "relance"))


async def test_contact_relance_overdue(client):
    cid = await _contact(client, status="contacte", next_relance_date=_d(-5))
    relances = _by_kind(await _agenda(client, days=30), "relance")
    item = next(i for i in relances if i["entity_type"] == "contact" and i["entity_id"] == cid)
    assert item["overdue"] is True


# ─── Deadlines ────────────────────────────────────────────
async def test_deadline_in_and_out_of_window(client):
    ok = await _offer(client, status="a_postuler", deadline=_d(5))
    await _offer(client, status="a_postuler", deadline=_d(100))  # hors fenêtre 30
    await _offer(client, status="a_postuler", deadline=_d(-2))  # passée → exclue
    await _offer(client, status="refuse", deadline=_d(5))  # terminale → exclue

    deadlines = _by_kind(await _agenda(client, days=30), "deadline")
    assert [i["entity_id"] for i in deadlines] == [ok]
    assert deadlines[0]["date"] == _d(5)


# ─── Entretiens / rdv ─────────────────────────────────────
async def test_interviews_future_included_past_excluded(client):
    o = await _offer(client, status="entretien")
    await _act(client, "offer", o, "interview_scheduled", _d(5))  # futur → inclus
    o2 = await _offer(client, status="entretien")
    await _act(client, "offer", o2, "interview_scheduled", _d(-5))  # passé → exclu
    c = await _contact(client, status="contacte")
    await _act(client, "contact", c, "meeting_scheduled", _d(3))  # futur → inclus

    interviews = _by_kind(await _agenda(client, days=30), "interview")
    entities = {(i["entity_type"], i["entity_id"]) for i in interviews}
    assert ("offer", o) in entities
    assert ("contact", c) in entities
    assert ("offer", o2) not in entities


# ─── Cohérence avec la logique de relance existante ───────
async def test_agenda_relances_match_relances_endpoint(client):
    await _offer(client, status="postule", date_added=_d(-60))  # due overdue
    await _offer(client, status="relance", date_added=_d(-40))  # due overdue
    await _contact(client, status="contacte", next_relance_date=_d(-3))  # due overdue
    await _offer(client, status="a_postuler", date_added=_d(-60))  # jamais relance

    # Items relance de l'agenda déjà dus (date <= aujourd'hui).
    due_agenda = {
        (i["entity_type"], i["entity_id"])
        for i in _by_kind(await _agenda(client, days=30), "relance")
        if i["date"] <= TODAY.isoformat()
    }
    relances = (await client.get("/relances")).json()["relances"]
    due_ref = {(r["kind"], r["id"]) for r in relances}
    assert due_agenda == due_ref


# ─── Validité de l'export .ics ────────────────────────────
async def test_ics_export_is_valid(client):
    await _offer(client, status="postule", date_added=_d(-60))  # relance overdue
    a = await _offer(client, status="a_postuler", deadline=_d(5))  # deadline
    await _act(client, "offer", a, "interview_scheduled", _d(4))  # interview

    items = await _agenda(client, days=30)

    r = await client.get("/agenda/export.ics", params={"days": 30})
    assert r.status_code == 200
    assert "text/calendar" in r.headers["content-type"]
    assert "attachment" in r.headers["content-disposition"]
    assert "agenda-stage-crm.ics" in r.headers["content-disposition"]

    from icalendar import Calendar

    cal = Calendar.from_ical(r.content)
    vevents = list(cal.walk("VEVENT"))
    assert len(vevents) == len(items) > 0

    uids = [str(ev.get("uid")) for ev in vevents]
    assert len(set(uids)) == len(uids)  # UID uniques
    summaries = {str(ev.get("summary")) for ev in vevents}
    assert {i["label"] for i in items} == summaries

    for ev in vevents:
        dt = ev.get("dtstart").dt
        # Journée entière → DATE, pas DATETIME.
        assert isinstance(dt, date) and not isinstance(dt, datetime)
