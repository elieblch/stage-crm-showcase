"""Tests des entretiens (rounds) rattachés à une offre.

- CRUD interviews ; `offer_id` requis (offre inconnue → 404) ; enums validés.
- CASCADE : suppression offre → interviews → liens ; suppression story → liens
  retirés (interview conservé) ; suppression interview → liens retirés (stories
  conservées).
- Attach / detach de stories STAR ; `InterviewOut` expose les stories liées.
- Cohésion timeline : `scheduled_at` → activity `interview_scheduled` ;
  `outcome=passed` → `interview_done` ; `last_action_date` mis à jour ; pas de
  doublon d'activity.
"""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import func, select

from app.models.models import (
    Interview,
    InterviewStory,
    Offer,
    interview_stories_link,
)

pytestmark = pytest.mark.asyncio


# ─── Helpers ──────────────────────────────────────────────
async def _make_offer(client, **kw) -> int:
    body = {"title": "A", "company": "X", **kw}
    return (await client.post("/offers", json=body)).json()["id"]


async def _make_story(client, title="Leadership") -> int:
    body = {
        "title": title,
        "situation": "s",
        "task": "t",
        "action": "a",
        "result": "r",
    }
    return (await client.post("/stories", json=body)).json()["id"]


async def _count_links(db_session) -> int:
    return (
        await db_session.execute(select(func.count()).select_from(interview_stories_link))
    ).scalar_one()


