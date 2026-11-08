"""
Service de scoring des offres par rapport au profil utilisateur.
Score combiné : 40% préférences + 60% matching CV/offre.
"""

import re
import logging
from datetime import date, timedelta

from app.services.cv_extraction import tokenize_for_matching

logger = logging.getLogger(__name__)

# ── Mots-clés pondérés (scoring préférences) ──────────────

KEYWORD_WEIGHTS = {
    "trading": 15, "trader": 15, "sales & trading": 20, "sales and trading": 20,
    "front office": 15, "salle de marché": 15, "salle des marchés": 15,
    "finance de marché": 20, "marchés financiers": 15,
    "dérivés": 12, "produits dérivés": 15, "options": 8, "futures": 10,
    "fixed income": 15, "taux": 8, "equity": 10, "equities": 10,
    "structuration": 15, "produits structurés": 15,
    "pricing": 12, "valorisation": 10,
    "quantitatif": 12, "quant": 12, "modélisation": 10,
    "risk management": 12, "risque de marché": 15, "risques de marché": 15,
    "var": 8, "p&l": 10, "pnl": 10,
    "m&a": 12, "fusion": 10, "acquisition": 10,
    "private equity": 12, "leveraged finance": 12,
    "debt capital markets": 12, "equity capital markets": 12,
    "dcm": 10, "ecm": 10, "ipo": 8,
    "conseil en stratégie": 12, "strategy consulting": 12, "due diligence": 10,
    "python": 5, "vba": 5, "excel": 3, "bloomberg": 8,
    "reuters": 5, "sql": 3, "c++": 5, "matlab": 5, "r": 3,
}

NEGATIVE_KEYWORDS = {
    "comptabilité": -15, "audit légal": -15, "commissariat aux comptes": -15,
    "contrôle de gestion": -10, "back office": -12, "middle office": -5,
    "ressources humaines": -20, "marketing": -15, "communication": -15,
    "supply chain": -20, "logistique": -20, "développeur": -10, "devops": -15,
}

TARGET_COMPANIES = {
    "société générale": 10, "bnp paribas": 10, "natixis": 10,
    "crédit agricole": 8, "hsbc": 10, "jp morgan": 12, "jpmorgan": 12,
    "goldman sachs": 12, "morgan stanley": 12, "barclays": 10,
    "deutsche bank": 10, "citi": 10, "citigroup": 10,
    "rothschild": 12, "lazard": 12,
    "amundi": 8, "axa im": 8, "axa investment": 8, "bnp am": 8,
    "mckinsey": 10, "bcg": 10, "bain": 10, "oliver wyman": 10, "roland berger": 8,
    "messier maris": 10, "perella weinberg": 10,
}


# Poids par défaut pour le scoring multi-dimensions (doivent sommer à 100)
DEFAULT_SCORING_WEIGHTS: dict[str, int] = {
    "domain": 20, "company": 15, "location": 10, "skills": 20,
    "education": 10, "quality": 10, "timing": 10, "ai": 5,
}

# Heuristique formation : mots-clés détectés dans les descriptions d'offres
EDUCATION_MATCH_KEYWORDS = {
    "bac+5", "bac +5", "bac + 5", "grande école", "grande ecole",
    "master", "mastère", "mba", "ingénieur", "ingenieur", "école de commerce",
    "ecole de commerce", "business school", "engineering school",
}
EDUCATION_MISMATCH_KEYWORDS = {
    "bac+2", "bac +2", "bac + 2", "bac+3", "bac +3", "bac + 3",
    "bts", "dut", "licence professionnelle", "licence pro",
}


# ══════════════════════════════════════════════════════════
# SCORE COMBINÉ
# ══════════════════════════════════════════════════════════

