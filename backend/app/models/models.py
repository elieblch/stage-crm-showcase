from __future__ import annotations

from datetime import date, datetime
from enum import Enum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    func,
)
from sqlalchemy.types import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


# ─── Enums ────────────────────────────────────────────────
class OfferPriority(str, Enum):
    haute = "haute"
    moyenne = "moyenne"
    basse = "basse"


class OfferStatus(str, Enum):
    a_postuler = "a_postuler"
    postule = "postule"
    relance = "relance"
    entretien = "entretien"
    offre_recue = "offre_recue"
    refuse = "refuse"
    sans_suite = "sans_suite"


class ContactStatus(str, Enum):
    a_contacter = "a_contacter"
    contacte = "contacte"
    relance = "relance"
    repondu = "repondu"
    rdv_obtenu = "rdv_obtenu"
    sans_suite = "sans_suite"


class DocType(str, Enum):
    cv = "cv"
    lm = "lm"


class InterviewFormat(str, Enum):
    visio = "visio"
    onsite = "onsite"
    phone = "phone"


class InterviewOutcome(str, Enum):
    pending = "pending"
    passed = "passed"
    rejected = "rejected"
    pending_next = "pending_next"


class ActivityType(str, Enum):
    """Superset des types d'événements de la timeline (offres ET contacts)."""

    applied = "applied"
    relance = "relance"
    response_received = "response_received"
    interview_scheduled = "interview_scheduled"
    interview_done = "interview_done"
    offer_received = "offer_received"
    rejected = "rejected"
    contacted = "contacted"
    replied = "replied"
    meeting_scheduled = "meeting_scheduled"
    meeting_done = "meeting_done"
    note = "note"
    status_change = "status_change"
    other = "other"


# Types comptant comme une « action » : ils font avancer last_action_date
# (donc pilotent la relance). `note` et `other` sont de simples annotations.
ACTION_ACTIVITY_TYPES: set[str] = {
    ActivityType.applied.value,
    ActivityType.relance.value,
    ActivityType.response_received.value,
    ActivityType.interview_scheduled.value,
    ActivityType.interview_done.value,
    ActivityType.offer_received.value,
    ActivityType.rejected.value,
    ActivityType.contacted.value,
    ActivityType.replied.value,
    ActivityType.meeting_scheduled.value,
    ActivityType.meeting_done.value,
    ActivityType.status_change.value,
}


# Statuts « en attente de réponse » → susceptibles de relance.
OFFER_WAITING_STATUSES: set[str] = {
    OfferStatus.postule.value,
    OfferStatus.relance.value,
    OfferStatus.entretien.value,
}
CONTACT_WAITING_STATUSES: set[str] = {
    ContactStatus.contacte.value,
    ContactStatus.relance.value,
}


# ─── Documents (bibliothèque CV / LM réutilisables) ───────
class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    doc_type: Mapped[str] = mapped_column(String(10), nullable=False)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(300), nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


# ─── Offers (offres en ligne) ─────────────────────────────
class Offer(Base):
    __tablename__ = "offers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    company: Mapped[str] = mapped_column(String(200), nullable=False)
    location: Mapped[str | None] = mapped_column(String(200), nullable=True)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str | None] = mapped_column(String(120), nullable=True)

    priority: Mapped[str] = mapped_column(
        String(20), nullable=False, default=OfferPriority.moyenne.value
    )
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default=OfferStatus.a_postuler.value
    )

    date_added: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)
    date_applied: Mapped[date | None] = mapped_column(Date, nullable=True)
    deadline: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Documents liés (bibliothèque) — FK SET NULL à la suppression du document.
    cv_document_id: Mapped[int | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
    )
    lm_document_id: Mapped[int | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
    )

    # Pilotage de la relance.
    last_action_date: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)
    next_relance_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    no_relance: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    contacts: Mapped[list["Contact"]] = relationship(
        back_populates="offer", passive_deletes=True
    )


