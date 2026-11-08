"""
Scraper pour les career pages Greenhouse de hedge funds / quant firms.
Utilise l'API publique Greenhouse boards.
"""

import time
import re
import logging

import httpx

from app.scrapers.registry import BaseScraper, ScrapedOffer, register_scraper

logger = logging.getLogger(__name__)

# Slugs Greenhouse vérifiés (mars 2026)
COMPANY_SLUGS: list[str] = [
    "squarepointcapital",           # Squarepoint Capital
    "cfm",                          # Capital Fund Management
    "marshallwace",                 # Marshall Wace
    "quberesearchandtechnologies",  # Qube Research & Technologies
    "point72",                      # Point72
    "imc",                          # IMC
    "flowtraders",                  # Flow Traders
    "akunacapital",                 # Akuna Capital
    "exoduspoint",                  # ExodusPoint
    "worldquant",                   # WorldQuant
]

API_BASE = "https://boards-api.greenhouse.io/v1/boards"

# Mots-clés indiquant un stage / poste junior
INTERNSHIP_KEYWORDS = {
    "intern", "internship", "stage", "stagiaire",
    "graduate", "junior", "trainee", "apprenti",
    "apprentice", "werkstudent", "placement",
    "co-op", "coop",
}

REQUEST_DELAY = 0.5  # secondes entre les requêtes


def _strip_html(html: str) -> str:
    """Supprime les balises HTML (y compris encodées) et retourne du texte brut."""
    import html as html_mod
    # Décoder les entités HTML (gère &lt; &gt; &amp; &nbsp; etc.)
    text = html_mod.unescape(html)
    # Certaines sources double-encodent, décoder une seconde fois
    if "&lt;" in text or "&gt;" in text or "&amp;" in text:
        text = html_mod.unescape(text)
    # Retirer les balises HTML
    text = re.sub(r"<[^>]+>", " ", text)
    # Nettoyer les espaces multiples
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _is_internship(title: str, departments: list[dict] | None = None,
                   metadata: list[dict] | None = None) -> bool:
    """Vérifie si un poste est un stage / graduate / junior."""
    title_lower = title.lower()

    # Vérifier le titre
    if any(kw in title_lower for kw in INTERNSHIP_KEYWORDS):
        return True

    # Vérifier les départements
    if departments:
        for dept in departments:
            dept_name = dept.get("name", "").lower()
            if any(kw in dept_name for kw in INTERNSHIP_KEYWORDS):
                return True

    # Vérifier les metadata (champ "Employment Type" ou "Experience Level")
    if metadata:
        for meta in metadata:
            value = str(meta.get("value", "")).lower()
            name = str(meta.get("name", "")).lower()
            if "experience" in name or "employment" in name or "type" in name:
                if any(kw in value for kw in INTERNSHIP_KEYWORDS):
                    return True

    return False


