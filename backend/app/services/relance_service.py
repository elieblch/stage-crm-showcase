"""Logique de relance — cœur du système.

Module **pur** (aucune dépendance DB, aucun appel réseau) afin d'être
trivialement testable. Le calcul est fait à la volée, il n'y a aucun scheduler.

Une entrée (offre ou contact) nécessite une relance si :
  1. ``no_relance`` est faux, ET
  2. son statut est « en attente de réponse », ET
  3. la date d'échéance est atteinte :
     - si ``next_relance_date`` est défini → due quand ``next_relance_date <= today``
       (l'override manuel l'emporte toujours),
     - sinon → due quand ``last_action_date + relance_delay_days <= today``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from app.models.models import CONTACT_WAITING_STATUSES, OFFER_WAITING_STATUSES

OFFER = "offer"
CONTACT = "contact"

_WAITING_BY_KIND: dict[str, set[str]] = {
    OFFER: OFFER_WAITING_STATUSES,
    CONTACT: CONTACT_WAITING_STATUSES,
}


def compute_due_date(
    last_action_date: date,
    next_relance_date: date | None,
    relance_delay_days: int,
) -> date:
    """Date d'échéance de la relance. L'override manuel l'emporte toujours."""
    if next_relance_date is not None:
        return next_relance_date
    return last_action_date + timedelta(days=relance_delay_days)


@dataclass(frozen=True)
class RelanceEval:
    needs_relance: bool
    due_date: date
    days_overdue: int  # >= 0 quand due, négatif/0 sinon (jours restants)


def evaluate(
    *,
    kind: str,
    no_relance: bool,
    status: str,
    last_action_date: date,
    next_relance_date: date | None,
    relance_delay_days: int,
    today: date,
) -> RelanceEval:
    """Évalue le besoin de relance d'une entrée à une date donnée."""
    waiting = _WAITING_BY_KIND[kind]
    due = compute_due_date(last_action_date, next_relance_date, relance_delay_days)
    days_overdue = (today - due).days

    needs = (not no_relance) and (status in waiting) and (due <= today)
    return RelanceEval(needs_relance=needs, due_date=due, days_overdue=days_overdue)


def deadline_is_soon(
    *,
    status: str,
    deadline: date | None,
    today: date,
    window_days: int = 3,
) -> bool:
    """Une offre encore à postuler dont la deadline arrive dans <= window_days."""
    from app.models.models import OfferStatus

    if deadline is None:
        return False
    if status != OfferStatus.a_postuler.value:
        return False
    days_left = (deadline - today).days
    return 0 <= days_left <= window_days