# ─── Contacts (personnes contactées) ──────────────────────
class Contact(Base):
    __tablename__ = "contacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[str | None] = mapped_column(String(200), nullable=True)
    company: Mapped[str | None] = mapped_column(String(200), nullable=True)
    email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    linkedin_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)

    offer_id: Mapped[int | None] = mapped_column(
        ForeignKey("offers.id", ondelete="SET NULL"), nullable=True
    )

    # Documents liés (bibliothèque) — FK SET NULL à la suppression du document.
    cv_document_id: Mapped[int | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
    )
    lm_document_id: Mapped[int | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
    )

    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default=ContactStatus.a_contacter.value
    )

    date_first_contact: Mapped[date | None] = mapped_column(Date, nullable=True)
    last_action_date: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)
    next_relance_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    no_relance: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    offer: Mapped["Offer | None"] = relationship(back_populates="contacts")


# ─── Interview stories (Story Bank STAR) ──────────────────
class InterviewStory(Base):
    __tablename__ = "interview_stories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    situation: Mapped[str] = mapped_column(Text, nullable=False)
    task: Mapped[str] = mapped_column(Text, nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    result: Mapped[str] = mapped_column(Text, nullable=False)
    # Champs optionnels conservés de la v1 (sans aucune intégration IA).
    source: Mapped[str | None] = mapped_column(String(200), nullable=True)
    reflection: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


# ─── Activities (timeline append-only, offres ET contacts) ─
class Activity(Base):
    __tablename__ = "activities"
    __table_args__ = (
        # Exactement un parent : soit une offre, soit un contact (jamais les deux,
        # jamais aucun). Formulation portable Postgres / SQLite.
        CheckConstraint(
            "(offer_id IS NOT NULL AND contact_id IS NULL) "
            "OR (offer_id IS NULL AND contact_id IS NOT NULL)",
            name="ck_activities_exactly_one_parent",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    offer_id: Mapped[int | None] = mapped_column(
        ForeignKey("offers.id", ondelete="CASCADE"), nullable=True, index=True
    )
    contact_id: Mapped[int | None] = mapped_column(
        ForeignKey("contacts.id", ondelete="CASCADE"), nullable=True, index=True
    )

    activity_type: Mapped[str] = mapped_column(String(30), nullable=False)
    event_date: Mapped[date] = mapped_column(Date, nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Document (CV/LM) associé à l'événement — SET NULL si le document est supprimé.
    document_id: Mapped[int | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


# ─── Interviews (rounds d'entretien sous une offre) ───────
# Table de liaison M2M entre interviews et la Story Bank (interview_stories).
# ⚠️ NE PAS confondre avec `interview_stories` (la Story Bank STAR elle-même) :
# ceci n'est QUE la table de liaison.
interview_stories_link = Table(
    "interview_stories_link",
    Base.metadata,
    Column(
        "interview_id",
        Integer,
        ForeignKey("interviews.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "story_id",
        Integer,
        ForeignKey("interview_stories.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class Interview(Base):
    __tablename__ = "interviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    offer_id: Mapped[int] = mapped_column(
        ForeignKey("offers.id", ondelete="CASCADE"), nullable=False, index=True
    )

    round_label: Mapped[str] = mapped_column(String(120), nullable=False)
    scheduled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    interviewer: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # Enum applicatif (visio / onsite / phone) stocké en String (convention projet).
    format: Mapped[str | None] = mapped_column(String(20), nullable=True)

    questions: Mapped[str | None] = mapped_column(Text, nullable=True)
    feeling: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_step: Mapped[str | None] = mapped_column(Text, nullable=True)

    outcome: Mapped[str] = mapped_column(
        String(20), nullable=False, default=InterviewOutcome.pending.value
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Stories STAR rattachées (Story Bank existante, non modifiée). Chargement
    # eager (selectin) pour exposer les stories liées dans InterviewOut en async.
    stories: Mapped[list["InterviewStory"]] = relationship(
        secondary=interview_stories_link,
        lazy="selectin",
        passive_deletes=True,
    )


# ─── Settings (singleton, utilisateur unique) ─────────────
class AppSettings(Base):
    __tablename__ = "settings"

    user_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    relance_delay_days: Mapped[int] = mapped_column(Integer, nullable=False, default=10)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
