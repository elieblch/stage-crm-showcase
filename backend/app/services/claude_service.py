"""
Service IA Claude — scoring, génération LM, emails, CV, entretiens.
Tous les appels sont loggés (modèle, tokens, durée) avec try/except + fallback.
Cache Redis pour le scoring (TTL 48h).
"""

import json
import re
import time
import hashlib
import logging

import anthropic
import redis

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
MODEL = settings.claude_model  # claude-sonnet-4-6

# Redis cache
try:
    rcache = redis.from_url(settings.redis_url, decode_responses=True)
except Exception:
    rcache = None

CACHE_TTL = 48 * 3600  # 48h


def _cache_key(prefix: str, *parts: str) -> str:
    h = hashlib.md5("|".join(parts).encode()).hexdigest()[:16]
    return f"claude:{prefix}:{h}"


def _call_claude(prompt: str, max_tokens: int = 1500, system: str | None = None) -> str:
    """Appel Claude avec logging. Retourne le texte brut."""
    start = time.time()
    msgs = [{"role": "user", "content": prompt}]
    kwargs = {"model": MODEL, "max_tokens": max_tokens, "messages": msgs}
    if system:
        kwargs["system"] = system

    response = client.messages.create(**kwargs)
    elapsed = time.time() - start

    logger.info(
        f"Claude call: model={response.model}, "
        f"tokens={response.usage.input_tokens}in/{response.usage.output_tokens}out, "
        f"duration={elapsed:.1f}s"
    )
    return response.content[0].text


def _parse_json(text: str) -> dict | None:
    """Parse du JSON depuis une réponse Claude (gère les blocs ```json et les sorties partielles)."""
    if not text:
        return None
    cleaned = text.strip()
    # Retirer les fences markdown ```json ou ```
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"```\s*$", "", cleaned)
        cleaned = cleaned.strip()
    # Tentative directe
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    # Extraire le premier objet complet { … }
    start = cleaned.find("{")
    if start < 0:
        return None
    end = cleaned.rfind("}") + 1
    if end > start:
        try:
            return json.loads(cleaned[start:end])
        except json.JSONDecodeError:
            pass
    # Dernier recours : JSON tronqué (max_tokens hit). On tente de fermer les brackets.
    truncated = cleaned[start:]
    opens = truncated.count("{") - truncated.count("}")
    arr_opens = truncated.count("[") - truncated.count("]")
    if opens > 0 or arr_opens > 0:
        # Couper à la dernière virgule de niveau racine pour éviter les items incomplets
        last_complete = max(truncated.rfind('",'), truncated.rfind("},"), truncated.rfind("],"))
        if last_complete > 0:
            candidate = truncated[:last_complete + 1] + ("]" * arr_opens) + ("}" * opens)
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                pass
    return None


# ══════════════════════════════════════════════════════════
# 1. SCORING IA
# ══════════════════════════════════════════════════════════

