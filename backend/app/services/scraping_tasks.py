"""
Tâches de scraping quotidien.
Chaque scraper récupère les offres d'une plateforme spécifique,
puis les sauvegarde en BDD.
"""

import logging
from datetime import datetime

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.core.celery_app import celery_app
from app.core.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

# Engine synchrone pour les tâches Celery (asyncpg → psycopg2)
SYNC_DATABASE_URL = settings.database_url.replace("+asyncpg", "+psycopg2")
sync_engine = create_engine(SYNC_DATABASE_URL)


@celery_app.task(name="app.services.scraping_tasks.run_daily_scraping")
def run_daily_scraping():
    """Tâche principale : lance tous les scrapers, puis score automatiquement."""
    from app.scrapers.registry import list_scrapers

    logger.info("Démarrage du scan quotidien des offres...")

    available = list_scrapers()
    logger.info(f"Scrapers disponibles : {available}")

    for scraper_name in available:
        try:
            scrape_platform.delay(scraper_name)
            logger.info(f"  {scraper_name} : tâche lancée")
        except Exception as e:
            logger.error(f"  {scraper_name} : {e}")

    # Scorer automatiquement pour tous les utilisateurs après un délai
    # (laisser le temps aux scrapers de finir)
    score_all_users.apply_async(countdown=180)  # 3 min après

    logger.info("Scan quotidien — tâches de scraping lancées")
    return {"status": "scraping_started", "platforms": available}


@celery_app.task(name="app.services.scraping_tasks.score_all_users")
def score_all_users():
    """Score les nouvelles offres uniquement pour les utilisateurs en recherche active."""
    with Session(sync_engine) as session:
        users = session.execute(
            text("SELECT id FROM users WHERE COALESCE(is_active_search, true) = true")
        ).fetchall()

    logger.info(f"Scoring automatique pour {len(users)} utilisateur(s) actif(s)…")

    for user_row in users:
        try:
            score_all_offers.delay(str(user_row.id))
        except Exception as e:
            logger.error(f"Scoring user {user_row.id} erreur: {e}")

    return {"status": "scoring_started", "users": len(users)}


@celery_app.task(name="app.services.scraping_tasks.scrape_platform")
def scrape_platform(platform_name: str):
    """Scrape une plateforme et sauvegarde les nouvelles offres en BDD."""
    from app.scrapers.registry import get_scraper

    logger.info(f"Scraping {platform_name}...")

    scraper = get_scraper(platform_name)
    if not scraper:
        logger.warning(f"Scraper non trouvé : {platform_name}")
        return {"platform": platform_name, "status": "not_found"}

    try:
        offers = scraper.scrape()
        logger.info(f"{platform_name} : {len(offers)} offres scrapées")

        new_count = _save_offers(offers)
        logger.info(f"{platform_name} : {new_count} nouvelles offres sauvegardées")

        return {"platform": platform_name, "scraped": len(offers), "new": new_count}
    except Exception as e:
        logger.error(f"{platform_name} erreur : {e}")
        return {"platform": platform_name, "error": str(e)}


