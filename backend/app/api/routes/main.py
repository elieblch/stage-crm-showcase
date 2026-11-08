"""Routes API principales du CRM Stage."""

import os
import io
from uuid import UUID
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete, cast, Text
from sqlalchemy.dialects.postgresql import ARRAY as PG_ARRAY
from sqlalchemy.orm import selectinload
from datetime import datetime, timedelta

from app.core.database import get_db
from app.models.models import (
    User, SearchPreference, UserDocument, Offer, OfferMatch,
    Application, ApplicationEvent, Interview, FollowUp, UserIntegration,
    InterviewStory,
)
from app.schemas.schemas import (
    UserCreate, UserUpdate, UserResponse,
    SearchPreferenceUpdate, SearchPreferenceResponse,
    DocumentResponse,
    OfferResponse, OfferMatchResponse,
    ApplicationCreate, ApplicationUpdate, ApplicationResponse,
    InterviewCreate, InterviewResponse,
    DashboardStats,
    StoryCreate, StoryUpdate, StoryResponse,
    SearchStatusUpdate,
)
from app.services.claude_service import (
    generate_cover_letter, generate_email_draft,
    generate_interview_prep, suggest_cv_adaptations,
)

router = APIRouter()


# ══════════════════════════════════════════════════════════
# DASHBOARD
# ══════════════════════════════════════════════════════════

@router.get("/users/{user_id}/alerts")
async def get_user_alerts(user_id: UUID, db: AsyncSession = Depends(get_db)):
    """Retourne les alertes actives pour un utilisateur (cookie expire, etc.)."""
    alerts = []

    # Verifier les integrations
    result = await db.execute(
        select(UserIntegration).where(UserIntegration.user_id == user_id)
    )
    for integ in result.scalars().all():
        if not integ.is_active and integ.session_cookie:
            alerts.append({
                "type": "integration_expired",
                "service": integ.service_name,
                "message": f"Votre connexion {integ.service_name.title()} a expire. Reconnectez-vous via le Profil.",
                "severity": "warning",
            })
        elif integ.is_active and integ.session_expires_at:
            days_left = (integ.session_expires_at - datetime.utcnow()).days
            if days_left <= 3:
                alerts.append({
                    "type": "integration_expiring",
                    "service": integ.service_name,
                    "message": f"Votre connexion {integ.service_name.title()} expire dans {days_left} jour(s).",
                    "severity": "info",
                })

    return alerts


@router.get("/dashboard/{user_id}", response_model=DashboardStats)
async def get_dashboard(user_id: UUID, db: AsyncSession = Depends(get_db)):
    """Stats du dashboard principal."""
    today = datetime.utcnow().date()

    total_matches = await db.scalar(
        select(func.count(OfferMatch.id)).where(OfferMatch.user_id == user_id)
    )
    new_today = await db.scalar(
        select(func.count(OfferMatch.id)).where(
            OfferMatch.user_id == user_id,
            func.date(OfferMatch.created_at) == today,
        )
    )
    apps_sent = await db.scalar(
        select(func.count(Application.id)).where(
            Application.user_id == user_id,
            Application.status.in_(["sent", "acknowledged", "interview", "offer"]),
        )
    )
    interviews = await db.scalar(
        select(func.count(Interview.id))
        .join(Application)
        .where(
            Application.user_id == user_id,
            Interview.scheduled_at >= datetime.utcnow(),
        )
    )
    follow_ups = await db.scalar(
        select(func.count(FollowUp.id))
        .join(Application)
        .where(
            Application.user_id == user_id,
            FollowUp.is_sent == False,
            FollowUp.scheduled_at <= datetime.utcnow() + timedelta(days=3),
        )
    )

    # Pipeline
    pipeline_query = (
        select(Application.status, func.count(Application.id))
        .where(Application.user_id == user_id)
        .group_by(Application.status)
    )
    result = await db.execute(pipeline_query)
    pipeline = {row[0]: row[1] for row in result.all()}

    return DashboardStats(
        total_offers_matched=total_matches or 0,
        new_today=new_today or 0,
        applications_sent=apps_sent or 0,
        interviews_scheduled=interviews or 0,
        pending_follow_ups=follow_ups or 0,
        pipeline=pipeline,
    )


