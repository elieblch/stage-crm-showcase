"""Endpoints REST — tracker manuel de recherche de stage.

Tout est async. Mode mono-utilisateur (pas d'auth). Aucun appel réseau payant,
aucun scraping, aucune IA : la saisie des offres et contacts est 100 % manuelle.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.models.models import (
    ACTION_ACTIVITY_TYPES,
    Activity,
    ActivityType,
    AppSettings,
    Contact,
    ContactStatus,
    Document,
    DocType,
    Interview,
    InterviewOutcome,
    InterviewStory,
    Offer,
    OfferPriority,
    OfferStatus,
)
from app.schemas.schemas import (
    ActivityCreate,
    ActivityOut,
    ContactCreate,
    ContactOut,
    ContactUpdate,
    DashboardOut,
    DeadlineItem,
    DocumentBrief,
    DocumentDeleteResult,
    DocumentOut,
    DocumentRename,
    InterviewCreate,
    InterviewOut,
    InterviewUpdate,
    OfferCreate,
    OfferOut,
    OfferUpdate,
    RelanceItem,
    RelancesOut,
    SettingsOut,
    SettingsUpdate,
    StoryCreate,
    StoryOut,
    StoryUpdate,
)
from app.services.relance_service import (
    CONTACT,
    OFFER,
    deadline_is_soon,
    evaluate,
)

router = APIRouter()
settings = get_settings()


# ─── Helpers ──────────────────────────────────────────────
async def _get_settings_row(db: AsyncSession) -> AppSettings:
    row = await db.get(AppSettings, settings.single_user_id)
    if row is None:
        row = AppSettings(user_id=settings.single_user_id, relance_delay_days=10)
        db.add(row)
        await db.flush()
    return row


async def _doc_brief(db: AsyncSession, doc_id: int | None) -> DocumentBrief | None:
    if doc_id is None:
        return None
    doc = await db.get(Document, doc_id)
    return DocumentBrief.model_validate(doc) if doc is not None else None


async def _enrich_offer(offer: Offer, delay: int, today: date, db: AsyncSession) -> OfferOut:
    ev = evaluate(
        kind=OFFER,
        no_relance=offer.no_relance,
        status=offer.status,
        last_action_date=offer.last_action_date,
        next_relance_date=offer.next_relance_date,
        relance_delay_days=delay,
        today=today,
    )
    out = OfferOut.model_validate(offer)
    out.needs_relance = ev.needs_relance
    out.days_overdue = ev.days_overdue if ev.needs_relance else None
    out.cv_document = await _doc_brief(db, offer.cv_document_id)
    out.lm_document = await _doc_brief(db, offer.lm_document_id)
    return out


async def _enrich_contact(contact: Contact, delay: int, today: date, db: AsyncSession) -> ContactOut:
    ev = evaluate(
        kind=CONTACT,
        no_relance=contact.no_relance,
        status=contact.status,
        last_action_date=contact.last_action_date,
        next_relance_date=contact.next_relance_date,
        relance_delay_days=delay,
        today=today,
    )
    out = ContactOut.model_validate(contact)
    out.needs_relance = ev.needs_relance
    out.days_overdue = ev.days_overdue if ev.needs_relance else None
    out.cv_document = await _doc_brief(db, contact.cv_document_id)
    out.lm_document = await _doc_brief(db, contact.lm_document_id)
    return out


async def _validate_doc_link(db: AsyncSession, doc_id: int | None, expected: DocType) -> None:
    """Vérifie qu'un document lié existe et correspond au bon doc_type (cv / lm)."""
    if doc_id is None:
        return
    doc = await db.get(Document, doc_id)
    if doc is None:
        raise HTTPException(status_code=400, detail="Document inconnu.")
    if doc.doc_type != expected.value:
        raise HTTPException(
            status_code=400,
            detail=f"Le document #{doc_id} n'est pas de type {expected.value}.",
        )


async def _validate_doc_links(db: AsyncSession, data: dict) -> None:
    if "cv_document_id" in data:
        await _validate_doc_link(db, data["cv_document_id"], DocType.cv)
    if "lm_document_id" in data:
        await _validate_doc_link(db, data["lm_document_id"], DocType.lm)