def score_offer(
    offer_title: str,
    offer_description: str | None,
    offer_company: str,
    offer_location: str | None,
    offer_domain: str | None,
    target_domains: list[str],
    target_locations: list[str],
    keywords: list[str],
    excluded_keywords: list[str],
    start_date_earliest: date | None = None,
    offer_start_date: date | None = None,
    cv_tokens: set[str] | None = None,
    user_skills: list[str] | None = None,
) -> dict:
    """
    Score combiné : 40% préférences + 60% matching CV/offre.
    Si cv_tokens est None, fallback 100% préférences.
    """
    # Filtre date
    if start_date_earliest and offer_start_date:
        window_start = start_date_earliest - timedelta(days=30)
        window_end = start_date_earliest + timedelta(days=90)
        if offer_start_date < window_start or offer_start_date > window_end:
            return {
                "score": -1, "breakdown": {},
                "matched_keywords": [], "matched_negatives": [],
                "analysis": f"Date de debut ({offer_start_date}) hors fenetre ({window_start} - {window_end}).",
                "excluded_reason": "date_hors_fenetre",
            }

    # Score préférences (0-100)
    pref_result = _score_preferences(
        offer_title, offer_description, offer_company,
        offer_location, offer_domain,
        target_domains, target_locations, keywords, excluded_keywords,
    )
    pref_score = pref_result["score"]

    # Score CV/offre (0-100)
    if cv_tokens and len(cv_tokens) > 0:
        cv_result = _score_cv_match(
            offer_title, offer_description, offer_company,
            cv_tokens, user_skills or [],
        )
        cv_score = cv_result["score"]
        # Combiné : 80% pref + 20% CV (cohérence)
        final_score = int(0.8 * pref_score + 0.2 * cv_score)
        breakdown = {
            **pref_result["breakdown"],
            "cv_skills_match": cv_result["skills_matched"],
            "cv_token_overlap": cv_result["token_overlap_pct"],
            "cv_score": cv_score,
            "pref_score": pref_score,
        }
        cv_analysis = cv_result["analysis"]
    else:
        final_score = pref_score
        breakdown = {**pref_result["breakdown"], "cv_score": 0, "pref_score": pref_score}
        cv_analysis = ""

    final_score = max(0, min(100, final_score))

    analysis = _generate_analysis(
        final_score, pref_result["matched_keywords"], pref_result["matched_negatives"],
        pref_result["breakdown"].get("company_bonus", 0) > 0,
        pref_result["breakdown"].get("location_match", 0) > 0,
        offer_title, offer_company, cv_analysis,
    )

    return {
        "score": final_score,
        "breakdown": breakdown,
        "matched_keywords": pref_result["matched_keywords"],
        "matched_negatives": pref_result["matched_negatives"],
        "analysis": analysis,
    }


# ══════════════════════════════════════════════════════════
# SCORING PRÉFÉRENCES (inchangé, 0-100)
# ══════════════════════════════════════════════════════════

def _score_preferences(
    offer_title: str, offer_description: str | None, offer_company: str,
    offer_location: str | None, offer_domain: str | None,
    target_domains: list[str], target_locations: list[str],
    keywords: list[str], excluded_keywords: list[str],
) -> dict:
    text = f"{offer_title} {offer_description or ''}".lower()
    company_lower = offer_company.lower()

    points = 0
    breakdown = {"keywords_match": 0, "company_bonus": 0, "location_match": 0, "domain_match": 0, "negative_penalty": 0}
    matched_keywords = []
    matched_negatives = []

    # 1. Mots-clés (max 65)
    for kw, weight in KEYWORD_WEIGHTS.items():
        if kw.lower() in text:
            points += weight
            matched_keywords.append(kw)
    for kw in keywords:
        if kw.lower() in text and kw.lower() not in KEYWORD_WEIGHTS:
            points += 5
            matched_keywords.append(kw)
    breakdown["keywords_match"] = min(points, 65)
    points = min(points, 65)

    # 2. Entreprise cible (max 15)
    company_bonus = 0
    for company, bonus in TARGET_COMPANIES.items():
        if company in company_lower:
            company_bonus = max(company_bonus, bonus)
    breakdown["company_bonus"] = min(company_bonus, 15)
    points += min(company_bonus, 15)

    # 3. Localisation (max 15)
    location_score = 0
    if offer_location and target_locations:
        for loc in target_locations:
            if loc.lower() in offer_location.lower():
                location_score = 15
                break
    elif not offer_location:
        location_score = 8  # neutre si non précisé (beaucoup d'offres sans loc)
    breakdown["location_match"] = location_score
    points += location_score

    # 4. Domaine (max 15)
    domain_score = 0
    if offer_domain:
        for td in target_domains:
            if td.lower() in offer_domain.lower():
                domain_score = 15
                break
            elif any(w in offer_domain.lower() for w in ["finance", "banque", "trading"]):
                domain_score = 10
                break
    breakdown["domain_match"] = domain_score
    points += domain_score

    # 5. Pénalités
    penalty = 0
    for kw, pen in NEGATIVE_KEYWORDS.items():
        if kw in text:
            penalty += pen
            matched_negatives.append(kw)
    for kw in excluded_keywords:
        if kw.lower() in text and kw.lower() not in NEGATIVE_KEYWORDS:
            penalty -= 10
            matched_negatives.append(kw)
    breakdown["negative_penalty"] = penalty
    points += penalty

    return {
        "score": max(0, min(100, points)),
        "breakdown": breakdown,
        "matched_keywords": matched_keywords,
        "matched_negatives": matched_negatives,
    }