# ─── CRUD ─────────────────────────────────────────────────
async def test_create_list_get_interview(client):
    oid = await _make_offer(client)
    r = await client.post(
        f"/offers/{oid}/interviews",
        json={"round_label": "RH", "interviewer": "Alice", "format": "visio"},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["offer_id"] == oid
    assert body["round_label"] == "RH"
    assert body["outcome"] == "pending"  # défaut
    assert body["stories"] == []
    iid = body["id"]

    lst = (await client.get(f"/offers/{oid}/interviews")).json()
    assert [i["id"] for i in lst] == [iid]

    got = (await client.get(f"/interviews/{iid}")).json()
    assert got["interviewer"] == "Alice"


async def test_update_and_delete_interview(client):
    oid = await _make_offer(client)
    iid = (
        await client.post(f"/offers/{oid}/interviews", json={"round_label": "Technique"})
    ).json()["id"]

    r = await client.patch(
        f"/interviews/{iid}",
        json={"feeling": "plutôt bien", "next_step": "superday", "outcome": "pending_next"},
    )
    assert r.status_code == 200
    assert r.json()["feeling"] == "plutôt bien"
    assert r.json()["outcome"] == "pending_next"

    assert (await client.delete(f"/interviews/{iid}")).status_code == 204
    assert (await client.get(f"/interviews/{iid}")).status_code == 404


async def test_offer_id_required_unknown_offer_404(client):
    r = await client.post(
        "/offers/99999/interviews", json={"round_label": "RH"}
    )
    assert r.status_code == 404


async def test_enums_validated(client):
    oid = await _make_offer(client)
    bad_format = await client.post(
        f"/offers/{oid}/interviews", json={"round_label": "RH", "format": "carrier-pigeon"}
    )
    assert bad_format.status_code == 422
    bad_outcome = await client.post(
        f"/offers/{oid}/interviews", json={"round_label": "RH", "outcome": "maybe"}
    )
    assert bad_outcome.status_code == 422


# ─── Attach / detach stories ──────────────────────────────
async def test_attach_and_detach_story(client):
    oid = await _make_offer(client)
    iid = (
        await client.post(f"/offers/{oid}/interviews", json={"round_label": "RH"})
    ).json()["id"]
    sid = await _make_story(client, title="Conflit résolu")

    r = await client.post(f"/interviews/{iid}/stories/{sid}")
    assert r.status_code == 200
    stories = r.json()["stories"]
    assert len(stories) == 1
    assert stories[0]["id"] == sid
    assert stories[0]["title"] == "Conflit résolu"

    # Idempotent : ré-attacher ne duplique pas.
    r2 = await client.post(f"/interviews/{iid}/stories/{sid}")
    assert len(r2.json()["stories"]) == 1

    # InterviewOut expose bien les stories liées lors d'un GET.
    got = (await client.get(f"/interviews/{iid}")).json()
    assert [s["id"] for s in got["stories"]] == [sid]

    r3 = await client.delete(f"/interviews/{iid}/stories/{sid}")
    assert r3.status_code == 200
    assert r3.json()["stories"] == []


async def test_attach_unknown_story_404(client):
    oid = await _make_offer(client)
    iid = (
        await client.post(f"/offers/{oid}/interviews", json={"round_label": "RH"})
    ).json()["id"]
    r = await client.post(f"/interviews/{iid}/stories/424242")
    assert r.status_code == 404


# ─── CASCADE ──────────────────────────────────────────────
async def test_cascade_delete_offer_removes_interviews_and_links(db_session):
    offer = Offer(title="A", company="X")
    story = InterviewStory(title="S", situation="s", task="t", action="a", result="r")
    db_session.add_all([offer, story])
    await db_session.flush()
    interview = Interview(offer_id=offer.id, round_label="RH")
    interview.stories.append(story)
    db_session.add(interview)
    await db_session.commit()
    assert await _count_links(db_session) == 1

    await db_session.delete(offer)
    await db_session.flush()
    # Interview supprimé par CASCADE, lien supprimé, mais la story survit.
    assert (
        await db_session.execute(select(func.count()).select_from(Interview))
    ).scalar_one() == 0
    assert await _count_links(db_session) == 0
    assert (
        await db_session.execute(select(func.count()).select_from(InterviewStory))
    ).scalar_one() == 1


async def test_cascade_delete_story_removes_link_keeps_interview(db_session):
    offer = Offer(title="A", company="X")
    story = InterviewStory(title="S", situation="s", task="t", action="a", result="r")
    db_session.add_all([offer, story])
    await db_session.flush()
    interview = Interview(offer_id=offer.id, round_label="RH")
    interview.stories.append(story)
    db_session.add(interview)
    await db_session.commit()

    await db_session.delete(story)
    await db_session.flush()
    assert await _count_links(db_session) == 0
    # L'entretien est conservé.
    assert (
        await db_session.execute(select(func.count()).select_from(Interview))
    ).scalar_one() == 1


async def test_cascade_delete_interview_removes_link_keeps_story(db_session):
    offer = Offer(title="A", company="X")
    story = InterviewStory(title="S", situation="s", task="t", action="a", result="r")
    db_session.add_all([offer, story])
    await db_session.flush()
    interview = Interview(offer_id=offer.id, round_label="RH")
    interview.stories.append(story)
    db_session.add(interview)
    await db_session.commit()

    await db_session.delete(interview)
    await db_session.flush()
    assert await _count_links(db_session) == 0
    # La story STAR est conservée.
    assert (
        await db_session.execute(select(func.count()).select_from(InterviewStory))
    ).scalar_one() == 1


# ─── Cohésion timeline ────────────────────────────────────
async def _offer_activities(client, oid):
    return (await client.get(f"/offers/{oid}/activities")).json()


async def test_scheduled_at_creates_interview_scheduled_activity(client):
    oid = await _make_offer(client)
    await client.post(
        f"/offers/{oid}/interviews",
        json={"round_label": "RH", "scheduled_at": "2026-06-15T10:00:00"},
    )
    acts = await _offer_activities(client, oid)
    sched = [a for a in acts if a["activity_type"] == "interview_scheduled"]
    assert len(sched) == 1
    assert sched[0]["event_date"] == "2026-06-15"
    # interview_scheduled est une action → last_action_date avance.
    assert (await client.get(f"/offers/{oid}")).json()["last_action_date"] == "2026-06-15"


async def test_outcome_passed_creates_interview_done_no_duplicate(client):
    oid = await _make_offer(client)
    iid = (
        await client.post(
            f"/offers/{oid}/interviews",
            json={"round_label": "Technique", "scheduled_at": "2026-06-10T09:00:00"},
        )
    ).json()["id"]

    # Passage à passed → un seul interview_done.
    await client.patch(f"/interviews/{iid}", json={"outcome": "passed"})
    acts = await _offer_activities(client, oid)
    done = [a for a in acts if a["activity_type"] == "interview_done"]
    assert len(done) == 1

    # Un second PATCH avec le même/équivalent outcome final ne re-journalise PAS.
    await client.patch(f"/interviews/{iid}", json={"outcome": "rejected"})
    acts2 = await _offer_activities(client, oid)
    assert len([a for a in acts2 if a["activity_type"] == "interview_done"]) == 1
    # Et un seul interview_scheduled malgré les updates.
    assert len([a for a in acts2 if a["activity_type"] == "interview_scheduled"]) == 1


async def test_create_without_scheduled_at_no_activity(client):
    oid = await _make_offer(client)
    await client.post(f"/offers/{oid}/interviews", json={"round_label": "RH"})
    acts = await _offer_activities(client, oid)
    assert not any(a["activity_type"] == "interview_scheduled" for a in acts)
    assert not any(a["activity_type"] == "interview_done" for a in acts)