@celery_app.task(name="app.services.scraping_tasks.score_all_offers")
def score_all_offers(user_id: str):
    """Score toutes les offres non-scorées : passe locale puis passe IA Claude sur le top."""
    from app.services.scoring_service import score_offer_multidim
    from app.services.cv_extraction import tokenize_for_matching
    import json

    logger.info(f"Scoring des offres pour user {user_id}...")

    with Session(sync_engine) as session:
        # Charger les préférences utilisateur
        prefs = session.execute(
            text("SELECT * FROM search_preferences WHERE user_id = :uid"),
            {"uid": user_id},
        ).first()

        if not prefs:
            logger.warning(f"Pas de préférences pour user {user_id}")
            return {"status": "no_preferences"}

        prefs_dict = {
            "target_domains": list(prefs.target_domains or []),
            "target_locations": list(prefs.target_locations or []),
            "target_companies": list(prefs.target_companies or []),
            "keywords": list(prefs.keywords or []),
            "excluded_keywords": list(prefs.excluded_keywords or []),
            "start_date_earliest": prefs.start_date_earliest,
            "start_date_latest": prefs.start_date_latest,
        }
        weights = prefs.scoring_weights if prefs.scoring_weights else None
        min_score = prefs.min_match_score or 0

        # Charger le CV pour tokenisation
        cv_row = session.execute(
            text("SELECT extracted_text FROM user_documents WHERE user_id = :uid AND doc_type = 'cv' ORDER BY is_primary DESC LIMIT 1"),
            {"uid": user_id},
        ).first()
        cv_tokens = tokenize_for_matching(cv_row.extracted_text) if cv_row and cv_row.extracted_text else None

        # Charger les skills
        skills_rows = session.execute(
            text("SELECT skill_name FROM user_skills WHERE user_id = :uid"),
            {"uid": user_id},
        ).fetchall()
        user_skills = [r.skill_name for r in skills_rows]

        logger.info(f"CV tokens: {len(cv_tokens) if cv_tokens else 0}, Skills: {len(user_skills)}")

        # Offres pas encore scorées pour cet utilisateur
        offers = session.execute(
            text("""
                SELECT o.* FROM offers o
                WHERE o.is_active = true
                AND o.id NOT IN (
                    SELECT offer_id FROM offer_matches WHERE user_id = :uid
                )
            """),
            {"uid": user_id},
        ).fetchall()

        logger.info(f"{len(offers)} offres à scorer")

        scored = 0
        matched = 0
        for offer in offers:
            offer_dict = {
                "title": offer.title or "",
                "description": offer.description or "",
                "company_name": offer.company_name or "",
                "location": offer.location,
                "domain": offer.domain,
                "start_date": offer.start_date,
                "required_education": offer.required_education,
                "salary": offer.salary,
                "contact_email": offer.contact_email,
                "duration_months": offer.duration_months,
                "required_skills": list(offer.required_skills or []),
            }
            result = score_offer_multidim(
                offer=offer_dict,
                preferences=prefs_dict,
                cv_tokens=cv_tokens,
                user_skills=user_skills,
                weights=weights,
            )

            score = result["score"]
            scored += 1

            if score >= min_score:
                session.execute(
                    text("""
                        INSERT INTO offer_matches (
                            user_id, offer_id, match_score, match_reasons,
                            ai_summary, created_at
                        ) VALUES (
                            :user_id, :offer_id, :score,
                            CAST(:reasons AS json), :summary, NOW()
                        )
                    """),
                    {
                        "user_id": user_id,
                        "offer_id": offer.id,
                        "score": score,
                        "reasons": json.dumps({
                            "dimensions": result["dimensions"],
                            "weights": result["weights"],
                        }),
                        "summary": result["analysis"],
                    },
                )
                matched += 1

        session.commit()

    logger.info(f"Scoring local terminé : {scored} offres, {matched} matches (>= {min_score})")

    # ── Passe IA Claude sur le top 30 (local_score >= 50, offres récentes) ──
    ia_stats = _run_ia_scoring_pass(user_id)

    logger.info(
        f"Scoring total : {scored} offres locales, {matched} matches local | "
        f"IA: {ia_stats['ia_success']} succès, {ia_stats['ia_fallback']} fallback"
    )
    return {
        "scored": scored,
        "matched": matched,
        "min_score": min_score,
        "ia_scored": ia_stats["ia_success"],
        "ia_fallback": ia_stats["ia_fallback"],
    }