# ══════════════════════════════════════════════════════════
# UTILISATEUR & PROFIL
# ══════════════════════════════════════════════════════════

@router.post("/users", response_model=UserResponse)
async def create_user(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    user = User(**user_data.model_dump())
    db.add(user)
    await db.flush()
    # Créer les préférences par défaut
    prefs = SearchPreference(user_id=user.id)
    db.add(prefs)
    return user


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(user_id: UUID, db: AsyncSession = Depends(get_db)):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
    return user


@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: UUID,
    update: UserUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Met à jour les informations d'un utilisateur."""
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")

    for field, value in update.model_dump(exclude_unset=True).items():
        setattr(user, field, value)

    return user


@router.put("/users/{user_id}/search-status", response_model=UserResponse)
async def update_search_status(
    user_id: UUID,
    payload: SearchStatusUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Active/pause la recherche. Lance un scan+scoring immédiat si on réactive."""
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")

    was_active = user.is_active_search
    user.is_active_search = payload.is_active
    await db.flush()

    if payload.is_active and not was_active:
        # Réactivation : rescraper + rescorer pour rattraper
        from app.services.scraping_tasks import run_daily_scraping
        run_daily_scraping.delay()

    return user


# ══════════════════════════════════════════════════════════
# PRÉFÉRENCES DE RECHERCHE
# ══════════════════════════════════════════════════════════

@router.get("/users/{user_id}/preferences", response_model=SearchPreferenceResponse)
async def get_preferences(user_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(SearchPreference).where(SearchPreference.user_id == user_id)
    )
    prefs = result.scalar_one_or_none()
    if not prefs:
        raise HTTPException(status_code=404, detail="Préférences non trouvées")
    return prefs


# Champs qui influent sur le score calculé → nécessitent un rescore quand ils changent.
_SCORING_FIELDS = {
    "target_domains", "target_companies", "target_locations", "contract_types",
    "keywords", "excluded_keywords",
    "min_duration_months", "max_duration_months",
    "start_date_earliest", "start_date_latest", "min_salary",
    "scoring_weights",
}
# Champs UX/newsletter : sauvegarde sans rescore, sans DELETE.
_UX_FIELDS = {"newsletter_enabled", "newsletter_time", "min_match_score"}


@router.put("/users/{user_id}/preferences", response_model=SearchPreferenceResponse)
async def update_preferences(
    user_id: UUID,
    update: SearchPreferenceUpdate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SearchPreference).where(SearchPreference.user_id == user_id)
    )
    prefs = result.scalar_one_or_none()
    if not prefs:
        raise HTTPException(status_code=404, detail="Préférences non trouvées")

    # Snapshot AVANT changement, pour détecter les champs qui ont bougé
    before = {f: getattr(prefs, f) for f in _SCORING_FIELDS}

    incoming = update.model_dump(exclude_unset=True)
    for field, value in incoming.items():
        setattr(prefs, field, value)

    await db.flush()

    # Détecter si un champ scoring a changé
    scoring_changed = any(
        field in incoming and before[field] != getattr(prefs, field)
        for field in _SCORING_FIELDS
    )

    if scoring_changed:
        # Pas de DELETE — on UPDATE les matches existants via une task dédiée.
        from app.services.scraping_tasks import rescore_user_matches
        rescore_user_matches.delay(str(user_id))

    return prefs


# ══════════════════════════════════════════════════════════
# DOCUMENTS
# ══════════════════════════════════════════════════════════

@router.post("/users/{user_id}/documents", response_model=DocumentResponse)
async def upload_document(
    user_id: UUID,
    doc_type: str = Query(..., description="cv, bulletin, projet, certification"),
    title: str = Query(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    content = await file.read()

    # Sauvegarder le fichier sur disque
    file_path = f"uploads/{user_id}/{file.filename}"
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "wb") as f:
        f.write(content)

    # Extraire le texte selon le type de fichier
    extracted_text = ""
    filename_lower = (file.filename or "").lower()

    if filename_lower.endswith(".pdf"):
        import pdfplumber
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            extracted_text = "\n".join(
                page.extract_text() or "" for page in pdf.pages
            )
    elif filename_lower.endswith(".docx"):
        from docx import Document as DocxDocument
        doc_file = DocxDocument(io.BytesIO(content))
        extracted_text = "\n".join(p.text for p in doc_file.paragraphs)

    doc = UserDocument(
        user_id=user_id,
        doc_type=doc_type,
        title=title,
        file_path=file_path,
        extracted_text=extracted_text,
    )
    db.add(doc)
    await db.flush()
    await db.refresh(doc)
    return doc


@router.delete("/users/{user_id}/documents/{doc_id}")
async def delete_document(
    user_id: UUID,
    doc_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Supprime un document utilisateur."""
    result = await db.execute(
        select(UserDocument).where(
            UserDocument.id == doc_id,
            UserDocument.user_id == user_id,
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document non trouvé")

    # Supprimer le fichier physique si existant
    if doc.file_path and os.path.exists(doc.file_path):
        os.remove(doc.file_path)

    await db.delete(doc)
    return {"status": "deleted"}


@router.put("/users/{user_id}/documents/{doc_id}/set-primary", response_model=DocumentResponse)
async def set_primary_document(
    user_id: UUID,
    doc_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Définit un document comme principal (et retire le statut des autres du même type)."""
    result = await db.execute(
        select(UserDocument).where(
            UserDocument.id == doc_id,
            UserDocument.user_id == user_id,
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document non trouvé")

    # Retirer is_primary des autres documents du même type pour cet utilisateur
    result = await db.execute(
        select(UserDocument).where(
            UserDocument.user_id == user_id,
            UserDocument.doc_type == doc.doc_type,
            UserDocument.is_primary == True,
        )
    )
    for other_doc in result.scalars().all():
        other_doc.is_primary = False

    doc.is_primary = True
    return doc


@router.get("/users/{user_id}/documents", response_model=list[DocumentResponse])
async def list_documents(user_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(UserDocument).where(UserDocument.user_id == user_id)
    )
    return result.scalars().all()


# ══════════════════════════════════════════════════════════
# OFFRES MATCHÉES
# ══════════════════════════════════════════════════════════

@router.get("/users/{user_id}/matches", response_model=list[OfferMatchResponse])
async def get_matches(
    user_id: UUID,
    min_score: int = Query(0, ge=0, le=100),
    interest: str | None = None,
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(OfferMatch)
        .options(selectinload(OfferMatch.offer))
        .where(OfferMatch.user_id == user_id, OfferMatch.match_score >= min_score)
        .order_by(OfferMatch.match_score.desc())
        .limit(limit)
    )
    if interest:
        query = query.where(OfferMatch.user_interest == interest)

    result = await db.execute(query)
    return result.scalars().all()


@router.put("/matches/{match_id}/interest")
async def update_interest(
    match_id: UUID,
    interest: str = Query(..., description="interested, not_interested"),
    db: AsyncSession = Depends(get_db),
):
    match = await db.get(OfferMatch, match_id)
    if not match:
        raise HTTPException(status_code=404)
    match.user_interest = interest
    match.viewed_at = datetime.utcnow()
    return {"status": "ok"}


# ══════════════════════════════════════════════════════════
# CANDIDATURES
# ══════════════════════════════════════════════════════════

@router.post("/users/{user_id}/applications", response_model=ApplicationResponse)
async def create_application(
    user_id: UUID,
    data: ApplicationCreate,
    db: AsyncSession = Depends(get_db),
):
    app = Application(user_id=user_id, offer_id=data.offer_id)
    db.add(app)
    await db.flush()
    # Log event
    event = ApplicationEvent(
        application_id=app.id,
        event_type="created",
        event_data={"status": "draft"},
    )
    db.add(event)
    # Charger la relation offer pour la réponse
    await db.refresh(app, ["offer"])
    return app


@router.get("/users/{user_id}/applications", response_model=list[ApplicationResponse])
async def list_applications(
    user_id: UUID,
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(Application).options(selectinload(Application.offer)).where(Application.user_id == user_id)
    if status:
        query = query.where(Application.status == status)
    result = await db.execute(query.order_by(Application.updated_at.desc()))
    return result.scalars().all()


@router.put("/applications/{app_id}", response_model=ApplicationResponse)
async def update_application(
    app_id: UUID,
    update: ApplicationUpdate,
    db: AsyncSession = Depends(get_db),
):
    app = await db.get(Application, app_id)
    if not app:
        raise HTTPException(status_code=404)

    old_status = app.status
    for field, value in update.model_dump(exclude_unset=True).items():
        setattr(app, field, value)

    if update.status and update.status != old_status:
        event = ApplicationEvent(
            application_id=app.id,
            event_type="status_change",
            event_data={"from": old_status, "to": update.status},
        )
        db.add(event)

    return app


@router.delete("/applications/{app_id}")
async def delete_application(
    app_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Supprime une candidature uniquement si elle est en brouillon."""
    app = await db.get(Application, app_id)
    if not app:
        raise HTTPException(status_code=404)
    if app.status != "draft":
        raise HTTPException(status_code=400, detail="Seules les candidatures en brouillon peuvent etre supprimees")
    await db.delete(app)
    return {"status": "deleted"}


# ══════════════════════════════════════════════════════════
# GÉNÉRATION IA — helpers + endpoints
# ══════════════════════════════════════════════════════════

async def _load_full_profile(user_id: UUID, db: AsyncSession) -> dict:
    """Charge le profil complet : infos + CV + tous les documents + skills."""
    from app.models.models import UserSkill

    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")

    # Tous les documents
    docs_result = await db.execute(
        select(UserDocument).where(UserDocument.user_id == user_id)
    )
    all_docs = docs_result.scalars().all()

    # CV principal (ou premier CV)
    cv_doc = next((d for d in all_docs if d.doc_type == "cv" and d.is_primary), None)
    if not cv_doc:
        cv_doc = next((d for d in all_docs if d.doc_type == "cv"), None)

    # Documents complementaires (projets, lettres, certifications)
    extra_docs = []
    for doc in all_docs:
        if doc.doc_type != "cv" and doc.extracted_text:
            extra_docs.append({
                "type": doc.doc_type,
                "title": doc.title,
                "text": doc.extracted_text[:1500],
            })

    # Construire le resume des projets/experiences supplementaires
    projects_summary = ""
    if extra_docs:
        parts = []
        for ed in extra_docs[:5]:  # Max 5 documents supplementaires
            parts.append(f"[{ed['type'].upper()}: {ed['title']}]\n{ed['text'][:800]}")
        projects_summary = "\n\n".join(parts)

    # Skills
    skills_result = await db.execute(
        select(UserSkill).where(UserSkill.user_id == user_id)
    )
    skills = [s.skill_name for s in skills_result.scalars().all()]

    # Preferences
    prefs_result = await db.execute(
        select(SearchPreference).where(SearchPreference.user_id == user_id)
    )
    prefs = prefs_result.scalar_one_or_none()

    return {
        "id": str(user.id),
        "full_name": user.full_name,
        "email": user.email,
        "phone": user.phone or "",
        "linkedin_url": user.linkedin_url or "",
        "education": os.getenv("USER_EDUCATION", ""),
        "skills": skills,
        "cv_text": cv_doc.extracted_text[:3000] if cv_doc and cv_doc.extracted_text else "",
        "cv_summary": (cv_doc.extracted_text[:500] if cv_doc and cv_doc.extracted_text else ""),
        "projects_summary": projects_summary,
        "extra_documents": extra_docs,
        "preferences": {
            "target_domains": prefs.target_domains if prefs else [],
            "target_locations": prefs.target_locations if prefs else [],
            "keywords": prefs.keywords if prefs else [],
            "excluded_keywords": prefs.excluded_keywords if prefs else [],
            "target_companies": prefs.target_companies if prefs else [],
            "contract_types": prefs.contract_types if prefs else [],
        } if prefs else {},
    }


def _offer_to_dict(offer: Offer) -> dict:
    return {
        "id": str(offer.id),
        "title": offer.title,
        "company_name": offer.company_name,
        "description": offer.description,
        "location": offer.location,
        "domain": offer.domain,
        "required_skills": offer.required_skills or [],
        "contact_name": offer.contact_name,
        "contact_email": offer.contact_email,
    }


@router.post("/applications/{app_id}/generate-cover-letter")
async def api_generate_cover_letter(app_id: UUID, db: AsyncSession = Depends(get_db)):
    app = await db.get(Application, app_id)
    if not app:
        raise HTTPException(status_code=404)

    offer = await db.get(Offer, app.offer_id)
    profile = await _load_full_profile(app.user_id, db)

    letter = await generate_cover_letter(profile, _offer_to_dict(offer))
    app.cover_letter_text = letter
    return {"cover_letter": letter}


@router.post("/applications/{app_id}/generate-email")
async def api_generate_email(app_id: UUID, email_type: str = Query("candidature"), db: AsyncSession = Depends(get_db)):
    app = await db.get(Application, app_id)
    if not app:
        raise HTTPException(status_code=404)

    offer = await db.get(Offer, app.offer_id)
    profile = await _load_full_profile(app.user_id, db)

    email = await generate_email_draft(profile, _offer_to_dict(offer), email_type)
    app.email_draft = email.get("body", "")
    return email


@router.post("/applications/{app_id}/generate-interview-prep")
async def api_generate_prep(app_id: UUID, interview_type: str = Query("general"), db: AsyncSession = Depends(get_db)):
    app = await db.get(Application, app_id)
    if not app:
        raise HTTPException(status_code=404)

    offer = await db.get(Offer, app.offer_id)
    profile = await _load_full_profile(app.user_id, db)

    # Charger les stories de l'utilisateur, triées par updated_at desc (pour fallback "5 plus récentes")
    stories_result = await db.execute(
        select(InterviewStory)
        .where(InterviewStory.user_id == app.user_id)
        .order_by(InterviewStory.updated_at.desc())
    )
    stories = [
        {
            "id": str(s.id), "title": s.title,
            "situation": s.situation, "task": s.task,
            "action": s.action, "result": s.result,
            "reflection": s.reflection, "tags": list(s.tags or []),
            "source": s.source,
        }
        for s in stories_result.scalars().all()
    ]

    prep = await generate_interview_prep(profile, _offer_to_dict(offer), interview_type, user_stories=stories)
    return prep


@router.post("/applications/{app_id}/suggest-cv-changes")
async def api_suggest_cv(app_id: UUID, db: AsyncSession = Depends(get_db)):
    app = await db.get(Application, app_id)
    if not app:
        raise HTTPException(status_code=404)

    offer = await db.get(Offer, app.offer_id)
    profile = await _load_full_profile(app.user_id, db)

    if not profile.get("cv_text"):
        raise HTTPException(status_code=400, detail="Aucun CV uploade")

    offer_data = _offer_to_dict(offer)
    offer_data["_projects_summary"] = profile.get("projects_summary", "")
    suggestions = await suggest_cv_adaptations(profile["cv_text"], offer_data)
    return suggestions


# ══════════════════════════════════════════════════════════
# INTÉGRATIONS (JobTeaser, etc.)
# ══════════════════════════════════════════════════════════

@router.post("/users/{user_id}/integrations/jobteaser/cookie")
async def save_jobteaser_cookie(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    cookie_value: str = Query(..., description="Resultat de document.cookie depuis les DevTools"),
    base_url: str = Query("https://em-lyon.jobteaser.com"),
):
    """Stocke les cookies de session JobTeaser et verifie leur validite.

    Accepte le resultat complet de document.cookie (toutes les paires key=value).
    """
    import httpx
    import logging
    logger = logging.getLogger(__name__)

    cookie_str = cookie_value.strip()

    # Log pour debug
    cookie_count = len([c for c in cookie_str.split(";") if "=" in c])
    logger.info(f"JobTeaser cookie: recu {len(cookie_str)} chars, {cookie_count} paires")

    test_urls = [
        f"{base_url.rstrip('/')}/fr/job-offers",
        f"{base_url.rstrip('/')}/fr/offers",
        f"{base_url.rstrip('/')}/fr/dashboard",
    ]

    valid = False
    final_url = ""
    status_code = 0
    body_len = 0

    try:
        with httpx.Client(timeout=20, follow_redirects=True) as client:
            for test_url in test_urls:
                headers = {
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "fr-FR,fr;q=0.9",
                    "Cookie": cookie_str,
                }
                r = client.get(test_url, headers=headers)
                final_url = str(r.url)
                status_code = r.status_code
                body_len = len(r.text)

                logger.info(
                    f"JobTeaser test: GET {test_url} -> "
                    f"status={status_code}, final_url={final_url}, "
                    f"body={body_len} chars, "
                    f"has_sign_in={'sign_in' in final_url}"
                )

                # Succes si pas de redirect vers sign_in et status 200
                if status_code == 200 and "sign_in" not in final_url and "login" not in final_url:
                    valid = True
                    break

    except Exception as e:
        logger.error(f"JobTeaser cookie test error: {e}")
        raise HTTPException(status_code=500, detail=f"Erreur de test : {str(e)[:100]}")

    if not valid:
        raise HTTPException(
            status_code=400,
            detail=f"Cookie invalide. Status={status_code}, redirect={'sign_in' in final_url}. Copiez TOUS les cookies via document.cookie dans la console."
        )

    # Stocker en BDD
    result = await db.execute(
        select(UserIntegration).where(
            UserIntegration.user_id == user_id,
            UserIntegration.service_name == "jobteaser",
        )
    )
    integration = result.scalar_one_or_none()

    if integration:
        integration.session_cookie = cookie_str
        integration.service_url = base_url
        integration.is_active = True
        integration.session_expires_at = datetime.utcnow() + timedelta(days=14)
    else:
        integration = UserIntegration(
            user_id=user_id,
            service_name="jobteaser",
            service_url=base_url,
            session_cookie=cookie_str,
            is_active=True,
            session_expires_at=datetime.utcnow() + timedelta(days=14),
        )
        db.add(integration)

    await db.flush()
    logger.info(f"JobTeaser cookie stocke, {cookie_count} cookies, expire dans 14j")
    return {"status": "connected", "service": "jobteaser", "expires_in_days": 14}


@router.post("/users/{user_id}/integrations/jobteaser/test")
async def test_jobteaser_cookie(user_id: UUID, db: AsyncSession = Depends(get_db)):
    """Teste si le cookie JobTeaser stocke est encore valide."""
    import httpx

    result = await db.execute(
        select(UserIntegration).where(
            UserIntegration.user_id == user_id,
            UserIntegration.service_name == "jobteaser",
            UserIntegration.is_active == True,
        )
    )
    integration = result.scalar_one_or_none()
    if not integration or not integration.session_cookie:
        return {"valid": False, "reason": "no_cookie"}

    # Verifier expiration
    if integration.session_expires_at and integration.session_expires_at < datetime.utcnow():
        integration.is_active = False
        return {"valid": False, "reason": "expired"}

    # Tester le cookie
    try:
        base = (integration.service_url or "https://em-lyon.jobteaser.com").rstrip("/")
        for path in ["/fr/job-offers", "/fr/offers", "/fr/dashboard"]:
            with httpx.Client(timeout=15, follow_redirects=True) as client:
                r = client.get(f"{base}{path}", headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                    "Cookie": integration.session_cookie,
                })
                if r.status_code == 200 and "sign_in" not in str(r.url) and "login" not in str(r.url):
                    return {"valid": True, "expires_at": integration.session_expires_at.isoformat() if integration.session_expires_at else None}
    except Exception:
        pass

    integration.is_active = False
    return {"valid": False, "reason": "invalid"}


@router.get("/users/{user_id}/integrations/jobteaser/status")
async def jobteaser_status(user_id: UUID, db: AsyncSession = Depends(get_db)):
    """Verifie si la connexion JobTeaser est active."""
    result = await db.execute(
        select(UserIntegration).where(
            UserIntegration.user_id == user_id,
            UserIntegration.service_name == "jobteaser",
        )
    )
    integration = result.scalar_one_or_none()

    if not integration or not integration.is_active:
        return {"connected": False}

    expired = integration.session_expires_at and integration.session_expires_at < datetime.utcnow()
    return {
        "connected": not expired,
        "service_url": integration.service_url,
        "expires_at": integration.session_expires_at.isoformat() if integration.session_expires_at else None,
    }


@router.delete("/users/{user_id}/integrations/jobteaser")
async def disconnect_jobteaser(user_id: UUID, db: AsyncSession = Depends(get_db)):
    """Deconnecte JobTeaser."""
    result = await db.execute(
        select(UserIntegration).where(
            UserIntegration.user_id == user_id,
            UserIntegration.service_name == "jobteaser",
        )
    )
    integration = result.scalar_one_or_none()
    if integration:
        integration.is_active = False
        integration.session_cookie = None
    return {"status": "disconnected"}


@router.post("/users/{user_id}/extract-skills")
async def extract_cv_skills(user_id: UUID, db: AsyncSession = Depends(get_db)):
    """Extrait les compétences du CV principal et les stocke dans user_skills."""
    from app.services.cv_extraction import extract_skills_from_cv
    from app.models.models import UserSkill

    # Trouver le CV principal ou le premier CV
    result = await db.execute(
        select(UserDocument).where(
            UserDocument.user_id == user_id,
            UserDocument.doc_type == "cv",
        ).order_by(UserDocument.is_primary.desc())
    )
    cv_doc = result.scalars().first()
    if not cv_doc or not cv_doc.extracted_text:
        raise HTTPException(status_code=400, detail="Aucun CV avec texte extrait")

    # Extraire les skills
    skills = extract_skills_from_cv(cv_doc.extracted_text)

    # Supprimer les anciennes skills de ce user
    await db.execute(delete(UserSkill).where(UserSkill.user_id == user_id))

    # Insérer les nouvelles
    for s in skills:
        skill = UserSkill(
            user_id=user_id,
            skill_name=s["skill_name"],
            skill_category=s["skill_category"],
            proficiency_level=s["proficiency_level"],
            source_document_id=cv_doc.id,
        )
        db.add(skill)

    await db.flush()
    return {"extracted": len(skills), "skills": skills}


@router.post("/users/{user_id}/score-offers")
async def trigger_scoring(user_id: UUID):
    """Déclenche le scoring de toutes les offres pour un utilisateur."""
    from app.services.scraping_tasks import score_all_offers
    result = score_all_offers.delay(str(user_id))
    return {"status": "started", "task_id": str(result.id)}


@router.post("/users/{user_id}/score-offers/sync")
async def score_offers_sync(user_id: UUID, db: AsyncSession = Depends(get_db)):
    """Score les offres avec matching CV enrichi."""
    from app.services.scoring_service import score_offer
    from app.services.cv_extraction import tokenize_for_matching
    from app.models.models import UserSkill

    # Charger les préférences
    result = await db.execute(
        select(SearchPreference).where(SearchPreference.user_id == user_id)
    )
    prefs = result.scalar_one_or_none()
    if not prefs:
        raise HTTPException(status_code=404, detail="Préférences non trouvées")

    # Charger le CV pour tokenisation
    cv_result = await db.execute(
        select(UserDocument).where(
            UserDocument.user_id == user_id,
            UserDocument.doc_type == "cv",
        ).order_by(UserDocument.is_primary.desc())
    )
    cv_doc = cv_result.scalars().first()
    cv_tokens = tokenize_for_matching(cv_doc.extracted_text) if cv_doc and cv_doc.extracted_text else None

    # Charger les skills extraites
    skills_result = await db.execute(
        select(UserSkill).where(UserSkill.user_id == user_id)
    )
    user_skills = [s.skill_name for s in skills_result.scalars().all()]

    # Offres pas encore scorées
    result = await db.execute(
        select(Offer).where(
            Offer.is_active == True,
            ~Offer.id.in_(
                select(OfferMatch.offer_id).where(OfferMatch.user_id == user_id)
            ),
        )
    )
    offers = result.scalars().all()

    scored = 0
    matched = 0
    excluded_date = 0
    for offer in offers:
        scoring = score_offer(
            offer_title=offer.title or "",
            offer_description=offer.description or "",
            offer_company=offer.company_name or "",
            offer_location=offer.location or "",
            offer_domain=offer.domain or "",
            target_domains=prefs.target_domains or [],
            target_locations=prefs.target_locations or [],
            keywords=prefs.keywords or [],
            excluded_keywords=prefs.excluded_keywords or [],
            start_date_earliest=prefs.start_date_earliest,
            offer_start_date=offer.start_date,
            cv_tokens=cv_tokens,
            user_skills=user_skills,
        )

        score = scoring["score"]
        if score == -1:
            excluded_date += 1
            continue
        scored += 1

        if score >= (prefs.min_match_score or 0):
            match = OfferMatch(
                user_id=user_id,
                offer_id=offer.id,
                match_score=score,
                match_reasons=scoring["breakdown"],
                ai_summary=scoring["analysis"],
            )
            db.add(match)
            matched += 1

    await db.flush()
    return {"scored": scored, "matched": matched, "excluded_date": excluded_date, "min_score": prefs.min_match_score or 0}


@router.post("/scraping/run")
async def trigger_scraping():
    """Déclenche un scraping manuel de toutes les plateformes."""
    from app.services.scraping_tasks import run_daily_scraping
    result = run_daily_scraping.delay()
    return {"status": "started", "task_id": str(result.id)}


@router.post("/scraping/run/{platform}")
async def trigger_platform_scraping(platform: str):
    """Déclenche le scraping d'une plateforme spécifique."""
    from app.services.scraping_tasks import scrape_platform
    result = scrape_platform.delay(platform)
    return {"status": "started", "task_id": str(result.id), "platform": platform}


@router.get("/offers/stats")
async def offer_stats(db: AsyncSession = Depends(get_db)):
    """Retourne le nombre d'offres par plateforme."""
    result = await db.execute(
        select(Offer.source_platform, func.count(Offer.id))
        .where(Offer.is_active == True)
        .group_by(Offer.source_platform)
    )
    return {row[0]: row[1] for row in result.all()}


@router.get("/offers", response_model=list[OfferResponse])
async def list_offers(
    limit: int = Query(50, le=200),
    domain: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Liste les offres scrapées."""
    query = select(Offer).where(Offer.is_active == True).order_by(Offer.scraped_at.desc()).limit(limit)
    if domain:
        query = query.where(Offer.domain == domain)
    result = await db.execute(query)
    return result.scalars().all()




# ══════════════════════════════════════════════════════════
# STORY BANK (STAR)
# ══════════════════════════════════════════════════════════

@router.post("/users/{user_id}/stories", response_model=StoryResponse)
async def create_story(user_id: UUID, data: StoryCreate, db: AsyncSession = Depends(get_db)):
    story = InterviewStory(user_id=user_id, **data.model_dump())
    db.add(story)
    await db.commit()
    await db.refresh(story)
    return story


@router.get("/users/{user_id}/stories", response_model=list[StoryResponse])
async def list_stories(
    user_id: UUID,
    tags: list[str] | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    q = select(InterviewStory).where(InterviewStory.user_id == user_id)
    if tags:
        # Filtre : au moins un tag en commun (opérateur PostgreSQL &&)
        q = q.where(InterviewStory.tags.op("&&")(cast(tags, PG_ARRAY(Text))))
    q = q.order_by(InterviewStory.updated_at.desc())
    result = await db.execute(q)
    return list(result.scalars().all())


@router.get("/stories/{story_id}", response_model=StoryResponse)
async def get_story(story_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(InterviewStory).where(InterviewStory.id == story_id))
    story = result.scalar_one_or_none()
    if not story:
        raise HTTPException(status_code=404, detail="Story non trouvée")
    return story


@router.put("/stories/{story_id}", response_model=StoryResponse)
async def update_story(story_id: UUID, data: StoryUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(InterviewStory).where(InterviewStory.id == story_id))
    story = result.scalar_one_or_none()
    if not story:
        raise HTTPException(status_code=404, detail="Story non trouvée")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(story, field, value)
    await db.commit()
    await db.refresh(story)
    return story


@router.delete("/stories/{story_id}")
async def delete_story(story_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(InterviewStory).where(InterviewStory.id == story_id))
    story = result.scalar_one_or_none()
    if not story:
        raise HTTPException(status_code=404, detail="Story non trouvée")
    await db.delete(story)
    await db.commit()
    return {"status": "deleted"}


# ══════════════════════════════════════════════════════════
# NEWSLETTER
# ══════════════════════════════════════════════════════════

@router.post("/newsletter/send-now")
async def newsletter_send_now(user_id: UUID | None = Query(None)):
    """Déclenche l'envoi de la newsletter (sync pour pouvoir retourner le résultat).

    - Sans `user_id` : newsletter pour tous les users avec newsletter_enabled=true.
    - Avec `user_id` : newsletter uniquement pour ce user (mode test).
    """
    from app.services.newsletter_tasks import send_daily_newsletter, send_newsletter_for_user
    if user_id:
        result = send_newsletter_for_user(str(user_id))
        return result
    result = send_daily_newsletter()
    return result