async def _read_pdf_upload(file: UploadFile) -> bytes:
    if file.content_type not in ("application/pdf", "application/x-pdf"):
        raise HTTPException(status_code=400, detail="Le fichier doit être un PDF.")
    data = await file.read()
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail="Fichier trop volumineux (max 10 Mo).")
    if not data.startswith(b"%PDF-"):
        raise HTTPException(status_code=400, detail="Contenu PDF invalide.")
    return data


# ─── Activities (timeline) ────────────────────────────────
async def _activity_out(db: AsyncSession, act: Activity) -> ActivityOut:
    out = ActivityOut.model_validate(act)
    out.document = await _doc_brief(db, act.document_id)
    return out


async def _sync_last_action_date(
    db: AsyncSession, *, offer_id: int | None = None, contact_id: int | None = None
) -> None:
    """Aligne last_action_date de l'entité sur max(event_date) de ses activités « action ».

    `note` / `other` (simples annotations) n'entrent pas dans le calcul afin de
    ne pas perturber la logique de relance pilotée par last_action_date.
    """
    if offer_id is not None:
        entity = await db.get(Offer, offer_id)
        parent_filter = Activity.offer_id == offer_id
    else:
        entity = await db.get(Contact, contact_id)
        parent_filter = Activity.contact_id == contact_id
    if entity is None:
        return
    max_date = (
        await db.execute(
            select(func.max(Activity.event_date)).where(
                parent_filter, Activity.activity_type.in_(ACTION_ACTIVITY_TYPES)
            )
        )
    ).scalar_one_or_none()
    if max_date is not None:
        entity.last_action_date = max_date


async def _add_activity(
    db: AsyncSession,
    *,
    offer_id: int | None = None,
    contact_id: int | None = None,
    activity_type: str,
    event_date: date,
    note: str | None = None,
    document_id: int | None = None,
) -> Activity:
    """Crée un événement de timeline puis resynchronise last_action_date."""
    act = Activity(
        offer_id=offer_id,
        contact_id=contact_id,
        activity_type=activity_type,
        event_date=event_date,
        note=note,
        document_id=document_id,
    )
    db.add(act)
    await db.flush()
    if activity_type in ACTION_ACTIVITY_TYPES:
        await _sync_last_action_date(db, offer_id=offer_id, contact_id=contact_id)
        await db.flush()
    await db.refresh(act)
    return act


async def _validate_activity_document(db: AsyncSession, document_id: int | None) -> None:
    if document_id is not None and await db.get(Document, document_id) is None:
        raise HTTPException(status_code=400, detail="Document inconnu.")


# ══════════════════════════════════════════════════════════
#  OFFERS
# ══════════════════════════════════════════════════════════
@router.get("/offers", response_model=list[OfferOut])
async def list_offers(
    status: OfferStatus | None = None,
    priority: OfferPriority | None = None,
    needs_relance: bool | None = None,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Offer)
    if status is not None:
        stmt = stmt.where(Offer.status == status.value)
    if priority is not None:
        stmt = stmt.where(Offer.priority == priority.value)
    stmt = stmt.order_by(Offer.date_added.desc(), Offer.id.desc())
    offers = (await db.execute(stmt)).scalars().all()

    delay = (await _get_settings_row(db)).relance_delay_days
    today = date.today()
    result = [await _enrich_offer(o, delay, today, db) for o in offers]
    if needs_relance is not None:
        result = [o for o in result if o.needs_relance == needs_relance]
    return result


@router.get("/offers/{offer_id}", response_model=OfferOut)
async def get_offer(offer_id: int, db: AsyncSession = Depends(get_db)):
    offer = await db.get(Offer, offer_id)
    if offer is None:
        raise HTTPException(status_code=404, detail="Offre introuvable.")
    delay = (await _get_settings_row(db)).relance_delay_days
    return await _enrich_offer(offer, delay, date.today(), db)


@router.post("/offers", response_model=OfferOut, status_code=201)
async def create_offer(payload: OfferCreate, db: AsyncSession = Depends(get_db)):
    data = payload.model_dump()
    await _validate_doc_links(db, data)
    date_added = data.pop("date_added", None) or date.today()
    data["priority"] = data["priority"].value
    data["status"] = data["status"].value
    offer = Offer(**data, date_added=date_added, last_action_date=date_added)
    db.add(offer)
    await db.flush()
    await db.refresh(offer)
    delay = (await _get_settings_row(db)).relance_delay_days
    return await _enrich_offer(offer, delay, date.today(), db)


