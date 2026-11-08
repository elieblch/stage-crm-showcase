"""Tests unitaires de la logique de relance (cœur du système)."""

from datetime import date

import pytest

from app.models.models import ContactStatus, OfferStatus
from app.services.relance_service import (
    CONTACT,
    OFFER,
    compute_due_date,
    deadline_is_soon,
    evaluate,
)

TODAY = date(2026, 6, 9)


def _eval_offer(**kw):
    base = dict(
        kind=OFFER,
        no_relance=False,
        status=OfferStatus.postule.value,
        last_action_date=date(2026, 5, 30),
        next_relance_date=None,
        relance_delay_days=10,
        today=TODAY,
    )
    base.update(kw)
    return evaluate(**base)


# ─── compute_due_date ─────────────────────────────────────
def test_due_date_uses_delay_when_no_override():
    assert compute_due_date(date(2026, 6, 1), None, 10) == date(2026, 6, 11)


def test_due_date_override_wins():
    # L'override manuel l'emporte toujours, même s'il est plus tôt ou plus tard.
    assert compute_due_date(date(2026, 6, 1), date(2026, 6, 20), 10) == date(2026, 6, 20)
    assert compute_due_date(date(2026, 6, 1), date(2026, 6, 3), 10) == date(2026, 6, 3)


# ─── Échéance ─────────────────────────────────────────────
def test_relance_due_when_delay_passed():
    # last_action 2026-05-30 + 10j = 2026-06-09 == today → due (échéance pile).
    res = _eval_offer(last_action_date=date(2026, 5, 30))
    assert res.needs_relance is True
    assert res.due_date == date(2026, 6, 9)
    assert res.days_overdue == 0


def test_relance_due_exact_boundary():
    # Échéance pile : due_date == today doit déclencher la relance.
    res = _eval_offer(last_action_date=TODAY, relance_delay_days=0)
    assert res.needs_relance is True
    assert res.days_overdue == 0


def test_relance_not_due_before_delay():
    res = _eval_offer(last_action_date=date(2026, 6, 5), relance_delay_days=10)
    assert res.needs_relance is False
    assert res.due_date == date(2026, 6, 15)
    assert res.days_overdue == -6  # 6 jours restants


def test_days_overdue_positive_when_late():
    res = _eval_offer(last_action_date=date(2026, 5, 20), relance_delay_days=10)
    # due = 2026-05-30, today = 2026-06-09 → 10 jours de retard.
    assert res.needs_relance is True
    assert res.days_overdue == 10


# ─── Override prioritaire ─────────────────────────────────
def test_override_makes_relance_due_even_if_delay_not_passed():
    res = _eval_offer(
        last_action_date=TODAY,  # délai pas écoulé via la règle standard
        next_relance_date=date(2026, 6, 8),  # mais override dans le passé
        relance_delay_days=30,
    )
    assert res.needs_relance is True
    assert res.due_date == date(2026, 6, 8)
    assert res.days_overdue == 1


def test_override_in_future_postpones_relance():
    res = _eval_offer(
        last_action_date=date(2026, 5, 1),  # délai largement écoulé
        next_relance_date=date(2026, 6, 20),  # mais override repousse
        relance_delay_days=10,
    )
    assert res.needs_relance is False
    assert res.due_date == date(2026, 6, 20)


# ─── Statuts terminaux / non-attente ──────────────────────
@pytest.mark.parametrize(
    "status",
    [
        OfferStatus.a_postuler.value,
        OfferStatus.offre_recue.value,
        OfferStatus.refuse.value,
        OfferStatus.sans_suite.value,
    ],
)
def test_terminal_or_non_waiting_offer_status_never_relance(status):
    res = _eval_offer(status=status, last_action_date=date(2026, 1, 1))
    assert res.needs_relance is False


@pytest.mark.parametrize(
    "status",
    [OfferStatus.postule.value, OfferStatus.relance.value, OfferStatus.entretien.value],
)
def test_waiting_offer_statuses_can_relance(status):
    res = _eval_offer(status=status, last_action_date=date(2026, 1, 1))
    assert res.needs_relance is True


# ─── no_relance ───────────────────────────────────────────
def test_no_relance_flag_disables_relance():
    res = _eval_offer(no_relance=True, last_action_date=date(2026, 1, 1))
    assert res.needs_relance is False


# ─── Contacts ─────────────────────────────────────────────
def test_contact_waiting_status_relance():
    res = evaluate(
        kind=CONTACT,
        no_relance=False,
        status=ContactStatus.contacte.value,
        last_action_date=date(2026, 5, 20),
        next_relance_date=None,
        relance_delay_days=10,
        today=TODAY,
    )
    assert res.needs_relance is True


@pytest.mark.parametrize(
    "status",
    [
        ContactStatus.a_contacter.value,
        ContactStatus.repondu.value,
        ContactStatus.rdv_obtenu.value,
        ContactStatus.sans_suite.value,
    ],
)
def test_contact_non_waiting_status_no_relance(status):
    res = evaluate(
        kind=CONTACT,
        no_relance=False,
        status=status,
        last_action_date=date(2026, 1, 1),
        next_relance_date=None,
        relance_delay_days=10,
        today=TODAY,
    )
    assert res.needs_relance is False


# ─── Deadlines proches ────────────────────────────────────
def test_deadline_soon_within_window():
    assert deadline_is_soon(
        status=OfferStatus.a_postuler.value,
        deadline=date(2026, 6, 11),
        today=TODAY,
    ) is True


def test_deadline_today_is_soon():
    assert deadline_is_soon(
        status=OfferStatus.a_postuler.value,
        deadline=TODAY,
        today=TODAY,
    ) is True


def test_deadline_past_not_soon():
    assert deadline_is_soon(
        status=OfferStatus.a_postuler.value,
        deadline=date(2026, 6, 1),
        today=TODAY,
    ) is False


def test_deadline_far_not_soon():
    assert deadline_is_soon(
        status=OfferStatus.a_postuler.value,
        deadline=date(2026, 6, 30),
        today=TODAY,
    ) is False


def test_deadline_only_for_a_postuler_status():
    assert deadline_is_soon(
        status=OfferStatus.postule.value,
        deadline=date(2026, 6, 10),
        today=TODAY,
    ) is False
