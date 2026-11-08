"""Tâche Celery newsletter quotidienne : top offres des dernières 24h par user."""
import logging
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.core.celery_app import celery_app
from app.core.config import get_settings
from app.services.email_service import send_email

logger = logging.getLogger(__name__)

settings = get_settings()
SYNC_DATABASE_URL = settings.database_url.replace("+asyncpg", "+psycopg2")
sync_engine = create_engine(SYNC_DATABASE_URL)

# Jinja2 env — chargement du template HTML une seule fois
_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"
_jinja = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_DIR)),
    autoescape=select_autoescape(["html"]),
)

MAX_OFFERS_PER_EMAIL = 15
LOOKBACK_HOURS = 24

FRENCH_MONTHS = ["janvier", "février", "mars", "avril", "mai", "juin",
                 "juillet", "août", "septembre", "octobre", "novembre", "décembre"]


def _format_date_fr(d: datetime) -> str:
    return f"{d.day} {FRENCH_MONTHS[d.month - 1]} {d.year}"


def _collect_user_matches(session: Session, user_id: str, min_score: int) -> list[dict]:
    """Top matches non-envoyés des dernières 24h."""
    rows = session.execute(
        text(f"""
            SELECT m.id AS match_id, m.match_score, m.ai_summary,
                   o.id AS offer_id, o.title, o.company_name, o.location,
                   o.domain, o.duration_months, o.salary, o.source_url, o.source_platform
            FROM offer_matches m
            JOIN offers o ON o.id = m.offer_id
            WHERE m.user_id = :uid
              AND m.match_score >= :min_score
              AND COALESCE(m.newsletter_sent, false) = false
              AND m.created_at > NOW() - INTERVAL '{LOOKBACK_HOURS} hours'
            ORDER BY m.match_score DESC
            LIMIT :lim
        """),
        {"uid": user_id, "min_score": min_score, "lim": MAX_OFFERS_PER_EMAIL},
    ).fetchall()
    return [
        {
            "match_id": str(r.match_id),
            "match_score": r.match_score,
            "ai_summary": r.ai_summary,
            "offer": {
                "id": str(r.offer_id),
                "title": r.title or "",
                "company_name": r.company_name or "",
                "location": r.location,
                "domain": r.domain,
                "duration_months": r.duration_months,
                "salary": r.salary,
                "source_url": r.source_url,
                "source_platform": r.source_platform,
            },
        }
        for r in rows
    ]


def _render_html(user_name: str, offers: list[dict]) -> str:
    tpl = _jinja.get_template("newsletter.html")
    scores = [o["match_score"] for o in offers]
    avg = round(sum(scores) / len(scores)) if scores else 0
    companies = sorted({o["offer"]["company_name"] for o in offers if o["offer"]["company_name"]})
    return tpl.render(
        user_name=user_name,
        date_str=_format_date_fr(datetime.now()),
        offers=offers,
        avg_score=avg,
        top_companies=companies,
        frontend_url=settings.frontend_url,
    )


def _send_for_user(session: Session, user_row) -> dict:
    """Construit + envoie la newsletter d'un utilisateur. Marque les matches."""
    user_id = str(user_row.user_id)
    user_name = (user_row.full_name or user_row.email.split("@")[0] or "").strip()
    recipient = settings.newsletter_recipient or user_row.email

    offers = _collect_user_matches(session, user_id, user_row.min_match_score or 60)
    if not offers:
        logger.info(f"📧 {user_name} : aucune nouvelle offre >= {user_row.min_match_score}, pas d'envoi.")
        return {"user_id": user_id, "status": "empty", "offers": 0}

    subject = f"Stage CRM — {len(offers)} nouvelle{'s' if len(offers) > 1 else ''} offre{'s' if len(offers) > 1 else ''} pour vous"
    html_body = _render_html(user_name, offers)
    result = send_email(recipient, subject, html_body)

    if result["status"] in ("sent", "logged"):
        # En mode test (logged), on marque aussi pour ne pas re-envoyer le même contenu au prochain cycle
        ids = [o["match_id"] for o in offers]
        session.execute(
            text("UPDATE offer_matches SET newsletter_sent=true, newsletter_sent_at=NOW() WHERE id = ANY(CAST(:ids AS uuid[]))"),
            {"ids": ids},
        )
        session.commit()
    return {"user_id": user_id, "status": result["status"], "offers": len(offers), "message": result.get("message", "")}


@celery_app.task(name="app.services.newsletter_tasks.send_daily_newsletter")
def send_daily_newsletter():
    """Newsletter quotidienne pour tous les users avec newsletter_enabled=true."""
    logger.info("📧 Génération de la newsletter quotidienne…")
    results: list[dict] = []

    with Session(sync_engine) as session:
        users = session.execute(
            text("""
                SELECT u.id AS user_id, u.email, u.full_name,
                       p.newsletter_enabled, p.min_match_score
                FROM users u
                JOIN search_preferences p ON p.user_id = u.id
                WHERE COALESCE(p.newsletter_enabled, true) = true
                  AND COALESCE(u.is_active_search, true) = true
            """)
        ).fetchall()

        logger.info(f"📧 {len(users)} utilisateur(s) avec newsletter activée")
        for u in users:
            try:
                results.append(_send_for_user(session, u))
            except Exception as e:
                logger.error(f"Newsletter user {u.user_id} échoué: {e}")
                results.append({"user_id": str(u.user_id), "status": "error", "message": str(e)})

    sent = sum(1 for r in results if r["status"] == "sent")
    logged = sum(1 for r in results if r["status"] == "logged")
    empty = sum(1 for r in results if r["status"] == "empty")
    errors = sum(1 for r in results if r["status"] == "error")
    logger.info(f"📧 Newsletter : sent={sent}, logged={logged}, empty={empty}, errors={errors}")
    return {"results": results, "sent": sent, "logged": logged, "empty": empty, "errors": errors}


@celery_app.task(name="app.services.newsletter_tasks.send_newsletter_for_user")
def send_newsletter_for_user(user_id: str):
    """Envoi manuel pour 1 user (déclenché via API)."""
    with Session(sync_engine) as session:
        u = session.execute(
            text("""
                SELECT u.id AS user_id, u.email, u.full_name,
                       p.newsletter_enabled, p.min_match_score
                FROM users u
                JOIN search_preferences p ON p.user_id = u.id
                WHERE u.id = :uid
            """),
            {"uid": user_id},
        ).first()
        if not u:
            return {"status": "user_not_found"}
        return _send_for_user(session, u)
