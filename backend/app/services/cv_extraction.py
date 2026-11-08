"""
Extraction de compétences, formations, langues et expériences depuis le texte d'un CV.
Approche par règles — pas de dépendance IA.
"""

import re
import logging

logger = logging.getLogger(__name__)

# ── Dictionnaires de compétences connues par catégorie ──────

TECHNICAL_SKILLS = {
    # Programmation
    "python", "sql", "r", "c", "c++", "java", "javascript", "vba", "matlab",
    "stata", "sas", "typescript", "html", "css", "rust", "go", "scala",
    # Outils finance
    "bloomberg", "reuters", "eikon", "factset", "capital iq", "pitchbook",
    "morningstar", "datastream", "refinitiv",
    # Data / Quant
    "excel", "power bi", "tableau", "pandas", "numpy", "scikit-learn",
    "tensorflow", "keras", "pytorch", "machine learning", "deep learning",
    "data analysis", "analyse de données", "modélisation statistique",
    "modélisation de données", "recherche opérationnelle",
    "méthodes numériques", "optimisation",
    # Finance
    "analyse financière", "financial analysis", "valorisation", "valuation",
    "modélisation financière", "financial modeling", "dcf",
    "tableaux croisés dynamiques", "pivot tables",
    "états financiers", "financial statements",
    "comptabilité", "accounting",
    # Outils généraux
    "microsoft office", "word", "powerpoint", "teams", "canva",
    "git", "docker", "linux", "jira", "confluence",
}

SOFT_SKILLS = {
    "travail d'équipe", "teamwork", "communication", "adaptabilité",
    "rigueur", "esprit analytique", "analytical thinking",
    "leadership", "gestion de projet", "project management",
    "résolution de problèmes", "problem solving",
    "autonomie", "créativité", "négociation",
}

LANGUAGES = {
    "français": "langue maternelle",
    "anglais": "courant",
    "english": "fluent",
    "espagnol": "intermédiaire",
    "spanish": "intermediate",
    "allemand": "intermédiaire",
    "german": "intermediate",
    "mandarin": "débutant",
    "italien": "débutant",
    "arabe": "débutant",
    "portugais": "débutant",
    "japonais": "débutant",
    "chinois": "débutant",
}

CERTIFICATIONS = {
    "bloomberg", "bff", "cfa", "frm", "amf", "acca",
    "google analytics", "aws", "azure", "permis",
    "toefl", "toeic", "ielts", "gmat",
}

# ── Patterns pour les niveaux de compétence ──────

LEVEL_PATTERNS = {
    "expert": r"expert|avancé|advanced|maîtrise|mastery|10\+\s*ans",
    "avance": r"courant|fluent|avancé|advanced|solide|C[12]",
    "intermediaire": r"intermédiaire|intermediate|B[12]|opérationnel|fonctionnel",
    "debutant": r"débutant|beginner|notions|bases|A[12]",
}


def extract_skills_from_cv(cv_text: str) -> list[dict]:
    """
    Extrait les compétences structurées d'un texte de CV.
    Retourne une liste de dicts: {skill_name, skill_category, proficiency_level}
    """
    if not cv_text:
        return []

    text_lower = cv_text.lower()
    skills = []
    seen = set()

    # 1. Compétences techniques
    for skill in TECHNICAL_SKILLS:
        if skill.lower() in text_lower:
            if skill.lower() not in seen:
                seen.add(skill.lower())
                skills.append({
                    "skill_name": skill.title() if len(skill) > 3 else skill.upper(),
                    "skill_category": "technique",
                    "proficiency_level": _guess_level(cv_text, skill),
                })

    # 2. Soft skills
    for skill in SOFT_SKILLS:
        if skill.lower() in text_lower:
            if skill.lower() not in seen:
                seen.add(skill.lower())
                skills.append({
                    "skill_name": skill.title(),
                    "skill_category": "soft_skill",
                    "proficiency_level": None,
                })

    # 3. Langues
    for lang, default_level in LANGUAGES.items():
        if lang.lower() in text_lower:
            if lang.lower() not in seen:
                seen.add(lang.lower())
                level = _extract_language_level(cv_text, lang) or default_level
                skills.append({
                    "skill_name": lang.title(),
                    "skill_category": "langue",
                    "proficiency_level": level,
                })

    # 4. Certifications
    for cert in CERTIFICATIONS:
        if cert.lower() in text_lower:
            if cert.lower() not in seen:
                seen.add(cert.lower())
                skills.append({
                    "skill_name": cert.upper() if len(cert) <= 4 else cert.title(),
                    "skill_category": "certification",
                    "proficiency_level": None,
                })

    logger.info(f"CV extraction: {len(skills)} compétences trouvées")
    return skills


def extract_formations(cv_text: str) -> list[str]:
    """Extrait les formations / écoles mentionnées."""
    formations = []
    # Patterns courants
    patterns = [
        r"([\w-]+\s+business\s+school)",
        r"([eé]cole\s+des\s+mines|mines\s+[\w-]+)",
        r"(hec|essec|edhec|escp|Sciences\s*Po)",
        r"(polytechnique|centrale|ens)",
        r"(master|mba|bachelor|licence|bac\+\d)",
        r"(classe\s+préparatoire|cpge|mp\w*|mpsi)",
    ]
    for pat in patterns:
        matches = re.findall(pat, cv_text, re.IGNORECASE)
        formations.extend(matches)
    return list(set(f.strip() for f in formations if f.strip()))


def tokenize_for_matching(text: str) -> set[str]:
    """
    Tokenise un texte pour le matching CV/offre.
    Retourne un set de tokens normalisés (lowercase, sans ponctuation, > 2 chars).
    """
    # Retirer ponctuation sauf tirets et apostrophes internes
    cleaned = re.sub(r"[^\w\s'-]", " ", text.lower())
    tokens = cleaned.split()
    # Filtrer les tokens trop courts et les stop words
    stop_words = {
        "le", "la", "les", "de", "du", "des", "un", "une", "et", "ou",
        "en", "au", "aux", "ce", "qui", "que", "par", "pour", "sur",
        "avec", "dans", "est", "sont", "être", "avoir", "fait", "plus",
        "the", "and", "for", "with", "you", "our", "are", "will", "your",
        "this", "that", "from", "have", "has", "been", "all", "can",
        "not", "but", "they", "was", "were", "its",
    }
    return {t for t in tokens if len(t) > 2 and t not in stop_words}


def _guess_level(cv_text: str, skill: str) -> str | None:
    """Essaie de deviner le niveau d'une compétence depuis le contexte."""
    # Chercher le skill et le texte autour
    idx = cv_text.lower().find(skill.lower())
    if idx == -1:
        return None
    context = cv_text[max(0, idx - 50):idx + len(skill) + 50].lower()
    for level, pattern in LEVEL_PATTERNS.items():
        if re.search(pattern, context, re.IGNORECASE):
            return level
    return None


def _extract_language_level(cv_text: str, lang: str) -> str | None:
    """Extrait le niveau d'une langue depuis le contexte."""
    idx = cv_text.lower().find(lang.lower())
    if idx == -1:
        return None
    context = cv_text[max(0, idx - 10):idx + len(lang) + 40].lower()

    if any(w in context for w in ["maternelle", "native", "mother"]):
        return "langue maternelle"
    if any(w in context for w in ["courant", "fluent", "c2", "c1", "bilingue"]):
        return "courant"
    if any(w in context for w in ["intermédiaire", "intermediate", "b2", "b1"]):
        return "intermédiaire"
    if any(w in context for w in ["débutant", "beginner", "a1", "a2", "notions"]):
        return "débutant"
    return None