class GreenhouseScraper(BaseScraper):
    platform_name = "greenhouse"

    def __init__(self, slugs: list[str] | None = None):
        self._slugs = slugs or COMPANY_SLUGS

    def scrape(
        self,
        keywords: list[str] | None = None,
        location: str | None = None,
    ) -> list[ScrapedOffer]:
        """Scrape les offres de stage / junior depuis les boards Greenhouse."""
        all_offers: list[ScrapedOffer] = []

        known_ids = self._load_known_external_ids()
        logger.info(
            f"Greenhouse: {len(known_ids)} offres déjà en BDD (skip détail)"
        )

        t0 = time.time()
        with httpx.Client(timeout=20) as client:
            for slug in self._slugs:
                try:
                    offers = self._scrape_board(client, slug, location, known_ids)
                    all_offers.extend(offers)
                    logger.info(f"Greenhouse '{slug}': {len(offers)} offres retenues")
                except Exception as e:
                    logger.error(f"Greenhouse '{slug}' erreur: {e}")

        # Dédupliquer par external_id
        seen: set[str] = set()
        unique: list[ScrapedOffer] = []
        for o in all_offers:
            if o.external_id not in seen:
                seen.add(o.external_id)
                unique.append(o)

        # Filtrer finance/conseil
        filtered = self.filter_finance_conseil(unique)
        logger.info(
            f"Greenhouse total: {len(unique)} nouvelles, "
            f"{len(filtered)} finance/conseil | durée: {time.time()-t0:.1f}s"
        )
        return filtered

    @staticmethod
    def _load_known_external_ids() -> set[str]:
        """Charge les external_id déjà présents en BDD pour cette plateforme."""
        try:
            from sqlalchemy import create_engine, text
            from app.core.config import get_settings
            s = get_settings()
            sync_url = s.database_url.replace("+asyncpg", "+psycopg2")
            engine = create_engine(sync_url)
            with engine.connect() as conn:
                rows = conn.execute(text(
                    "SELECT external_id FROM offers "
                    "WHERE source_platform = 'greenhouse'"
                )).fetchall()
                return {r[0] for r in rows}
        except Exception as e:
            logger.warning(f"Greenhouse: impossible de charger les IDs BDD: {e}")
            return set()

    def _scrape_board(
        self,
        client: httpx.Client,
        slug: str,
        location: str | None,
        known_ids: set[str],
    ) -> list[ScrapedOffer]:
        """Scrape un board Greenhouse donné."""

        # 1. Récupérer la liste des jobs
        url = f"{API_BASE}/{slug}/jobs"
        time.sleep(REQUEST_DELAY)
        resp = client.get(url)
        resp.raise_for_status()
        data = resp.json()
        jobs = data.get("jobs", [])

        if not jobs:
            logger.debug(f"Greenhouse '{slug}': aucun job trouvé")
            return []

        # 2. Filtrer les stages / postes junior
        candidates = []
        for job in jobs:
            title = job.get("title", "")
            departments = job.get("departments", [])
            metadata = job.get("metadata", [])

            if _is_internship(title, departments, metadata):
                candidates.append(job)

        logger.debug(
            f"Greenhouse '{slug}': {len(candidates)}/{len(jobs)} "
            f"correspondent aux critères stage/junior"
        )

        # 3. Filtrer par localisation si demandé
        if location:
            loc_lower = location.lower()
            candidates = [
                j for j in candidates
                if loc_lower in (j.get("location", {}).get("name", "") or "").lower()
            ]

        # 4. Early-stop : skip les jobs déjà en BDD (évite le fetch détail)
        new_candidates = [
            j for j in candidates
            if f"gh-{j.get('id')}" not in known_ids
        ]
        skipped = len(candidates) - len(new_candidates)
        if skipped:
            logger.debug(f"Greenhouse '{slug}': {skipped} jobs skip (déjà en BDD)")

        # 5. Récupérer les détails et construire les ScrapedOffer
        offers: list[ScrapedOffer] = []
        for job in new_candidates:
            try:
                offer = self._fetch_and_parse_job(client, slug, job)
                if offer:
                    offers.append(offer)
            except Exception as e:
                logger.warning(
                    f"Greenhouse '{slug}' job {job.get('id')}: erreur détail: {e}"
                )

        return offers

    def _fetch_and_parse_job(
        self,
        client: httpx.Client,
        slug: str,
        job_summary: dict,
    ) -> ScrapedOffer | None:
        """Récupère le détail d'un job et le parse en ScrapedOffer."""
        job_id = job_summary["id"]

        # Récupérer le détail complet
        time.sleep(REQUEST_DELAY)
        detail_url = f"{API_BASE}/{slug}/jobs/{job_id}"
        resp = client.get(detail_url)
        resp.raise_for_status()
        detail = resp.json()

        # Extraire les champs
        title = detail.get("title", "Sans titre")
        content_html = detail.get("content", "")
        description = _strip_html(content_html) if content_html else None
        location_name = detail.get("location", {}).get("name")
        absolute_url = detail.get("absolute_url", "")
        company_name = detail.get("company_name") or slug

        # Déterminer le type de contrat
        title_lower = title.lower()
        if any(kw in title_lower for kw in ("intern", "internship", "stage", "stagiaire")):
            contract_type = "stage"
        elif any(kw in title_lower for kw in ("graduate", "trainee")):
            contract_type = "graduate"
        elif "junior" in title_lower:
            contract_type = "junior"
        else:
            contract_type = "stage"

        # Vérifier is_remote
        is_remote = False
        if location_name and "remote" in location_name.lower():
            is_remote = True

        # Départements
        departments = [d.get("name") for d in detail.get("departments", []) if d.get("name")]

        return ScrapedOffer(
            external_id=f"gh-{job_id}",
            source_platform=self.platform_name,
            source_url=absolute_url,
            title=title,
            company_name=company_name,
            description=description[:5000] if description else None,
            location=location_name,
            is_remote=is_remote,
            domain="finance",
            contract_type=contract_type,
            raw_data={
                "greenhouse_slug": slug,
                "greenhouse_job_id": job_id,
                "departments": departments,
                "metadata": detail.get("metadata", []),
                "offices": detail.get("offices", []),
                "first_published": detail.get("first_published"),
                "updated_at": detail.get("updated_at"),
            },
        )


# Enregistrer le scraper
register_scraper(GreenhouseScraper())
