from pydantic import BaseModel, EmailStr, Field
from datetime import datetime, date, time
from uuid import UUID


# ══════════════════════════════════════════════════════════
# USER
# ══════════════════════════════════════════════════════════

class UserCreate(BaseModel):
    email: str
    full_name: str
    phone: str | None = None
    linkedin_url: str | None = None


class UserUpdate(BaseModel):
    full_name: str | None = None
    phone: str | None = None
    linkedin_url: str | None = None
    email: str | None = None


class UserResponse(BaseModel):
    id: UUID
    email: str
    full_name: str
    phone: str | None
    linkedin_url: str | None
    is_active_search: bool = True
    created_at: datetime

    class Config:
        from_attributes = True


class SearchStatusUpdate(BaseModel):
    is_active: bool


# ══════════════════════════════════════════════════════════
# PRÉFÉRENCES DE RECHERCHE
# ══════════════════════════════════════════════════════════

class SearchPreferenceUpdate(BaseModel):
    target_domains: list[str] | None = None
    target_companies: list[str] | None = None
    target_locations: list[str] | None = None
    contract_types: list[str] | None = None
    min_duration_months: int | None = None
    max_duration_months: int | None = None
    start_date_earliest: date | None = None
    start_date_latest: date | None = None
    min_salary: int | None = None
    keywords: list[str] | None = None
    excluded_keywords: list[str] | None = None
    newsletter_enabled: bool | None = None
    newsletter_time: time | None = None
    min_match_score: int | None = Field(None, ge=0, le=100)
    scoring_weights: dict[str, int] | None = None


class SearchPreferenceResponse(BaseModel):
    id: UUID
    target_domains: list[str]
    target_companies: list[str]
    target_locations: list[str]
    contract_types: list[str]
    min_duration_months: int | None
    max_duration_months: int | None
    start_date_earliest: date | None
    start_date_latest: date | None
    min_salary: int | None
    keywords: list[str]
    excluded_keywords: list[str]
    newsletter_enabled: bool
    newsletter_time: time
    min_match_score: int
    scoring_weights: dict[str, int] | None = None
    updated_at: datetime

    class Config:
        from_attributes = True


# ══════════════════════════════════════════════════════════
# DOCUMENTS
# ══════════════════════════════════════════════════════════

class DocumentResponse(BaseModel):
    id: UUID
    doc_type: str
    title: str
    is_primary: bool
    extracted_text: str | None = None
    file_path: str | None = None
    uploaded_at: datetime

    class Config:
        from_attributes = True


# ══════════════════════════════════════════════════════════
# OFFRES
# ══════════════════════════════════════════════════════════

class OfferResponse(BaseModel):
    id: UUID
    title: str
    company_name: str
    company_logo_url: str | None
    location: str | None
    is_remote: bool
    domain: str | None
    contract_type: str | None
    duration_months: int | None
    start_date: date | None
    salary: str | None
    source_platform: str
    source_url: str | None
    description: str | None
    required_skills: list[str]
    contact_email: str | None
    created_at: datetime

    class Config:
        from_attributes = True


class OfferMatchResponse(BaseModel):
    id: UUID
    offer: OfferResponse
    match_score: int
    match_reasons: dict
    ai_summary: str | None
    user_interest: str
    created_at: datetime

    class Config:
        from_attributes = True


# ══════════════════════════════════════════════════════════
# CANDIDATURES
# ══════════════════════════════════════════════════════════

class ApplicationCreate(BaseModel):
    offer_id: UUID


class ApplicationUpdate(BaseModel):
    status: str | None = None
    notes: str | None = None
    recipient_email: str | None = None
    applied_via: str | None = None


class ApplicationResponse(BaseModel):
    id: UUID
    offer: OfferResponse
    status: str
    cover_letter_text: str | None
    email_draft: str | None
    applied_via: str | None
    applied_at: datetime | None
    recipient_email: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ══════════════════════════════════════════════════════════
# ENTRETIENS
# ══════════════════════════════════════════════════════════

class InterviewCreate(BaseModel):
    application_id: UUID
    interview_type: str | None = None
    scheduled_at: datetime | None = None
    duration_minutes: int = 60
    location: str | None = None
    interviewer_name: str | None = None
    interviewer_role: str | None = None


class InterviewResponse(BaseModel):
    id: UUID
    interview_type: str | None
    scheduled_at: datetime | None
    duration_minutes: int
    location: str | None
    interviewer_name: str | None
    interviewer_role: str | None
    prep_notes: str | None
    company_research: str | None
    common_questions: str | None
    feedback: str | None
    rating: int | None
    created_at: datetime

    class Config:
        from_attributes = True


# ══════════════════════════════════════════════════════════
# DASHBOARD STATS
# ══════════════════════════════════════════════════════════

class DashboardStats(BaseModel):
    total_offers_matched: int
    new_today: int
    applications_sent: int
    interviews_scheduled: int
    pending_follow_ups: int
    pipeline: dict[str, int]  # {"draft": 3, "sent": 5, "interview": 2, ...}


# ══════════════════════════════════════════════════════════
# STORY BANK (STAR)
# ══════════════════════════════════════════════════════════

class StoryCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    situation: str = Field(..., min_length=1)
    task: str = Field(..., min_length=1)
    action: str = Field(..., min_length=1)
    result: str = Field(..., min_length=1)
    reflection: str | None = None
    tags: list[str] = Field(default_factory=list)
    source: str | None = None


class StoryUpdate(BaseModel):
    title: str | None = None
    situation: str | None = None
    task: str | None = None
    action: str | None = None
    result: str | None = None
    reflection: str | None = None
    tags: list[str] | None = None
    source: str | None = None
    used_in_interviews: list[str] | None = None


class StoryResponse(BaseModel):
    id: UUID
    user_id: UUID
    title: str
    situation: str
    task: str
    action: str
    result: str
    reflection: str | None
    tags: list[str]
    source: str | None
    used_in_interviews: list[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