# ══════════════════════════════════════════════════════════
# SCORING CV/OFFRE (nouveau, 0-100)
# ══════════════════════════════════════════════════════════

def _score_cv_match(
    offer_title: str,
    offer_description: str | None,
    offer_company: str,
    cv_tokens: set[str],
    user_skills: list[str],
) -> dict:
    """
    Score le matching entre le CV et une offre.
    Combine : overlap de tokens + matching de skills explicites.
    """
    offer_text = f"{offer_title} {offer_description or ''} {offer_company}"
    offer_tokens = tokenize_for_matching(offer_text)

    if not offer_tokens or not cv_tokens:
        return {"score": 0, "skills_matched": 0, "token_overlap_pct": 0, "analysis": ""}

    # 1. Token overlap (Jaccard-like mais pondéré par la taille de l'offre)
    # On mesure : quelle proportion des tokens de l'offre sont dans le CV
    overlap = offer_tokens & cv_tokens
    overlap_pct = len(overlap) / len(offer_tokens) * 100 if offer_tokens else 0

    # 2. Skills matching : combien de skills du user apparaissent dans l'offre
    skills_lower = {s.lower() for s in user_skills}
    offer_text_lower = offer_text.lower()
    skills_matched = sum(1 for s in skills_lower if s in offer_text_lower)
    skills_total = len(skills_lower) if skills_lower else 1
    skills_pct = skills_matched / skills_total * 100

    # Score combiné : 50% overlap + 50% skills match
    # Normaliser l'overlap (30% overlap = bon score)
    overlap_score = min(100, overlap_pct * 3.3)  # 30% overlap → 100
    skills_score = min(100, skills_pct * 5)       # 20% skills match → 100

    cv_score = int(0.5 * overlap_score + 0.5 * skills_score)

    # Analyse
    analysis_parts = []
    if skills_matched > 0:
        matched_names = [s for s in user_skills if s.lower() in offer_text_lower][:5]
        analysis_parts.append(f"CV: {skills_matched} competences en commun ({', '.join(matched_names)})")
    if overlap_pct > 15:
        analysis_parts.append(f"Vocabulaire commun: {overlap_pct:.0f}%")

    return {
        "score": max(0, min(100, cv_score)),
        "skills_matched": skills_matched,
        "token_overlap_pct": round(overlap_pct, 1),
        "analysis": ". ".join(analysis_parts),
    }


# ══════════════════════════════════════════════════════════
# ANALYSE TEXTUELLE
# ══════════════════════════════════════════════════════════

