from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from app.models.models import (
    ActivityType,
    ContactStatus,
    DocType,
    InterviewFormat,
    InterviewOutcome,
    OfferPriority,
    OfferStatus,
)


# ─── Documents (bibliothèque CV / LM) ─────────────────────
class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    doc_type: DocType
    label: str
    original_filename: str
    file_size: int
    created_at: datetime


class DocumentBrief(BaseModel):
    """Infos document exposées sur les fiches offre / contact (affichage direct)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    doc_type: DocType
    label: str
    original_filename: str


class DocumentRename(BaseModel):
    label: str


class DocumentDeleteResult(BaseModel):
    affected: int  # nombre de fiches (offres + contacts) qui ont perdu le lien


# ─── Offers ───────────────────────────────────────────────
class OfferBase(BaseModel):
    title: str
    company: str
    location: str | None = None
    url: str | None = None
    source: str | None = None
    priority: OfferPriority = OfferPriority.moyenne
    status: OfferStatus = OfferStatus.a_postuler
    date_applied: date | None = None
    deadline: date | None = None
    next_relance_date: date | None = None
    no_relance: bool = False
    notes: str | None = None
    cv_document_id: int | None = None
    lm_document_id: int | None = None


class OfferCreate(OfferBase):
    date_added: date | None = None


class OfferUpdate(BaseModel):
    title: str | None = None
    company: str | None = None
    location: str | None = None
    url: str | None = None
    source: str | None = None
    priority: OfferPriority | None = None
    status: OfferStatus | None = None
    date_applied: date | None = None
    deadline: date | None = None
    next_relance_date: date | None = None
    no_relance: bool | None = None
    notes: str | None = None
    cv_document_id: int | None = None
    lm_document_id: int | None = None


class OfferOut(OfferBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    date_added: date
    last_action_date: date
    created_at: datetime
    updated_at: datetime
    needs_relance: bool = False
    days_overdue: int | None = None
    cv_document: DocumentBrief | None = None
    lm_document: DocumentBrief | None = None


# ─── Contacts ─────────────────────────────────────────────
class ContactBase(BaseModel):
    name: str
    role: str | None = None
    company: str | None = None
    email: str | None = None
    linkedin_url: str | None = None
    phone: str | None = None
    offer_id: int | None = None
    status: ContactStatus = ContactStatus.a_contacter
    date_first_contact: date | None = None
    next_relance_date: date | None = None
    no_relance: bool = False
    notes: str | None = None
    cv_document_id: int | None = None
    lm_document_id: int | None = None


class ContactCreate(ContactBase):
    pass


class ContactUpdate(BaseModel):
    name: str | None = None
    role: str | None = None
    company: str | None = None
    email: str | None = None
    linkedin_url: str | None = None
    phone: str | None = None
    offer_id: int | None = None
    status: ContactStatus | None = None
    date_first_contact: date | None = None
    next_relance_date: date | None = None
    no_relance: bool | None = None
    notes: str | None = None
    cv_document_id: int | None = None
    lm_document_id: int | None = None


class ContactOut(ContactBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    last_action_date: date
    created_at: datetime
    updated_at: datetime
    needs_relance: bool = False
    days_overdue: int | None = None
    cv_document: DocumentBrief | None = None
    lm_document: DocumentBrief | None = None


# ─── Activities (timeline) ────────────────────────────────
class ActivityBase(BaseModel):
    activity_type: ActivityType
    event_date: date
    note: str | None = None
    document_id: int | None = None


class ActivityCreate(ActivityBase):
    pass


class ActivityOut(ActivityBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    offer_id: int | None = None
    contact_id: int | None = None
    created_at: datetime
    document: DocumentBrief | None = None


# ─── Interview stories ────────────────────────────────────
class StoryBase(BaseModel):
    title: str
    situation: str
    task: str
    action: str
    result: str
    source: str | None = None
    reflection: str | None = None
    tags: list[str] = []


class StoryCreate(StoryBase):
    pass


class StoryUpdate(BaseModel):
    title: str | None = None
    situation: str | None = None
    task: str | None = None
    action: str | None = None
    result: str | None = None
    source: str | None = None
    reflection: str | None = None
    tags: list[str] | None = None


class StoryOut(StoryBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class StoryBrief(BaseModel):
    """Story STAR exposée en résumé sur une fiche entretien (id + titre)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str


# ─── Interviews (rounds d'entretien sous une offre) ───────
class InterviewBase(BaseModel):
    round_label: str
    scheduled_at: datetime | None = None
    interviewer: str | None = None
    format: InterviewFormat | None = None
    questions: str | None = None
    feeling: str | None = None
    next_step: str | None = None
    outcome: InterviewOutcome = InterviewOutcome.pending


class InterviewCreate(InterviewBase):
    pass


class InterviewUpdate(BaseModel):
    round_label: str | None = None
    scheduled_at: datetime | None = None
    interviewer: str | None = None
    format: InterviewFormat | None = None
    questions: str | None = None
    feeling: str | None = None
    next_step: str | None = None
    outcome: InterviewOutcome | None = None


class InterviewOut(InterviewBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    offer_id: int
    created_at: datetime
    updated_at: datetime
    stories: list[StoryBrief] = []


# ─── Settings ─────────────────────────────────────────────
class SettingsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    relance_delay_days: int


class SettingsUpdate(BaseModel):
    relance_delay_days: int | None = None


# ─── Relances / Dashboard ─────────────────────────────────
class RelanceItem(BaseModel):
    """Élément à relancer (offre ou contact), enrichi du retard."""

    kind: str  # "offer" | "contact"
    id: int
    title: str  # titre offre ou nom contact
    company: str | None = None
    status: str
    days_overdue: int
    due_date: date


class DeadlineItem(BaseModel):
    id: int
    title: str
    company: str
    deadline: date
    days_left: int


class RelancesOut(BaseModel):
    relances: list[RelanceItem]
    deadlines: list[DeadlineItem]


class DashboardOut(BaseModel):
    offers_by_status: dict[str, int]
    contacts_by_status: dict[str, int]
    offers_total: int
    contacts_total: int
    relances_due: int
    deadlines_soon: int


# ─── Statistiques / funnel (agrégations locales, 0 IA) ────
class FunnelStage(BaseModel):
    key: str
    label: str
    count: int


class FunnelOut(BaseModel):
    stages: list[FunnelStage]


class ResponseRateOut(BaseModel):
    applied_count: int
    responded_count: int
    response_rate: float | None  # None si aucun dénominateur (pas de candidature)
    avg_time_to_response_days: float | None


class CvStatItem(BaseModel):
    document_id: int
    label: str
    applied_count: int  # volume : offres postulées avec ce CV
    responded_count: int
    response_rate: float | None


class ByCvOut(BaseModel):
    items: list[CvStatItem]


class WeeklyActivityItem(BaseModel):
    week: str  # clé ISO, ex. "2026-W23"
    week_start: date
    applied: int
    relance: int


class WeeklyActivityOut(BaseModel):
    weeks: list[WeeklyActivityItem]


class OutreachOut(BaseModel):
    contacted_count: int
    replied_count: int
    reply_rate: float | None


# ─── Agenda (échéances à venir, lecture seule) ────────────
class AgendaItem(BaseModel):
    kind: str  # relance | deadline | interview
    date: date
    entity_type: str  # offer | contact
    entity_id: int
    label: str
    company: str | None = None
    title: str | None = None  # titre d'offre ou nom de contact
    status: str | None = None
    note: str | None = None
    overdue: bool = False


class AgendaOut(BaseModel):
    days: int
    items: list[AgendaItem]