def _run_ia_scoring_pass(user_id: str) -> dict:
    """Appelle Claude sur le top 30 des matches récents à local_score >= 50.

    Score combiné = 0.4 * local + 0.6 * IA.
    Budget : 30 offres/jour × ~$0.013 = ~$0.40/jour max.
    Fallback silencieux sur erreur API (on garde le score local).
    Marque ia_scored=True dans match_reasons pour ne pas retraiter.
    """
    import asyncio
    import json
    from app.services.claude_service import score_offer_match
    from app.services.scoring_service import recompute_global_score

    MAX_IA_OFFERS = 30
    MIN_LOCAL_SCORE = 50

    ia_success = 0
    ia_fallback = 0

    with Session(sync_engine) as session:
        # Charger le profil pour Claude
        u = session.execute(
            text("SELECT id, full_name, email, phone, linkedin_url FROM users WHERE id = :uid"),
            {"uid": user_id},
        ).first()
        if not u:
            return {"ia_success": 0, "ia_fallback": 0}

        prefs = session.execute(
            text("SELECT target_domains, target_locations, keywords, scoring_weights FROM search_preferences WHERE user_id = :uid"),
            {"uid": user_id},
        ).first()

        skills_rows = session.execute(
            text("SELECT skill_name FROM user_skills WHERE user_id = :uid"),
            {"uid": user_id},
        ).fetchall()

        cv_row = session.execute(
            text("SELECT extracted_text FROM user_documents WHERE user_id = :uid AND doc_type = 'cv' ORDER BY is_primary DESC LIMIT 1"),
            {"uid": user_id},
        ).first()

        profile = {
            "id": str(u.id),
            "full_name": u.full_name or "",
            "education": "",
            "skills": [r.skill_name for r in skills_rows],
            "cv_summary": (cv_row.extracted_text[:500] if cv_row and cv_row.extracted_text else ""),
            "cv_text": cv_row.extracted_text if cv_row and cv_row.extracted_text else "",
        }
        prefs_dict = {
            "target_domains": list(prefs.target_domains or []) if prefs else [],
            "target_locations": list(prefs.target_locations or []) if prefs else [],
            "keywords": list(prefs.keywords or []) if prefs else [],
        }
        scoring_weights = prefs.scoring_weights if (prefs and prefs.scoring_weights) else None

        # Sélection : top 30 par récence + score, filtré sur local>=50, pas encore IA-scoré
        candidates = session.execute(
            text(f"""
                SELECT m.id AS match_id, m.match_score AS local_score, m.match_reasons,
                       o.id AS offer_id, o.title, o.description, o.company_name,
                       o.location, o.domain, o.required_skills
                FROM offer_matches m
                JOIN offers o ON o.id = m.offer_id
                WHERE m.user_id = :uid
                  AND m.match_score >= :minscore
                  AND o.scraped_at > NOW() - INTERVAL '36 hours'
                  AND COALESCE(m.match_reasons->>'ia_scored', 'false') = 'false'
                ORDER BY o.scraped_at DESC, m.match_score DESC
                LIMIT :maxoffers
            """),
            {"uid": user_id, "minscore": MIN_LOCAL_SCORE, "maxoffers": MAX_IA_OFFERS},
        ).fetchall()

        logger.info(f"Scoring IA : {len(candidates)} offres candidates (max {MAX_IA_OFFERS})")

        for cand in candidates:
            offer_dict = {
                "id": str(cand.offer_id),
                "title": cand.title or "",
                "company_name": cand.company_name or "",
                "location": cand.location or "",
                "description": cand.description or "",
                "domain": cand.domain or "",
                "required_skills": list(cand.required_skills or []),
            }

            try:
                result = asyncio.run(score_offer_match(profile, prefs_dict, offer_dict))
                claude_score = float(result.get("match_score", 0))
                summary = result.get("summary", "")
            except Exception as e:
                logger.warning(f"Scoring IA fallback pour offre {cand.offer_id}: {e}")
                ia_fallback += 1
                continue

            existing_reasons = cand.match_reasons or {}
            if isinstance(existing_reasons, str):
                try:
                    existing_reasons = json.loads(existing_reasons)
                except json.JSONDecodeError:
                    existing_reasons = {}

            # Si match multi-dim, injecter la dim "ai" et recalculer le global pondéré.
            # Sinon (match legacy mono-dim), fallback sur l'ancienne formule 40/60.
            dims = existing_reasons.get("dimensions") if isinstance(existing_reasons, dict) else None
            if isinstance(dims, dict):
                dims["ai"] = int(round(claude_score))
                weights = existing_reasons.get("weights") or scoring_weights
                combined = recompute_global_score(dims, weights)
                existing_reasons["dimensions"] = dims
                if weights:
                    existing_reasons["weights"] = weights
            else:
                combined = round(0.4 * float(cand.local_score) + 0.6 * claude_score)

            merged = {
                **existing_reasons,
                "ia_scored": True,
                "local_score": float(cand.local_score),
                "claude_score": claude_score,
                "claude_highlights": result.get("highlights", []),
                "claude_concerns": result.get("concerns", []),
                "claude_sub_scores": result.get("sub_scores", {}),
            }

            session.execute(
                text("""
                    UPDATE offer_matches
                    SET match_score = :score,
                        ai_summary = :summary,
                        match_reasons = CAST(:reasons AS json)
                    WHERE id = :mid
                """),
                {
                    "score": combined,
                    "summary": summary,
                    "reasons": json.dumps(merged),
                    "mid": cand.match_id,
                },
            )
            ia_success += 1

        session.commit()

    return {"ia_success": ia_success, "ia_fallback": ia_fallback}