def _generate_analysis(
    score: int, matched_kw: list[str], matched_neg: list[str],
    is_target_company: bool, location_match: bool,
    title: str, company: str, cv_analysis: str,
) -> str:
    parts = []

    if score >= 75:
        parts.append(f"Excellente correspondance pour '{title}' chez {company}.")
    elif score >= 50:
        parts.append(f"Bonne correspondance pour '{title}' chez {company}.")
    elif score >= 30:
        parts.append(f"Correspondance moyenne pour '{title}' chez {company}.")
    else:
        parts.append(f"Faible correspondance pour '{title}' chez {company}.")

    if matched_kw:
        parts.append(f"Mots-cles: {', '.join(matched_kw[:5])}.")
    if is_target_company:
        parts.append("Entreprise cible.")
    if cv_analysis:
        parts.append(cv_analysis + ".")
    if matched_neg:
        parts.append(f"Penalites: {', '.join(matched_neg)}.")
    if not location_match:
        parts.append("Localisation non confirmee.")

    return " ".join(parts)


# ══════════════════════════════════════════════════════════
# SCORING MULTI-DIMENSIONS (8 axes)
# ══════════════════════════════════════════════════════════

def _dim_domain(offer_domain: str | None, offer_title: str, offer_desc: str,
                target_domains: list[str]) -> int:
    """Matching domaine (target_domains vs offer.domain + texte)."""
    if not target_domains:
        return 50
    haystack = f"{offer_domain or ''} {offer_title} {offer_desc}".lower()
    for td in target_domains:
        if td.lower() in haystack:
            return 100
    # Partial match : domaines proches
    fallback_map = {
        "finance": ["banque", "bank", "investment", "trading"],
        "conseil": ["consulting", "advisory", "strategy"],
        "audit": ["accounting", "comptab"],
    }
    for td in target_domains:
        for syn in fallback_map.get(td.lower(), []):
            if syn in haystack:
                return 60
    return 20


def _dim_company(offer_company: str, target_companies: list[str]) -> int:
    """Matching entreprise (prefs.target_companies + TARGET_COMPANIES globales)."""
    if not offer_company:
        return 30
    company_lower = offer_company.lower()
    # Préférences utilisateur en premier
    for tc in target_companies or []:
        if tc.lower() in company_lower:
            return 100
    # Liste globale finance/conseil
    for tc, _ in TARGET_COMPANIES.items():
        if tc in company_lower:
            return 80
    return 40


def _dim_location(offer_location: str | None, target_locations: list[str]) -> int:
    """Matching localisation."""
    if not offer_location:
        return 50  # neutre si non précisé
    if not target_locations:
        return 50
    loc_lower = offer_location.lower()
    for tl in target_locations:
        if tl.lower() in loc_lower:
            return 100
    if "remote" in loc_lower or "télétravail" in loc_lower:
        return 70
    return 20


def _dim_skills(offer_title: str, offer_desc: str, offer_company: str,
                cv_tokens: set[str] | None, user_skills: list[str] | None) -> int:
    """Matching compétences (reprend l'algo existant _score_cv_match)."""
    if not cv_tokens and not user_skills:
        return 0
    cv_result = _score_cv_match(
        offer_title, offer_desc, offer_company,
        cv_tokens or set(), user_skills or [],
    )
    return cv_result["score"]


def _dim_education(offer_description: str | None, offer_required_education: str | None) -> int:
    """Heuristique formation : match Bac+5/Grande école vs rejet Bac+2/BTS."""
    text = f"{offer_description or ''} {offer_required_education or ''}".lower()
    if not text.strip():
        return 50  # non précisé
    if any(kw in text for kw in EDUCATION_MISMATCH_KEYWORDS):
        return 0
    if any(kw in text for kw in EDUCATION_MATCH_KEYWORDS):
        return 100
    return 50


def _dim_quality(offer: dict) -> int:
    """Qualité/complétude de l'offre (sur 100)."""
    points = 0
    desc = offer.get("description") or ""
    if len(desc) > 200:
        points += 30
    if offer.get("salary"):
        points += 20
    if offer.get("contact_email"):
        points += 15
    if offer.get("start_date"):
        points += 15
    if offer.get("duration_months"):
        points += 10
    if offer.get("required_skills"):
        points += 10
    return min(points, 100)


