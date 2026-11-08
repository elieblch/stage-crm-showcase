"""Endpoints d'agrégation — statistiques / funnel.

100 % calculé en local à partir de `activities` (+ offers / contacts / documents).
Aucune IA, aucun appel réseau. Les dénominateurs nuls renvoient `null` (jamais de
division par zéro).
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.models import (
    Activity,
    ActivityType,
    Contact,
    ContactStatus,
    Document,
    DocType,
    Offer,
    OfferStatus,
)
from app.schemas.schemas import (
    ByCvOut,
    CvStatItem,
    FunnelOut,
    FunnelStage,
    OutreachOut,
    ResponseRateOut,
    WeeklyActivityItem,
    WeeklyActivityOut,
)

router = APIRouter(prefix="/stats")

# Rang des statuts d'offre (pour « statut ≥ postulé »).
_OFFER_STATUS_ORDER = [
    OfferStatus.a_postuler,
    OfferStatus.postule,
    OfferStatus.relance,
    OfferStatus.entretien,
    OfferStatus.offre_recue,
    OfferStatus.refuse,
    OfferStatus.sans_suite,
]
OFFER_STATUS_RANK = {s.value: i for i, s in enumerate(_OFFER_STATUS_ORDER)}
_APPLIED_MIN_RANK = OFFER_STATUS_RANK[OfferStatus.postule.value]


async def _offer_activities(db: AsyncSession) -> list[Activity]:
    return list(
        (await db.execute(select(Activity).where(Activity.offer_id.isnot(None)))).scalars().all()
    )


def _types_by_parent(acts: list[Activity], key: str) -> dict[int, set[str]]:
    out: dict[int, set[str]] = defaultdict(set)
    for a in acts:
        out[getattr(a, key)].add(a.activity_type)
    return out


def _earliest_dates(acts: list[Activity], activity_type: str) -> dict[int, date]:
    """offer_id → plus ancienne event_date pour ce type d'événement."""
    out: dict[int, date] = {}
    for a in acts:
        if a.activity_type == activity_type:
            cur = out.get(a.offer_id)
            if cur is None or a.event_date < cur:
                out[a.offer_id] = a.event_date
    return out


# ══════════════════════════════════════════════════════════
@router.get("/funnel", response_model=FunnelOut)
async def stats_funnel(db: AsyncSession = Depends(get_db)):
    offers = (await db.execute(select(Offer))).scalars().all()
    types = _types_by_parent(await _offer_activities(db), "offer_id")

    applied = responded = interview = offer_recv = 0
    for o in offers:
        t = types.get(o.id, set())
        rank = OFFER_STATUS_RANK.get(o.status, 0)
        if ActivityType.applied.value in t or rank >= _APPLIED_MIN_RANK:
            applied += 1
        if ActivityType.response_received.value in t:
            responded += 1
        if (
            ActivityType.interview_scheduled.value in t
            or ActivityType.interview_done.value in t
            or o.status == OfferStatus.entretien.value
        ):
            interview += 1
        if ActivityType.offer_received.value in t or o.status == OfferStatus.offre_recue.value:
            offer_recv += 1

    return FunnelOut(
        stages=[
            FunnelStage(key="applied", label="Candidatures envoyées", count=applied),
            FunnelStage(key="response_received", label="Réponses reçues", count=responded),
            FunnelStage(key="interview", label="Entretiens", count=interview),
            FunnelStage(key="offer_received", label="Offres reçues", count=offer_recv),
        ]
    )


@router.get("/response-rate", response_model=ResponseRateOut)
async def stats_response_rate(db: AsyncSession = Depends(get_db)):
    acts = await _offer_activities(db)
    applied_dates = _earliest_dates(acts, ActivityType.applied.value)
    response_dates = _earliest_dates(acts, ActivityType.response_received.value)

    applied_count = len(applied_dates)
    responded_ids = [oid for oid in applied_dates if oid in response_dates]
    responded_count = len(responded_ids)
    response_rate = (responded_count / applied_count) if applied_count else None

    deltas = [
        (response_dates[oid] - applied_dates[oid]).days
        for oid in responded_ids
        if response_dates[oid] >= applied_dates[oid]
    ]
    avg_ttr = (sum(deltas) / len(deltas)) if deltas else None

    return ResponseRateOut(
        applied_count=applied_count,
        responded_count=responded_count,
        response_rate=response_rate,
        avg_time_to_response_days=avg_ttr,
    )