@celery_app.task(name="app.services.scraping_tasks.rescore_user_matches")
def rescore_user_matches(user_id: str):
    """Rescore TOUS les matches existants d'un utilisateur avec les critères/poids courants.

    N'efface RIEN : UPDATE en place de match_score + match_reasons.
    Préserve la dimension `ai` et les champs Claude déjà calculés (ia_scored, claude_score,
    claude_highlights, claude_concerns) — seul le score global et les 7 autres dimensions
    sont recalculés. Le `match_reasons.weights` est aussi mis à jour.
    """
    from app.services.scoring_service import score_offer_multidim, recompute_global_score
    from app.services.cv_extraction import tokenize_for_matching
    import json

    logger.info(f"Rescore matches pour user {user_id}…")

    with Session(sync_engine) as session:
        prefs = session.execute(
            text("SELECT * FROM search_preferences WHERE user_id = :uid"),
            {"uid": user_id},
        ).first()
        if not prefs:
            return {"status": "no_preferences"}

        prefs_dict = {
            "target_domains": list(prefs.target_domains or []),
            "target_locations": list(prefs.target_locations or []),
            "target_companies": list(prefs.target_companies or []),
            "keywords": list(prefs.keywords or []),
            "excluded_keywords": list(prefs.excluded_keywords or []),
            "start_date_earliest": prefs.start_date_earliest,
            "start_date_latest": prefs.start_date_latest,
        }
        weights = prefs.scoring_weights or None
        min_score = prefs.min_match_score or 0

        cv_row = session.execute(
            text("SELECT extracted_text FROM user_documents WHERE user_id = :uid AND doc_type = 'cv' ORDER BY is_primary DESC LIMIT 1"),
            {"uid": user_id},
        ).first()
        cv_tokens = tokenize_for_matching(cv_row.extracted_text) if cv_row and cv_row.extracted_text else None

        skills_rows = session.execute(
            text("SELECT skill_name FROM user_skills WHERE user_id = :uid"),
            {"uid": user_id},
        ).fetchall()
        user_skills = [r.skill_name for r in skills_rows]

        matches = session.execute(
            text("""
                SELECT m.id AS mid, m.match_reasons,
                       o.id AS oid, o.title, o.description, o.company_name, o.location,
                       o.domain, o.start_date, o.required_education, o.salary,
                       o.contact_email, o.duration_months, o.required_skills
                FROM offer_matches m JOIN offers o ON o.id=m.offer_id
                WHERE m.user_id=:uid
            """),
            {"uid": user_id},
        ).fetchall()

        logger.info(f"Rescore : {len(matches)} matches à recalculer")
        updated = 0

        for m in matches:
            offer_dict = {
                "title": m.title or "",
                "description": m.description or "",
                "company_name": m.company_name or "",
                "location": m.location,
                "domain": m.domain,
                "start_date": m.start_date,
                "required_education": m.required_education,
                "salary": m.salary,
                "contact_email": m.contact_email,
                "duration_months": m.duration_months,
                "required_skills": list(m.required_skills or []),
            }
            result = score_offer_multidim(
                offer=offer_dict, preferences=prefs_dict,
                cv_tokens=cv_tokens, user_skills=user_skills, weights=weights,
            )

            # Préserver les champs Claude déjà calculés
            existing = m.match_reasons or {}
            if isinstance(existing, str):
                try: existing = json.loads(existing)
                except json.JSONDecodeError: existing = {}

            dims = result["dimensions"]
            if existing.get("ia_scored") and "claude_score" in existing:
                dims["ai"] = int(round(float(existing["claude_score"])))
                final_score = recompute_global_score(dims, result["weights"])
            else:
                final_score = result["score"]

            merged = {
                **existing,
                "dimensions": dims,
                "weights": result["weights"],
            }

            # UPDATE en place, jamais de DELETE.
            # Le seuil min_match_score est appliqué côté frontend (bandeau / filtre).
            session.execute(
                text("UPDATE offer_matches SET match_score=:s, match_reasons=CAST(:r AS json) WHERE id=:id"),
                {"s": final_score, "r": json.dumps(merged), "id": m.mid},
            )
            updated += 1

        session.commit()

    # Ramener aussi les offres nouvelles (pas encore matchées)
    score_all_offers.delay(user_id)

    logger.info(f"Rescore terminé : {updated} matches mis à jour (min_score={min_score} appliqué côté UI)")
    return {"updated": updated, "min_score": min_score}