async def score_offer_match(
    user_profile: dict,
    preferences: dict,
    offer: dict,
) -> dict:
    """Score IA d'une offre. Cache Redis 48h."""
    offer_id = offer.get("id", "")
    user_id = user_profile.get("id", "")
    cache_k = _cache_key("score", str(user_id), str(offer_id))

    # Check cache
    if rcache:
        try:
            cached = rcache.get(cache_k)
            if cached:
                return json.loads(cached)
        except Exception:
            pass

    prompt = f"""Tu es un assistant expert en recrutement finance/conseil/stratégie.
Analyse la correspondance entre ce candidat et cette offre. Réponds en français.

## Candidat
- Nom : {user_profile.get('full_name', '')}
- Formation : {user_profile.get('education', '')}
- Compétences : {', '.join(user_profile.get('skills', [])[:15])}
- Résumé CV : {user_profile.get('cv_summary', '')[:500]}

## Préférences
- Domaines : {', '.join(preferences.get('target_domains', []))}
- Localisations : {', '.join(preferences.get('target_locations', []))}
- Mots-clés : {', '.join(preferences.get('keywords', [])[:10])}

## Offre
- Titre : {offer.get('title', '')}
- Entreprise : {offer.get('company_name', '')}
- Localisation : {offer.get('location', 'Non précisée')}
- Description : {(offer.get('description') or '')[:1500]}

Réponds UNIQUEMENT en JSON :
{{"match_score": <0-100>, "summary": "<2-3 phrases en français expliquant le matching>", "highlights": ["<atout1>", "<atout2>"], "concerns": ["<point faible>"], "sub_scores": {{"domain": <0-100>, "company": <0-100>, "location": <0-100>, "skills": <0-100>, "education": <0-100>}}}}"""

    try:
        text = _call_claude(prompt, max_tokens=500)
        result = _parse_json(text)
        if not result or "match_score" not in result:
            result = {"match_score": 50, "summary": text[:200], "highlights": [], "concerns": []}
    except Exception as e:
        logger.error(f"Claude scoring error: {e}")
        return {"match_score": 50, "summary": "Analyse IA non disponible.", "highlights": [], "concerns": []}

    # Cache
    if rcache:
        try:
            rcache.setex(cache_k, CACHE_TTL, json.dumps(result))
        except Exception:
            pass

    return result


# ══════════════════════════════════════════════════════════
# 2. LETTRE DE MOTIVATION
# ══════════════════════════════════════════════════════════

async def generate_cover_letter(
    user_profile: dict,
    offer: dict,
    tone: str = "professionnel",
) -> str:
    """Génère une lettre de motivation personnalisée."""
    system = """Tu es un expert en rédaction de candidatures pour des stages en finance, conseil et stratégie.
Tu rédiges des lettres de motivation percutantes, personnalisées et structurées.
Tu écris en français sauf si l'offre est en anglais."""

    projects = user_profile.get('projects_summary', '')
    projects_section = f"\n\n## Projets et documents complementaires\n{projects[:2000]}" if projects else ""

    prompt = f"""Rédige une lettre de motivation pour cette candidature.

## Candidat
- Nom : {user_profile.get('full_name', '')}
- Email : {user_profile.get('email', '')}
- Téléphone : {user_profile.get('phone', '')}
- Formation : {user_profile.get('education', '')}
- Compétences : {', '.join(user_profile.get('skills', [])[:15])}
- Expériences : {user_profile.get('cv_text', '')[:2000]}{projects_section}

## Offre
- Poste : {offer.get('title', '')}
- Entreprise : {offer.get('company_name', '')}
- Description : {(offer.get('description') or '')[:2500]}
- Compétences demandées : {', '.join(offer.get('required_skills', []))}

## Consignes
- Ton : {tone}
- Structure : accroche marquante → pourquoi cette entreprise → ce que j'apporte → conclusion avec call-to-action
- ~350 mots, personnalisé au maximum
- Mets en avant les compétences qui matchent l'offre"""

    try:
        return _call_claude(prompt, max_tokens=2000, system=system)
    except Exception as e:
        logger.error(f"Claude cover letter error: {e}")
        return f"Erreur lors de la génération : {e}"


# ══════════════════════════════════════════════════════════
# 3. DRAFT EMAIL
# ══════════════════════════════════════════════════════════