@router.get("/by-cv", response_model=ByCvOut)
async def stats_by_cv(db: AsyncSession = Depends(get_db)):
    acts = await _offer_activities(db)
    response_dates = _earliest_dates(acts, ActivityType.response_received.value)

    # Événement `applied` le plus ancien PORTANT un document, par offre.
    applied_cv: dict[int, tuple[int, date]] = {}
    for a in acts:
        if a.activity_type == ActivityType.applied.value and a.document_id is not None:
            cur = applied_cv.get(a.offer_id)
            if cur is None or a.event_date < cur[1]:
                applied_cv[a.offer_id] = (a.document_id, a.event_date)

    cv_docs = (
        await db.execute(select(Document).where(Document.doc_type == DocType.cv.value))
    ).scalars().all()
    label_by_id = {d.id: d.label for d in cv_docs}

    per_cv: dict[int, list[int]] = defaultdict(list)
    for oid, (cvid, _d) in applied_cv.items():
        per_cv[cvid].append(oid)

    items: list[CvStatItem] = []
    for cvid, offer_ids in per_cv.items():
        vol = len(offer_ids)
        resp = 0
        for oid in offer_ids:
            applied_date = applied_cv[oid][1]
            rd = response_dates.get(oid)
            if rd is not None and rd >= applied_date:
                resp += 1
        items.append(
            CvStatItem(
                document_id=cvid,
                label=label_by_id.get(cvid, f"CV #{cvid}"),
                applied_count=vol,
                responded_count=resp,
                response_rate=(resp / vol) if vol else None,
            )
        )

    # Tri : taux décroissant puis volume décroissant.
    items.sort(key=lambda i: (-(i.response_rate or 0.0), -i.applied_count))
    return ByCvOut(items=items)


@router.get("/weekly-activity", response_model=WeeklyActivityOut)
async def stats_weekly_activity(
    weeks: int = Query(default=12, ge=1, le=52),
    db: AsyncSession = Depends(get_db),
):
    today = date.today()
    current_monday = today - timedelta(days=today.isoweekday() - 1)
    range_start = current_monday - timedelta(weeks=weeks - 1)

    def iso_key(d: date) -> str:
        y, w, _ = d.isocalendar()
        return f"{y}-W{w:02d}"

    buckets: list[WeeklyActivityItem] = []
    key_to_idx: dict[str, int] = {}
    for i in range(weeks - 1, -1, -1):
        ws = current_monday - timedelta(weeks=i)
        key_to_idx[iso_key(ws)] = len(buckets)
        buckets.append(WeeklyActivityItem(week=iso_key(ws), week_start=ws, applied=0, relance=0))

    all_acts = (await db.execute(select(Activity))).scalars().all()
    for a in all_acts:
        if a.event_date < range_start or a.event_date > today:
            continue
        idx = key_to_idx.get(iso_key(a.event_date))
        if idx is None:
            continue
        if a.activity_type == ActivityType.applied.value:
            buckets[idx].applied += 1
        elif a.activity_type == ActivityType.relance.value:
            buckets[idx].relance += 1

    return WeeklyActivityOut(weeks=buckets)


@router.get("/outreach", response_model=OutreachOut)
async def stats_outreach(db: AsyncSession = Depends(get_db)):
    contacts = (await db.execute(select(Contact))).scalars().all()
    contact_acts = list(
        (await db.execute(select(Activity).where(Activity.contact_id.isnot(None)))).scalars().all()
    )
    types = _types_by_parent(contact_acts, "contact_id")

    contacted = replied = 0
    for c in contacts:
        t = types.get(c.id, set())
        if ActivityType.contacted.value in t or c.status != ContactStatus.a_contacter.value:
            contacted += 1
        if (
            ActivityType.replied.value in t
            or ActivityType.response_received.value in t
            or c.status in (ContactStatus.repondu.value, ContactStatus.rdv_obtenu.value)
        ):
            replied += 1

    return OutreachOut(
        contacted_count=contacted,
        replied_count=replied,
        reply_rate=(replied / contacted) if contacted else None,
    )
