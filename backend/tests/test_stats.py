"""Tests des agrégations statistiques (funnel, response-rate, by-cv, weekly, outreach).

Jeux de données seedés via l'API (base SQLite isolée par test).
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

pytestmark = pytest.mark.asyncio


async def _offer(client, **kw) -> int:
    body = {"title": "T", "company": "C", **kw}
    r = await client.post("/offers", json=body)
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _act(client, kind: str, pid: int, activity_type: str, event_date: str, **kw):
    r = await client.post(
        f"/{kind}s/{pid}/activities",
        json={"activity_type": activity_type, "event_date": event_date, **kw},
    )
    assert r.status_code == 201, r.text
    return r.json()


async def _contact(client, **kw) -> int:
    r = await client.post("/contacts", json={"name": "N", **kw})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _upload_cv(client, label: str) -> int:
    r = await client.post(
        "/documents",
        data={"doc_type": "cv", "label": label},
        files={"file": (f"{label}.pdf", b"%PDF-1.4\n%stub\n", "application/pdf")},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


# ─── Funnel ───────────────────────────────────────────────
async def test_funnel_multi_stage(client):
    await _offer(client)  # o1 : a_postuler, aucun event → pas applied
    o2 = await _offer(client)
    await _act(client, "offer", o2, "applied", "2026-01-01")
    o3 = await _offer(client)
    await _act(client, "offer", o3, "applied", "2026-01-01")
    await _act(client, "offer", o3, "response_received", "2026-01-05")
    o4 = await _offer(client)
    await _act(client, "offer", o4, "applied", "2026-01-01")
    await _act(client, "offer", o4, "response_received", "2026-01-05")
    await _act(client, "offer", o4, "interview_scheduled", "2026-01-10")
    await _offer(client, status="offre_recue")  # o5 : compte applied (rang) + offer_received

    stages = (await client.get("/stats/funnel")).json()["stages"]
    counts = {s["key"]: s["count"] for s in stages}
    assert [s["key"] for s in stages] == [
        "applied",
        "response_received",
        "interview",
        "offer_received",
    ]
    assert counts == {"applied": 4, "response_received": 2, "interview": 1, "offer_received": 1}


# ─── Response-rate ────────────────────────────────────────
async def test_response_rate_null_denominator(client):
    # Aucune candidature → pas de division par zéro.
    r = (await client.get("/stats/response-rate")).json()
    assert r["applied_count"] == 0
    assert r["responded_count"] == 0
    assert r["response_rate"] is None
    assert r["avg_time_to_response_days"] is None


async def test_response_rate_and_time_to_response(client):
    a = await _offer(client)
    await _act(client, "offer", a, "applied", "2026-01-01")
    await _act(client, "offer", a, "response_received", "2026-01-06")  # +5 j
    b = await _offer(client)
    await _act(client, "offer", b, "applied", "2026-02-01")  # sans réponse

    r = (await client.get("/stats/response-rate")).json()
    assert r["applied_count"] == 2
    assert r["responded_count"] == 1
    assert r["response_rate"] == 0.5
    assert r["avg_time_to_response_days"] == 5.0


# ─── By-CV ────────────────────────────────────────────────
async def test_by_cv_multiple_documents(client):
    cv_a = await _upload_cv(client, "CV_A")
    cv_b = await _upload_cv(client, "CV_B")

    a1 = await _offer(client)
    await _act(client, "offer", a1, "applied", "2026-01-01", document_id=cv_a)
    await _act(client, "offer", a1, "response_received", "2026-01-08")
    a2 = await _offer(client)
    await _act(client, "offer", a2, "applied", "2026-01-02", document_id=cv_a)  # sans réponse
    b1 = await _offer(client)
    await _act(client, "offer", b1, "applied", "2026-01-03", document_id=cv_b)
    await _act(client, "offer", b1, "response_received", "2026-01-09")

    items = (await client.get("/stats/by-cv")).json()["items"]
    assert len(items) == 2
    # Tri : taux décroissant → CV_B (1.0) avant CV_A (0.5).
    assert items[0]["document_id"] == cv_b
    assert items[0]["label"] == "CV_B"
    assert items[0]["applied_count"] == 1
    assert items[0]["response_rate"] == 1.0
    assert items[1]["document_id"] == cv_a
    assert items[1]["applied_count"] == 2
    assert items[1]["responded_count"] == 1
    assert items[1]["response_rate"] == 0.5


# ─── Weekly activity ──────────────────────────────────────
async def test_weekly_activity_iso_buckets(client):
    o = await _offer(client)
    today = date.today()
    last_week = today - timedelta(days=7)
    await _act(client, "offer", o, "applied", today.isoformat())
    await _act(client, "offer", o, "relance", last_week.isoformat())

    data = (await client.get("/stats/weekly-activity", params={"weeks": 4})).json()["weeks"]
    assert len(data) == 4
    # Dernier bucket = semaine courante.
    assert data[-1]["applied"] == 1
    assert data[-1]["relance"] == 0
    # Avant-dernier = semaine passée.
    assert data[-2]["relance"] == 1
    assert data[-2]["applied"] == 0
    # Clés ISO ordonnées et distinctes.
    keys = [w["week"] for w in data]
    assert len(set(keys)) == 4


# ─── Outreach ─────────────────────────────────────────────
async def test_outreach_reply_rate(client):
    c1 = await _contact(client, status="contacte")
    await _act(client, "contact", c1, "contacted", "2026-01-01")
    await _contact(client, status="a_contacter")  # c2 : jamais contacté
    await _contact(client, status="repondu")  # c3 : contacté + a répondu (statut)
    c4 = await _contact(client, status="a_contacter")
    await _act(client, "contact", c4, "contacted", "2026-01-02")
    await _act(client, "contact", c4, "replied", "2026-01-04")

    r = (await client.get("/stats/outreach")).json()
    assert r["contacted_count"] == 3  # c1, c3, c4
    assert r["replied_count"] == 2  # c3 (statut), c4 (event)
    assert r["reply_rate"] == pytest.approx(2 / 3)