async def generate_email_draft(
    user_profile: dict,
    offer: dict,
    email_type: str = "candidature",
) -> dict:
    """Génère un brouillon d'email structuré."""
    type_desc = {
        "candidature": "Email de candidature. Objet accrocheur, corps concis et professionnel.",
        "relance": "Email de relance 7-10 jours après candidature. Poli, bref, montre l'intérêt.",
        "remerciement": "Email de remerciement post-entretien. Personnalisé.",
    }

    prompt = f"""Rédige un email de type "{email_type}" pour un stage.

{type_desc.get(email_type, '')}

## Candidat
- Nom : {user_profile.get('full_name', '')}
- Email : {user_profile.get('email', '')}
- Téléphone : {user_profile.get('phone', '')}
- LinkedIn : {user_profile.get('linkedin_url', '')}
- Formation : {user_profile.get('education', '')}

## Offre
- Poste : {offer.get('title', '')}
- Entreprise : {offer.get('company_name', '')}
- Contact : {offer.get('contact_name', 'Madame, Monsieur')}

## Consignes
- Inclure une signature professionnelle (nom, formation, tel, LinkedIn)
- Langue : français sauf si offre anglophone

Réponds en JSON :
{{"subject": "<objet>", "body": "<corps complet avec signature>", "recipients": ["{offer.get('contact_email', '')}"]}}"""

    try:
        text = _call_claude(prompt, max_tokens=1500)
        result = _parse_json(text)
        if result:
            return result
        return {"subject": "", "body": text, "recipients": []}
    except Exception as e:
        logger.error(f"Claude email error: {e}")
        return {"subject": "", "body": f"Erreur : {e}", "recipients": []}


# ══════════════════════════════════════════════════════════
# 4. SUGGESTIONS CV
# ══════════════════════════════════════════════════════════

async def suggest_cv_adaptations(
    cv_text: str,
    offer: dict,
) -> dict:
    """Suggère des adaptations du CV pour une offre."""
    prompt = f"""Tu es un expert en optimisation de CV pour des stages en finance/conseil.

## CV actuel
{cv_text[:3500]}

## Projets et realisations supplementaires (a valoriser si pertinent)
{offer.get('_projects_summary', '')[:1500]}

## Offre ciblée
- Poste : {offer.get('title', '')}
- Entreprise : {offer.get('company_name', '')}
- Description : {(offer.get('description') or '')[:1500]}
- Compétences : {', '.join(offer.get('required_skills', []))}

Réponds en JSON :
{{"overall_assessment": "<évaluation globale>", "adaptations": [{{"section": "<section>", "current": "<actuel>", "suggested": "<suggestion>", "priority": "high|medium|low", "rationale": "<pourquoi>"}}], "keywords_to_add": ["<mot-clé>"]}}"""

    try:
        text = _call_claude(prompt, max_tokens=2000)
        result = _parse_json(text)
        if result:
            return result
        return {"overall_assessment": text[:500], "adaptations": [], "keywords_to_add": []}
    except Exception as e:
        logger.error(f"Claude CV suggestions error: {e}")
        return {"overall_assessment": f"Erreur : {e}", "adaptations": [], "keywords_to_add": []}


# ══════════════════════════════════════════════════════════
# 5. PRÉPARATION ENTRETIEN
# ══════════════════════════════════════════════════════════

# Mapping domaine offre → tags STAR à filtrer en priorité
_DOMAIN_TO_TAGS: dict[str, list[str]] = {
    "finance": ["finance", "quantitatif", "technical", "problem_solving"],
    "conseil": ["problem_solving", "communication", "leadership", "gestion_projet"],
    "audit": ["technical", "problem_solving", "communication"],
    "risk": ["quantitatif", "technical", "problem_solving"],
}


def _select_relevant_stories(stories: list[dict], offer_domain: str, max_n: int = 5) -> list[dict]:
    """Filtre stories par tags correspondant au domaine. Fallback : 5 plus récentes."""
    if not stories:
        return []
    dom = (offer_domain or "").lower().strip()
    target_tags = set()
    for key, tags in _DOMAIN_TO_TAGS.items():
        if key in dom:
            target_tags.update(tags)

    if target_tags:
        matching = [s for s in stories if any(t in target_tags for t in (s.get("tags") or []))]
        if matching:
            return matching[:max_n]
    # Fallback : 5 plus récentes (stories est déjà triée desc par updated_at côté appelant)
    return stories[:max_n]


