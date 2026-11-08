"""Agenda — échéances à venir + export iCalendar (lecture seule).

Agrège trois sources DÉJÀ existantes (aucune écriture en base, aucune migration) :
  1. relances dues (logique de relance RÉUTILISÉE depuis `relance_service`),
  2. deadlines d'offres non terminales,
  3. entretiens / rdv planifiés (`activities`).
L'export .ics est généré localement via la lib `icalendar` (gratuite).
"""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.models.models import (
    Activity,
    ActivityType,
    AppSettings,
    Contact,
    CONTACT_WAITING_STATUSES,
    Offer,
    OFFER_WAITING_STATUSES,
    OfferStatus,
)
from app.schemas.schemas import AgendaItem, AgendaOut
from app.services.relance_service import CONTACT, OFFER, evaluate

router = APIRouter(prefix="/agenda")
settings = get_settings()

# Statuts d'offre terminaux : plus aucune échéance de deadline à afficher.
OFFER_TERMINAL_STATUSES: set[str] = {
    OfferStatus.offre_recue.value,
    OfferStatus.refuse.value,
    OfferStatus.sans_suite.value,
}

# Types d'activités « rendez-vous planifié » repris dans l'agenda.
_MEETING_TYPES = {
    ActivityType.interview_scheduled.value,
    ActivityType.meeting_scheduled.value,
}


async def _relance_delay_days(db: AsyncSession) -> int:
    """Délai de relance — lecture SEULE (ne crée pas la ligne settings)."""
    row = await db.get(AppSettings, settings.single_user_id)
    return row.relance_delay_days if row is not None else 10


def _join(*parts: str | None) -> str:
    return " / ".join(p for p in parts if p)


async def collect_agenda_items(db: AsyncSession, days: int) -> list[AgendaItem]:
    today = date.today()
    horizon = today + timedelta(days=days)
    delay = await _relance_delay_days(db)

    offers = list((await db.execute(select(Offer))).scalars().all())
    contacts = list((await db.execute(select(Contact))).scalars().all())

    items: list[AgendaItem] = []

    # ── 1. Relances dues (logique réutilisée : evaluate) ──────────────────
    for o in offers:
        if o.no_relance or o.status not in OFFER_WAITING_STATUSES:
            continue
        ev = evaluate(
            kind=OFFER,
            no_relance=o.no_relance,
            status=o.status,
            last_action_date=o.last_action_date,
            next_relance_date=o.next_relance_date,
            relance_delay_days=delay,
            today=today,
        )
        if ev.due_date <= horizon:
            items.append(
                AgendaItem(
                    kind="relance",
                    date=ev.due_date,
                    entity_type="offer",
                    entity_id=o.id,
                    label=_join("Relancer — " + o.company if o.company else "Relancer", o.title),
                    company=o.company,
                    title=o.title,
                    status=o.status,
                    overdue=ev.days_overdue > 0,
                )
            )

    for c in contacts:
        if c.no_relance or c.status not in CONTACT_WAITING_STATUSES:
            continue
        ev = evaluate(
            kind=CONTACT,
            no_relance=c.no_relance,
            status=c.status,
            last_action_date=c.last_action_date,
            next_relance_date=c.next_relance_date,
            relance_delay_days=delay,
            today=today,
        )
        if ev.due_date <= horizon:
            items.append(
                AgendaItem(
                    kind="relance",
                    date=ev.due_date,
                    entity_type="contact",
                    entity_id=c.id,
                    label=_join("Relancer — " + c.name, c.company),
                    company=c.company,
                    title=c.name,
                    status=c.status,
                    overdue=ev.days_overdue > 0,
                )
            )

    # ── 2. Deadlines d'offres (non terminales, dans la fenêtre) ───────────
    for o in offers:
        if o.deadline is None or o.status in OFFER_TERMINAL_STATUSES:
            continue
        if today <= o.deadline <= horizon:
            items.append(
                AgendaItem(
                    kind="deadline",
                    date=o.deadline,
                    entity_type="offer",
                    entity_id=o.id,
                    label=f"Deadline — {o.title}",
                    company=o.company,
                    title=o.title,
                    status=o.status,
                )
            )

    # ── 3. Entretiens / rdv planifiés (activities dans la fenêtre) ────────
    offers_by_id = {o.id: o for o in offers}
    contacts_by_id = {c.id: c for c in contacts}
    meeting_acts = (
        await db.execute(
            select(Activity).where(Activity.activity_type.in_(_MEETING_TYPES))
        )
    ).scalars().all()
    for a in meeting_acts:
        if not (today <= a.event_date <= horizon):
            continue
        if a.offer_id is not None:
            o = offers_by_id.get(a.offer_id)
            company, title = (o.company, o.title) if o else (None, None)
            entity_type, entity_id = "offer", a.offer_id
        elif a.contact_id is not None:
            c = contacts_by_id.get(a.contact_id)
            company, title = (c.company, c.name) if c else (None, None)
            entity_type, entity_id = "contact", a.contact_id
        else:
            continue
        is_interview = a.activity_type == ActivityType.interview_scheduled.value
        prefix = "Entretien" if is_interview else "RDV"
        items.append(
            AgendaItem(
                kind="interview",
                date=a.event_date,
                entity_type=entity_type,
                entity_id=entity_id,
                label=f"{prefix} — {_join(company, title) or 'à planifier'}",
                company=company,
                title=title,
                note=a.note,
            )
        )

    # Tri par date croissante (les overdue, date < aujourd'hui, remontent en tête).
    items.sort(key=lambda i: (i.date, i.kind, i.entity_type, i.entity_id))
    return items


@router.get("", response_model=AgendaOut)
async def get_agenda(
    days: int = Query(default=30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
):
    return AgendaOut(days=days, items=await collect_agenda_items(db, days))


@router.get("/export.ics")
async def export_agenda_ics(
    days: int = Query(default=30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
):
    from icalendar import Calendar, Event

    items = await collect_agenda_items(db, days)

    cal = Calendar()
    cal.add("prodid", "-//stage-crm//agenda//FR")
    cal.add("version", "2.0")
    cal.add("x-wr-calname", "Agenda — Stage CRM")

    for it in items:
        ev = Event()
        ev.add("uid", f"{it.kind}-{it.entity_type}-{it.entity_id}-{it.date.isoformat()}@stage-crm")
        ev.add("summary", it.label)
        ev.add("dtstart", it.date)  # objet date → journée entière (VALUE=DATE)
        desc_parts = []
        if it.status:
            desc_parts.append(f"Statut : {it.status}")
        if it.overdue:
            desc_parts.append("En retard")
        if it.note:
            desc_parts.append(it.note)
        if desc_parts:
            ev.add("description", " — ".join(desc_parts))
        cal.add_component(ev)

    return Response(
        content=cal.to_ical(),
        media_type="text/calendar; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="agenda-stage-crm.ics"',
        },
    )