@router.put("/offers/{offer_id}", response_model=OfferOut)
async def update_offer(
    offer_id: int, payload: OfferUpdate, db: AsyncSession = Depends(get_db)
):
    offer = await db.get(Offer, offer_id)
    if offer is None:
        raise HTTPException(status_code=404, detail="Offre introuvable.")
    data = payload.model_dump(exclude_unset=True)
    await _validate_doc_links(db, data)
    status_changed = (
        "status" in data and data["status"] is not None and data["status"].value != offer.status
    )
    for key, value in data.items():
        if value is None and key in ("title", "company", "priority", "status", "no_relance"):
            continue
        if key in ("priority", "status") and value is not None:
            value = value.value
        setattr(offer, key, value)
    # Un changement de statut compte comme une action → réinitialise la relance.
    if status_changed:
        offer.last_action_date = date.today()
        if "next_relance_date" not in data:
            offer.next_relance_date = None
    await db.flush()
    await db.refresh(offer)
    delay = (await _get_settings_row(db)).relance_delay_days
    return await _enrich_offer(offer, delay, date.today(), db)


@router.delete("/offers/{offer_id}", status_code=204)
async def delete_offer(offer_id: int, db: AsyncSession = Depends(get_db)):
    offer = await db.get(Offer, offer_id)
    if offer is None:
        raise HTTPException(status_code=404, detail="Offre introuvable.")
    # Les documents appartiennent à la bibliothèque partagée : on ne les supprime pas.
    await db.delete(offer)
    return None


@router.post("/offers/{offer_id}/mark-relanced", response_model=OfferOut)
async def mark_offer_relanced(offer_id: int, db: AsyncSession = Depends(get_db)):
    offer = await db.get(Offer, offer_id)
    if offer is None:
        raise HTTPException(status_code=404, detail="Offre introuvable.")
    today = date.today()
    # Journalise l'action dans la timeline (met aussi à jour last_action_date).
    await _add_activity(
        db, offer_id=offer_id, activity_type=ActivityType.relance.value, event_date=today
    )
    offer.status = OfferStatus.relance.value
    offer.last_action_date = today
    offer.next_relance_date = None
    await db.flush()
    await db.refresh(offer)
    delay = (await _get_settings_row(db)).relance_delay_days
    return await _enrich_offer(offer, delay, today, db)


@router.get("/offers/{offer_id}/contacts", response_model=list[ContactOut])
async def list_offer_contacts(offer_id: int, db: AsyncSession = Depends(get_db)):
    offer = await db.get(Offer, offer_id)
    if offer is None:
        raise HTTPException(status_code=404, detail="Offre introuvable.")
    stmt = select(Contact).where(Contact.offer_id == offer_id).order_by(Contact.id.desc())
    contacts = (await db.execute(stmt)).scalars().all()
    delay = (await _get_settings_row(db)).relance_delay_days
    today = date.today()
    return [await _enrich_contact(c, delay, today, db) for c in contacts]


# ══════════════════════════════════════════════════════════
#  DOCUMENTS (bibliothèque CV / LM réutilisables)
# ══════════════════════════════════════════════════════════
@router.get("/documents", response_model=list[DocumentOut])
async def list_documents(
    doc_type: DocType | None = None,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Document)
    if doc_type is not None:
        stmt = stmt.where(Document.doc_type == doc_type.value)
    stmt = stmt.order_by(Document.created_at.desc(), Document.id.desc())
    return list((await db.execute(stmt)).scalars().all())