def _dim_timing(offer_start_date: date | None,
                start_date_earliest: date | None,
                start_date_latest: date | None) -> int:
    """Timing : date de début de l'offre vs fenêtre utilisateur."""
    if not offer_start_date:
        return 60  # neutre
    if not start_date_earliest and not start_date_latest:
        return 60
    earliest = start_date_earliest or offer_start_date
    latest = start_date_latest or offer_start_date
    if earliest <= offer_start_date <= latest:
        return 100
    # Calcul du dépassement en jours
    overshoot = min(
        abs((offer_start_date - earliest).days) if offer_start_date < earliest else 10**6,
        abs((offer_start_date - latest).days) if offer_start_date > latest else 10**6,
    )
    if overshoot <= 30:
        return 70
    if overshoot <= 60:
        return 40
    return 0


def score_offer_multidim(
    offer: dict,
    preferences: dict,
    cv_tokens: set[str] | None = None,
    user_skills: list[str] | None = None,
    weights: dict | None = None,
) -> dict:
    """Scoring 8 dimensions avec poids configurables.

    `offer` doit contenir : title, description, company_name, location, domain,
    start_date, required_education, salary, contact_email, duration_months,
    required_skills.
    `preferences` : target_domains, target_locations, target_companies, keywords,
    excluded_keywords, start_date_earliest, start_date_latest.
    Retourne : { score, dimensions, weights, analysis, breakdown }.
    """
    w = {**DEFAULT_SCORING_WEIGHTS, **(weights or {})}

    title = offer.get("title") or ""
    desc = offer.get("description") or ""
    company = offer.get("company_name") or ""
    location = offer.get("location")
    domain = offer.get("domain")

    dims = {
        "domain": _dim_domain(domain, title, desc, preferences.get("target_domains", [])),
        "company": _dim_company(company, preferences.get("target_companies", [])),
        "location": _dim_location(location, preferences.get("target_locations", [])),
        "skills": _dim_skills(title, desc, company, cv_tokens, user_skills),
        "education": _dim_education(desc, offer.get("required_education")),
        "quality": _dim_quality(offer),
        "timing": _dim_timing(
            offer.get("start_date"),
            preferences.get("start_date_earliest"),
            preferences.get("start_date_latest"),
        ),
        "ai": None,  # rempli par la passe Claude
    }

    # Score global : moyenne pondérée sur les dimensions disponibles (ai peut être None)
    total_weight = 0
    weighted_sum = 0
    for key, value in dims.items():
        if value is None:
            continue
        weight = w.get(key, 0)
        weighted_sum += weight * value
        total_weight += weight
    global_score = int(round(weighted_sum / total_weight)) if total_weight else 0

    return {
        "score": global_score,
        "dimensions": dims,
        "weights": w,
        "analysis": _summarize_dims(dims, title, company),
    }


def _summarize_dims(dims: dict, title: str, company: str) -> str:
    """Résumé textuel basé sur les dimensions fortes/faibles."""
    strong = sorted(
        [(k, v) for k, v in dims.items() if v is not None and v >= 70],
        key=lambda x: -x[1],
    )[:3]
    weak = sorted(
        [(k, v) for k, v in dims.items() if v is not None and v <= 30],
        key=lambda x: x[1],
    )[:2]
    labels = {
        "domain": "domaine", "company": "entreprise", "location": "localisation",
        "skills": "compétences", "education": "formation", "quality": "qualité offre",
        "timing": "timing", "ai": "IA",
    }
    parts = [f"'{title}' chez {company}."]
    if strong:
        parts.append("Points forts : " + ", ".join(f"{labels[k]} ({v})" for k, v in strong) + ".")
    if weak:
        parts.append("Points faibles : " + ", ".join(f"{labels[k]} ({v})" for k, v in weak) + ".")
    return " ".join(parts)


def recompute_global_score(dimensions: dict, weights: dict | None = None) -> int:
    """Recalcule le score global à partir des dimensions (utilisé après mise à jour IA)."""
    w = {**DEFAULT_SCORING_WEIGHTS, **(weights or {})}
    total_weight = 0
    weighted_sum = 0
    for key, value in dimensions.items():
        if value is None:
            continue
        weight = w.get(key, 0)
        weighted_sum += weight * value
        total_weight += weight
    return int(round(weighted_sum / total_weight)) if total_weight else 0