@celery_app.task(name="app.services.scraping_tasks.check_integration_cookies")
def check_integration_cookies():
    """Verifie la validite des cookies d'integration (JobTeaser, etc.)."""
    import httpx

    logger.info("Verification des cookies d'integration...")

    with Session(sync_engine) as session:
        integrations = session.execute(
            text("SELECT id, service_name, service_url, session_cookie, session_expires_at FROM user_integrations WHERE is_active = true")
        ).fetchall()

        for integ in integrations:
            try:
                base = (integ.service_url or "").rstrip("/")
                if not base or not integ.session_cookie:
                    continue

                with httpx.Client(timeout=15, follow_redirects=True) as client:
                    r = client.get(f"{base}/fr/job-offers", headers={
                        "User-Agent": "Mozilla/5.0",
                        "Cookie": integ.session_cookie,
                    })

                    if r.status_code != 200 or "sign_in" in str(r.url):
                        logger.warning(f"Cookie {integ.service_name} expire ou invalide — desactivation")
                        session.execute(
                            text("UPDATE user_integrations SET is_active = false WHERE id = :id"),
                            {"id": integ.id},
                        )
                    else:
                        logger.info(f"Cookie {integ.service_name} toujours valide")

            except Exception as e:
                logger.warning(f"Erreur verification cookie {integ.service_name}: {e}")

        session.commit()

    return {"status": "checked", "integrations": len(integrations)}


def _save_offers(offers) -> int:
    """Sauvegarde les offres en BDD (upsert : ignore les doublons)."""
    new_count = 0

    with Session(sync_engine) as session:
        for offer in offers:
            # Vérifier si l'offre existe déjà
            exists = session.execute(
                text(
                    "SELECT 1 FROM offers WHERE source_platform = :platform AND external_id = :eid LIMIT 1"
                ),
                {"platform": offer.source_platform, "eid": offer.external_id},
            ).first()

            if exists:
                continue

            session.execute(
                text("""
                    INSERT INTO offers (
                        external_id, source_platform, source_url, title, company_name,
                        company_logo_url, description, location, is_remote, domain,
                        contract_type, duration_months, start_date, salary,
                        required_skills, required_education, contact_name, contact_email,
                        raw_data, scraped_at, is_active
                    ) VALUES (
                        :external_id, :source_platform, :source_url, :title, :company_name,
                        :company_logo_url, :description, :location, :is_remote, :domain,
                        :contract_type, :duration_months, :start_date, :salary,
                        :required_skills, :required_education, :contact_name, :contact_email,
                        CAST(:raw_data AS jsonb), NOW(), true
                    )
                """),
                {
                    "external_id": offer.external_id,
                    "source_platform": offer.source_platform,
                    "source_url": offer.source_url,
                    "title": offer.title,
                    "company_name": offer.company_name,
                    "company_logo_url": offer.company_logo_url,
                    "description": offer.description,
                    "location": offer.location,
                    "is_remote": offer.is_remote,
                    "domain": offer.domain,
                    "contract_type": offer.contract_type,
                    "duration_months": offer.duration_months,
                    "start_date": offer.start_date,
                    "salary": offer.salary,
                    "required_skills": offer.required_skills or [],
                    "required_education": offer.required_education,
                    "contact_name": offer.contact_name,
                    "contact_email": offer.contact_email,
                    "raw_data": __import__("json").dumps(offer.raw_data or {}),
                },
            )
            new_count += 1

        session.commit()

    return new_count