async def generate_interview_prep(
    user_profile: dict,
    offer: dict,
    interview_type: str = "general",
    user_stories: list[dict] | None = None,
) -> dict:
    """Génère une fiche de préparation d'entretien complète.

    `user_stories` : liste facultative de stories STAR de l'utilisateur ; sera
    filtrée par pertinence puis injectée dans le prompt. Si vide, Claude
    suggère des types de stories à créer.
    """
    stories = _select_relevant_stories(user_stories or [], offer.get("domain") or "")
    if stories:
        stories_section = "\n\n## Stories STAR disponibles (à mobiliser dans les réponses)\n" + "\n\n".join(
            f"### {s['title']} (tags: {', '.join(s.get('tags', []) or ['-'])})\n"
            f"- Situation: {(s.get('situation') or '')[:300]}\n"
            f"- Task: {(s.get('task') or '')[:200]}\n"
            f"- Action: {(s.get('action') or '')[:300]}\n"
            f"- Result: {(s.get('result') or '')[:200]}"
            for s in stories
        )
        stories_instructions = (
            "L'utilisateur dispose des stories ci-dessus. Pour chaque question où c'est pertinent, "
            "référence par son TITRE la story à mobiliser dans `suggested_answer`, "
            "en intégrant Situation/Task/Action/Result de façon naturelle. "
            "Liste aussi dans `stories_to_prepare` les thèmes pour lesquels l'utilisateur n'a PAS encore de story adaptée."
        )
    else:
        stories_section = ""
        stories_instructions = (
            "L'utilisateur n'a PAS de story STAR enregistrée. "
            "Dans `stories_to_prepare`, liste 3 à 5 thèmes pour lesquels il devrait préparer des stories "
            "(ex: leadership, gestion de projet technique, travail en équipe sous pression, initiative, adaptabilité), "
            "avec une brève justification de pertinence pour ce poste spécifique."
        )

    prompt = f"""Prépare une fiche d'entretien complète pour un stage en {offer.get('domain', 'finance/conseil')}.

Type : {interview_type}
Poste : {offer.get('title', '')}
Entreprise : {offer.get('company_name', '')}
Description : {(offer.get('description') or '')[:1500]}

Candidat :
- Formation : {user_profile.get('education', '')}
- Compétences : {', '.join(user_profile.get('skills', [])[:10])}
- Projets pertinents : {user_profile.get('projects_summary', '')[:1000]}
{stories_section}

## Consignes
{stories_instructions}

Réponds en JSON :
{{"company_research": "<recherche entreprise: histoire, culture, actualités>", "common_questions": [{{"question": "<question>", "suggested_answer": "<piste de réponse — référence le titre exact d'une story si pertinent>", "story_to_use": "<titre de story à mobiliser, ou null>"}}], "technical_prep": "<préparation technique spécifique>", "questions_to_ask": ["<question à poser>"], "dos_and_donts": {{"do": ["<conseil>"], "dont": ["<erreur>"]}}, "stories_to_prepare": [{{"theme": "<leadership/teamwork/...>", "why": "<pourquoi pertinent pour ce poste>"}}]}}"""

    try:
        text = _call_claude(prompt, max_tokens=5000)
        result = _parse_json(text)
        if result:
            # Garantir la présence du champ stories_to_prepare
            result.setdefault("stories_to_prepare", [])
            return result
        logger.warning(f"Claude interview_prep: parse JSON échoué, raw len={len(text)}")
        return {"company_research": text[:500], "common_questions": [], "technical_prep": "", "questions_to_ask": [], "dos_and_donts": {"do": [], "dont": []}, "stories_to_prepare": []}
    except Exception as e:
        logger.error(f"Claude interview prep error: {e}")
        return {"company_research": f"Erreur : {e}", "common_questions": [], "technical_prep": "", "questions_to_ask": [], "dos_and_donts": {"do": [], "dont": []}, "stories_to_prepare": []}