@router.get("/documents/{document_id}", response_model=DocumentOut)
async def get_document(document_id: int, db: AsyncSession = Depends(get_db)):
    doc = await db.get(Document, document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document introuvable.")
    return doc


@router.post("/documents", response_model=DocumentOut, status_code=201)
async def upload_document(
    doc_type: DocType = Form(...),
    label: str = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    label = label.strip()
    if not label:
        raise HTTPException(status_code=400, detail="Le label est obligatoire.")
    data = await _read_pdf_upload(file)
    doc = Document(
        doc_type=doc_type.value,
        label=label,
        original_filename=file.filename or "document.pdf",
        file_path="",  # complété après obtention de l'id
        file_size=len(data),
    )
    db.add(doc)
    await db.flush()  # → doc.id
    dest_dir = Path(settings.upload_dir) / "documents"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{doc.id}.pdf"
    dest.write_bytes(data)
    doc.file_path = str(dest)
    await db.flush()
    await db.refresh(doc)
    return doc


@router.patch("/documents/{document_id}", response_model=DocumentOut)
async def rename_document(
    document_id: int, payload: DocumentRename, db: AsyncSession = Depends(get_db)
):
    doc = await db.get(Document, document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document introuvable.")
    label = payload.label.strip()
    if not label:
        raise HTTPException(status_code=400, detail="Le label est obligatoire.")
    doc.label = label
    await db.flush()
    await db.refresh(doc)
    return doc


@router.get("/documents/{document_id}/download")
async def download_document(document_id: int, db: AsyncSession = Depends(get_db)):
    doc = await db.get(Document, document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document introuvable.")
    if not doc.file_path or not Path(doc.file_path).exists():
        raise HTTPException(status_code=404, detail="Fichier absent.")
    return FileResponse(
        doc.file_path, media_type="application/pdf", filename=doc.original_filename
    )


@router.delete("/documents/{document_id}", response_model=DocumentDeleteResult)
async def delete_document(document_id: int, db: AsyncSession = Depends(get_db)):
    doc = await db.get(Document, document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document introuvable.")

    # Compte des fiches qui perdront le lien (chaque fiche compte une fois).
    affected_offers = (
        await db.execute(
            select(Offer.id).where(
                or_(Offer.cv_document_id == document_id, Offer.lm_document_id == document_id)
            )
        )
    ).scalars().all()
    affected_contacts = (
        await db.execute(
            select(Contact.id).where(
                or_(Contact.cv_document_id == document_id, Contact.lm_document_id == document_id)
            )
        )
    ).scalars().all()
    affected = len(affected_offers) + len(affected_contacts)

    if doc.file_path:
        Path(doc.file_path).unlink(missing_ok=True)
    # Le FK ON DELETE SET NULL nettoie les références côté offers / contacts.
    await db.delete(doc)
    await db.flush()
    return DocumentDeleteResult(affected=affected)


# ══════════════════════════════════════════════════════════
#  CONTACTS
# ══════════════════════════════════════════════════════════
async def _check_offer_exists(offer_id: int | None, db: AsyncSession) -> None:
    if offer_id is not None and await db.get(Offer, offer_id) is None:
        raise HTTPException(status_code=400, detail="offer_id inconnu.")


@router.get("/contacts", response_model=list[ContactOut])
async def list_contacts(
    status: ContactStatus | None = None,
    offer_id: int | None = None,
    needs_relance: bool | None = None,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Contact)
    if status is not None:
        stmt = stmt.where(Contact.status == status.value)
    if offer_id is not None:
        stmt = stmt.where(Contact.offer_id == offer_id)
    stmt = stmt.order_by(Contact.id.desc())
    contacts = (await db.execute(stmt)).scalars().all()
    delay = (await _get_settings_row(db)).relance_delay_days
    today = date.today()
    result = [await _enrich_contact(c, delay, today, db) for c in contacts]
    if needs_relance is not None:
        result = [c for c in result if c.needs_relance == needs_relance]
    return result


@router.get("/contacts/{contact_id}", response_model=ContactOut)
async def get_contact(contact_id: int, db: AsyncSession = Depends(get_db)):
    contact = await db.get(Contact, contact_id)
    if contact is None:
        raise HTTPException(status_code=404, detail="Contact introuvable.")
    delay = (await _get_settings_row(db)).relance_delay_days
    return await _enrich_contact(contact, delay, date.today(), db)


@router.post("/contacts", response_model=ContactOut, status_code=201)
async def create_contact(payload: ContactCreate, db: AsyncSession = Depends(get_db)):
    await _check_offer_exists(payload.offer_id, db)
    data = payload.model_dump()
    await _validate_doc_links(db, data)
    data["status"] = data["status"].value
    contact = Contact(**data, last_action_date=date.today())
    db.add(contact)
    await db.flush()
    await db.refresh(contact)
    delay = (await _get_settings_row(db)).relance_delay_days
    return await _enrich_contact(contact, delay, date.today(), db)


@router.put("/contacts/{contact_id}", response_model=ContactOut)
async def update_contact(
    contact_id: int, payload: ContactUpdate, db: AsyncSession = Depends(get_db)
):
    contact = await db.get(Contact, contact_id)
    if contact is None:
        raise HTTPException(status_code=404, detail="Contact introuvable.")
    data = payload.model_dump(exclude_unset=True)
    if "offer_id" in data:
        await _check_offer_exists(data["offer_id"], db)
    await _validate_doc_links(db, data)
    status_changed = (
        "status" in data and data["status"] is not None and data["status"].value != contact.status
    )
    for key, value in data.items():
        if value is None and key in ("name", "status", "no_relance"):
            continue
        if key == "status" and value is not None:
            value = value.value
        setattr(contact, key, value)
    if status_changed:
        contact.last_action_date = date.today()
        if "next_relance_date" not in data:
            contact.next_relance_date = None
    await db.flush()
    await db.refresh(contact)
    delay = (await _get_settings_row(db)).relance_delay_days
    return await _enrich_contact(contact, delay, date.today(), db)


@router.delete("/contacts/{contact_id}", status_code=204)
async def delete_contact(contact_id: int, db: AsyncSession = Depends(get_db)):
    contact = await db.get(Contact, contact_id)
    if contact is None:
        raise HTTPException(status_code=404, detail="Contact introuvable.")
    await db.delete(contact)
    return None


@router.post("/contacts/{contact_id}/mark-relanced", response_model=ContactOut)
async def mark_contact_relanced(contact_id: int, db: AsyncSession = Depends(get_db)):
    contact = await db.get(Contact, contact_id)
    if contact is None:
        raise HTTPException(status_code=404, detail="Contact introuvable.")
    today = date.today()
    # Journalise l'action dans la timeline (met aussi à jour last_action_date).
    await _add_activity(
        db, contact_id=contact_id, activity_type=ActivityType.relance.value, event_date=today
    )
    contact.status = ContactStatus.relance.value
    contact.last_action_date = today
    contact.next_relance_date = None
    await db.flush()
    await db.refresh(contact)
    delay = (await _get_settings_row(db)).relance_delay_days
    return await _enrich_contact(contact, delay, today, db)


# ══════════════════════════════════════════════════════════
#  ACTIVITIES (timeline append-only, par offre ou par contact)
# ══════════════════════════════════════════════════════════
@router.get("/offers/{offer_id}/activities", response_model=list[ActivityOut])
async def list_offer_activities(offer_id: int, db: AsyncSession = Depends(get_db)):
    if await db.get(Offer, offer_id) is None:
        raise HTTPException(status_code=404, detail="Offre introuvable.")
    stmt = (
        select(Activity)
        .where(Activity.offer_id == offer_id)
        .order_by(Activity.event_date.desc(), Activity.id.desc())
    )
    acts = (await db.execute(stmt)).scalars().all()
    return [await _activity_out(db, a) for a in acts]


@router.post("/offers/{offer_id}/activities", response_model=ActivityOut, status_code=201)
async def create_offer_activity(
    offer_id: int, payload: ActivityCreate, db: AsyncSession = Depends(get_db)
):
    if await db.get(Offer, offer_id) is None:
        raise HTTPException(status_code=404, detail="Offre introuvable.")
    await _validate_activity_document(db, payload.document_id)
    act = await _add_activity(
        db,
        offer_id=offer_id,
        activity_type=payload.activity_type.value,
        event_date=payload.event_date,
        note=payload.note,
        document_id=payload.document_id,
    )
    return await _activity_out(db, act)


@router.get("/contacts/{contact_id}/activities", response_model=list[ActivityOut])
async def list_contact_activities(contact_id: int, db: AsyncSession = Depends(get_db)):
    if await db.get(Contact, contact_id) is None:
        raise HTTPException(status_code=404, detail="Contact introuvable.")
    stmt = (
        select(Activity)
        .where(Activity.contact_id == contact_id)
        .order_by(Activity.event_date.desc(), Activity.id.desc())
    )
    acts = (await db.execute(stmt)).scalars().all()
    return [await _activity_out(db, a) for a in acts]


@router.post("/contacts/{contact_id}/activities", response_model=ActivityOut, status_code=201)
async def create_contact_activity(
    contact_id: int, payload: ActivityCreate, db: AsyncSession = Depends(get_db)
):
    if await db.get(Contact, contact_id) is None:
        raise HTTPException(status_code=404, detail="Contact introuvable.")
    await _validate_activity_document(db, payload.document_id)
    act = await _add_activity(
        db,
        contact_id=contact_id,
        activity_type=payload.activity_type.value,
        event_date=payload.event_date,
        note=payload.note,
        document_id=payload.document_id,
    )
    return await _activity_out(db, act)


@router.delete("/activities/{activity_id}", status_code=204)
async def delete_activity(activity_id: int, db: AsyncSession = Depends(get_db)):
    act = await db.get(Activity, activity_id)
    if act is None:
        raise HTTPException(status_code=404, detail="Événement introuvable.")
    await db.delete(act)
    return None


# ══════════════════════════════════════════════════════════
#  INTERVIEW STORIES
# ══════════════════════════════════════════════════════════
@router.get("/stories", response_model=list[StoryOut])
async def list_stories(
    tags: list[str] | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(InterviewStory).order_by(InterviewStory.updated_at.desc())
    stories = (await db.execute(stmt)).scalars().all()
    if tags:
        wanted = set(tags)
        stories = [s for s in stories if wanted.issubset(set(s.tags or []))]
    return list(stories)


@router.get("/stories/{story_id}", response_model=StoryOut)
async def get_story(story_id: int, db: AsyncSession = Depends(get_db)):
    story = await db.get(InterviewStory, story_id)
    if story is None:
        raise HTTPException(status_code=404, detail="Story introuvable.")
    return story


@router.post("/stories", response_model=StoryOut, status_code=201)
async def create_story(payload: StoryCreate, db: AsyncSession = Depends(get_db)):
    story = InterviewStory(**payload.model_dump())
    db.add(story)
    await db.flush()
    await db.refresh(story)
    return story


@router.put("/stories/{story_id}", response_model=StoryOut)
async def update_story(
    story_id: int, payload: StoryUpdate, db: AsyncSession = Depends(get_db)
):
    story = await db.get(InterviewStory, story_id)
    if story is None:
        raise HTTPException(status_code=404, detail="Story introuvable.")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(story, key, value)
    await db.flush()
    await db.refresh(story)
    return story


@router.delete("/stories/{story_id}", status_code=204)
async def delete_story(story_id: int, db: AsyncSession = Depends(get_db)):
    story = await db.get(InterviewStory, story_id)
    if story is None:
        raise HTTPException(status_code=404, detail="Story introuvable.")
    await db.delete(story)
    return None


# ══════════════════════════════════════════════════════════
#  INTERVIEWS (rounds d'entretien sous une offre)
# ══════════════════════════════════════════════════════════
_FINAL_OUTCOMES = {InterviewOutcome.passed.value, InterviewOutcome.rejected.value}


async def _get_interview_or_404(db: AsyncSession, interview_id: int) -> Interview:
    interview = await db.get(Interview, interview_id)
    if interview is None:
        raise HTTPException(status_code=404, detail="Entretien introuvable.")
    return interview


async def _log_interview_scheduled(db: AsyncSession, interview: Interview) -> None:
    """Journalise un événement `interview_scheduled` sur l'offre de l'entretien."""
    await _add_activity(
        db,
        offer_id=interview.offer_id,
        activity_type=ActivityType.interview_scheduled.value,
        event_date=interview.scheduled_at.date(),
        note=f"Entretien « {interview.round_label} » planifié",
    )


async def _log_interview_done(db: AsyncSession, interview: Interview) -> None:
    """Journalise un événement `interview_done` sur l'offre de l'entretien."""
    event_date = interview.scheduled_at.date() if interview.scheduled_at else date.today()
    await _add_activity(
        db,
        offer_id=interview.offer_id,
        activity_type=ActivityType.interview_done.value,
        event_date=event_date,
        note=f"Entretien « {interview.round_label} » — {interview.outcome}",
    )


@router.get("/offers/{offer_id}/interviews", response_model=list[InterviewOut])
async def list_offer_interviews(offer_id: int, db: AsyncSession = Depends(get_db)):
    if await db.get(Offer, offer_id) is None:
        raise HTTPException(status_code=404, detail="Offre introuvable.")
    stmt = (
        select(Interview)
        .where(Interview.offer_id == offer_id)
        .order_by(Interview.scheduled_at.desc().nullslast(), Interview.id.desc())
    )
    return list((await db.execute(stmt)).scalars().all())


@router.post("/offers/{offer_id}/interviews", response_model=InterviewOut, status_code=201)
async def create_offer_interview(
    offer_id: int, payload: InterviewCreate, db: AsyncSession = Depends(get_db)
):
    if await db.get(Offer, offer_id) is None:
        raise HTTPException(status_code=404, detail="Offre introuvable.")
    data = payload.model_dump()
    if data.get("format") is not None:
        data["format"] = data["format"].value
    data["outcome"] = data["outcome"].value
    interview = Interview(offer_id=offer_id, **data)
    db.add(interview)
    await db.flush()

    # Cohésion timeline : un entretien planifié / déjà conclu journalise l'offre.
    if interview.scheduled_at is not None:
        await _log_interview_scheduled(db, interview)
    if interview.outcome in _FINAL_OUTCOMES:
        await _log_interview_done(db, interview)

    await db.refresh(interview)
    return interview


@router.get("/interviews/{interview_id}", response_model=InterviewOut)
async def get_interview(interview_id: int, db: AsyncSession = Depends(get_db)):
    return await _get_interview_or_404(db, interview_id)


@router.patch("/interviews/{interview_id}", response_model=InterviewOut)
async def update_interview(
    interview_id: int, payload: InterviewUpdate, db: AsyncSession = Depends(get_db)
):
    interview = await _get_interview_or_404(db, interview_id)
    data = payload.model_dump(exclude_unset=True)

    prev_scheduled_at = interview.scheduled_at
    prev_outcome = interview.outcome

    for key, value in data.items():
        # Champs requis : ne jamais les écraser avec None.
        if value is None and key in ("round_label", "outcome"):
            continue
        if key in ("format", "outcome") and value is not None:
            value = value.value
        setattr(interview, key, value)
    await db.flush()

    # Cohésion timeline (transitions uniquement → pas de doublon).
    newly_scheduled = prev_scheduled_at is None and interview.scheduled_at is not None
    if newly_scheduled:
        await _log_interview_scheduled(db, interview)
    became_final = (
        prev_outcome not in _FINAL_OUTCOMES and interview.outcome in _FINAL_OUTCOMES
    )
    if became_final:
        await _log_interview_done(db, interview)

    await db.refresh(interview)
    return interview


@router.delete("/interviews/{interview_id}", status_code=204)
async def delete_interview(interview_id: int, db: AsyncSession = Depends(get_db)):
    interview = await db.get(Interview, interview_id)
    if interview is None:
        raise HTTPException(status_code=404, detail="Entretien introuvable.")
    # Les liens vers les stories partent en CASCADE ; les stories sont conservées.
    await db.delete(interview)
    return None


@router.post("/interviews/{interview_id}/stories/{story_id}", response_model=InterviewOut)
async def attach_story_to_interview(
    interview_id: int, story_id: int, db: AsyncSession = Depends(get_db)
):
    interview = await _get_interview_or_404(db, interview_id)
    story = await db.get(InterviewStory, story_id)
    if story is None:
        raise HTTPException(status_code=404, detail="Story introuvable.")
    if all(s.id != story_id for s in interview.stories):
        interview.stories.append(story)
        await db.flush()
    await db.refresh(interview)
    return interview


@router.delete("/interviews/{interview_id}/stories/{story_id}", response_model=InterviewOut)
async def detach_story_from_interview(
    interview_id: int, story_id: int, db: AsyncSession = Depends(get_db)
):
    interview = await _get_interview_or_404(db, interview_id)
    interview.stories = [s for s in interview.stories if s.id != story_id]
    await db.flush()
    await db.refresh(interview)
    return interview


# ══════════════════════════════════════════════════════════
#  SETTINGS
# ══════════════════════════════════════════════════════════
@router.get("/settings", response_model=SettingsOut)
async def get_app_settings(db: AsyncSession = Depends(get_db)):
    return await _get_settings_row(db)


@router.put("/settings", response_model=SettingsOut)
async def update_app_settings(payload: SettingsUpdate, db: AsyncSession = Depends(get_db)):
    row = await _get_settings_row(db)
    if payload.relance_delay_days is not None:
        if payload.relance_delay_days < 0:
            raise HTTPException(status_code=400, detail="Le délai doit être positif.")
        row.relance_delay_days = payload.relance_delay_days
    await db.flush()
    await db.refresh(row)
    return row


# ══════════════════════════════════════════════════════════
#  RELANCES (calcul à la volée, pas de scheduler)
# ══════════════════════════════════════════════════════════
@router.get("/relances", response_model=RelancesOut)
async def get_relances(db: AsyncSession = Depends(get_db)):
    delay = (await _get_settings_row(db)).relance_delay_days
    today = date.today()

    offers = (await db.execute(select(Offer))).scalars().all()
    contacts = (await db.execute(select(Contact))).scalars().all()

    relances: list[RelanceItem] = []
    deadlines: list[DeadlineItem] = []

    for o in offers:
        ev = evaluate(
            kind=OFFER,
            no_relance=o.no_relance,
            status=o.status,
            last_action_date=o.last_action_date,
            next_relance_date=o.next_relance_date,
            relance_delay_days=delay,
            today=today,
        )
        if ev.needs_relance:
            relances.append(
                RelanceItem(
                    kind=OFFER,
                    id=o.id,
                    title=o.title,
                    company=o.company,
                    status=o.status,
                    days_overdue=ev.days_overdue,
                    due_date=ev.due_date,
                )
            )
        if deadline_is_soon(status=o.status, deadline=o.deadline, today=today):
            deadlines.append(
                DeadlineItem(
                    id=o.id,
                    title=o.title,
                    company=o.company,
                    deadline=o.deadline,
                    days_left=(o.deadline - today).days,
                )
            )

    for c in contacts:
        ev = evaluate(
            kind=CONTACT,
            no_relance=c.no_relance,
            status=c.status,
            last_action_date=c.last_action_date,
            next_relance_date=c.next_relance_date,
            relance_delay_days=delay,
            today=today,
        )
        if ev.needs_relance:
            relances.append(
                RelanceItem(
                    kind=CONTACT,
                    id=c.id,
                    title=c.name,
                    company=c.company,
                    status=c.status,
                    days_overdue=ev.days_overdue,
                    due_date=ev.due_date,
                )
            )

    # Tri par urgence décroissante (plus de retard = plus urgent).
    relances.sort(key=lambda r: r.days_overdue, reverse=True)
    deadlines.sort(key=lambda d: d.days_left)
    return RelancesOut(relances=relances, deadlines=deadlines)


# ══════════════════════════════════════════════════════════
#  DASHBOARD
# ══════════════════════════════════════════════════════════
@router.get("/dashboard", response_model=DashboardOut)
async def get_dashboard(db: AsyncSession = Depends(get_db)):
    delay = (await _get_settings_row(db)).relance_delay_days
    today = date.today()

    offers = (await db.execute(select(Offer))).scalars().all()
    contacts = (await db.execute(select(Contact))).scalars().all()

    offers_by_status: dict[str, int] = {s.value: 0 for s in OfferStatus}
    contacts_by_status: dict[str, int] = {s.value: 0 for s in ContactStatus}
    relances_due = 0
    deadlines_soon = 0

    for o in offers:
        offers_by_status[o.status] = offers_by_status.get(o.status, 0) + 1
        ev = evaluate(
            kind=OFFER,
            no_relance=o.no_relance,
            status=o.status,
            last_action_date=o.last_action_date,
            next_relance_date=o.next_relance_date,
            relance_delay_days=delay,
            today=today,
        )
        if ev.needs_relance:
            relances_due += 1
        if deadline_is_soon(status=o.status, deadline=o.deadline, today=today):
            deadlines_soon += 1

    for c in contacts:
        contacts_by_status[c.status] = contacts_by_status.get(c.status, 0) + 1
        ev = evaluate(
            kind=CONTACT,
            no_relance=c.no_relance,
            status=c.status,
            last_action_date=c.last_action_date,
            next_relance_date=c.next_relance_date,
            relance_delay_days=delay,
            today=today,
        )
        if ev.needs_relance:
            relances_due += 1

    return DashboardOut(
        offers_by_status=offers_by_status,
        contacts_by_status=contacts_by_status,
        offers_total=len(offers),
        contacts_total=len(contacts),
        relances_due=relances_due,
        deadlines_soon=deadlines_soon,
    )
