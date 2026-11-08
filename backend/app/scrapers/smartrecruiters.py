"""
Scraper pour SmartRecruiters.
Utilise l'API publique SmartRecruiters v1 pour récupérer les offres de stage
de plusieurs entreprises (finance, conseil, stratégie).
"""

import time
import logging

import httpx

from app.scrapers.registry import BaseScraper, ScrapedOffer, register_scraper

logger = logging.getLogger(__name__)

BASE_URL = "https://api.smartrecruiters.com/v1/companies"
POSTINGS_PER_PAGE = 100
RATE_LIMIT_DELAY = 0.5  # secondes entre requêtes

# Entreprises à scraper — company_id SmartRecruiters => nom affiché
# SocieteGenerale et BNPParibas existent sur SmartRecruiters mais ont souvent
# 0 postings publics ; on les garde car ils publient par vagues saisonnières.
COMPANIES: dict[str, str] = {
    "SocieteGenerale": "Société Générale",
    "BNPParibas": "BNP Paribas",
    "Mazars": "Forvis Mazars",
    "RolandBerger": "Roland Berger",
}

# Mots-clés pour identifier un stage dans le titre ou les custom fields
_STAGE_KEYWORDS = {"stage", "stagiaire", "intern", "internship", "apprenti", "alternance"}

# Mots-clés de recherche envoyés à l'API pour pré-filtrer
_SEARCH_QUERIES = [
    "stage",
    "stagiaire",
    "intern",
]


class SmartRecruitersScraper(BaseScraper):
    platform_name = "smartrecruiters"

    def scrape(
        self,
        keywords: list[str] | None = None,
        location: str | None = None,
    ) -> list[ScrapedOffer]:
        """Scrape les offres de stage SmartRecruiters pour les entreprises configurées."""
        all_offers: list[ScrapedOffer] = []

        known_ids = self._load_known_external_ids()
        logger.info(
            f"SmartRecruiters: {len(known_ids)} offres déjà en BDD (skip détail)"
        )

        t0 = time.time()
        for company_id, company_display in COMPANIES.items():
            try:
                offers = self._scrape_company(
                    company_id, company_display, keywords, location, known_ids
                )
                all_offers.extend(offers)
                logger.info(
                    f"SmartRecruiters {company_display} ({company_id}): {len(offers)} offres stage"
                )
            except Exception as e:
                logger.error(f"SmartRecruiters {company_display}: erreur globale: {e}")

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
            f"SmartRecruiters total: {len(unique)} nouvelles, "
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
                    "WHERE source_platform = 'smartrecruiters'"
                )).fetchall()
                return {r[0] for r in rows}
        except Exception as e:
            logger.warning(f"SmartRecruiters: impossible de charger les IDs BDD: {e}")
            return set()

    def _scrape_company(
        self,
        company_id: str,
        company_display: str,
        keywords: list[str] | None,
        location: str | None,
        known_ids: set[str],
    ) -> list[ScrapedOffer]:
        """Scrape toutes les offres de stage d'une entreprise avec pagination."""
        offers: list[ScrapedOffer] = []
        queries = keywords or _SEARCH_QUERIES

        for query in queries:
            try:
                query_offers = self._fetch_postings(
                    company_id, company_display, query, location, known_ids
                )
                offers.extend(query_offers)
            except Exception as e:
                logger.error(f"SmartRecruiters {company_id} q={query}: {e}")
            time.sleep(RATE_LIMIT_DELAY)

        return offers

    def _fetch_postings(
        self,
        company_id: str,
        company_display: str,
        query: str,
        location: str | None,
        known_ids: set[str],
    ) -> list[ScrapedOffer]:
        """Récupère les postings paginés pour une entreprise et un mot-clé."""
        results: list[ScrapedOffer] = []
        offset = 0

        with httpx.Client(timeout=30) as client:
            while True:
                params: dict[str, str | int] = {
                    "limit": POSTINGS_PER_PAGE,
                    "offset": offset,
                    "q": query,
                }
                if location:
                    params["country"] = "fr"

                try:
                    response = client.get(
                        f"{BASE_URL}/{company_id}/postings",
                        params=params,
                        headers={"Accept": "application/json"},
                    )
                    response.raise_for_status()
                    data = response.json()
                except httpx.HTTPError as e:
                    logger.error(f"HTTP error SmartRecruiters {company_id}: {e}")
                    break

                content = data.get("content", [])
                total_found = data.get("totalFound", 0)

                for posting in content:
                    posting_id = posting.get("id", "")
                    # Early-stop : skip les postings déjà en BDD (évite fetch détail)
                    if f"sr-{posting_id}" in known_ids:
                        continue
                    if self._is_stage(posting):
                        offer = self._parse_posting(posting, company_id, company_display, client)
                        if offer:
                            results.append(offer)

                offset += len(content)
                if offset >= total_found or not content:
                    break

                time.sleep(RATE_LIMIT_DELAY)

        return results

    def _is_stage(self, posting: dict) -> bool:
        """Vérifie si le posting est un stage/internship."""
        # Vérifier typeOfEmployment
        toe = posting.get("typeOfEmployment", {})
        if isinstance(toe, dict) and toe.get("id") == "intern":
            return True

        # Vérifier le titre
        name_lower = posting.get("name", "").lower()
        if any(kw in name_lower for kw in _STAGE_KEYWORDS):
            return True

        # Vérifier les custom fields (certaines entreprises y mettent le type de contrat)
        for cf in posting.get("customField", []):
            label = cf.get("fieldLabel", "").lower()
            value = cf.get("valueLabel", "").lower()
            if ("contrat" in label or "type" in label) and any(
                kw in value for kw in _STAGE_KEYWORDS
            ):
                return True

        return False

    def _parse_posting(
        self,
        posting: dict,
        company_id: str,
        company_display: str,
        client: httpx.Client,
    ) -> ScrapedOffer | None:
        """Parse un posting SmartRecruiters en ScrapedOffer."""
        try:
            posting_id = posting.get("id", "")
            uuid = posting.get("uuid", posting_id)

            # Récupérer la description depuis le détail du posting
            description = self._fetch_description(company_id, posting_id, client)

            # Localisation
            loc = posting.get("location", {})
            location_parts = []
            city = loc.get("city")
            region = loc.get("region")
            country = loc.get("country", "").upper()
            if city:
                location_parts.append(city)
            if region:
                location_parts.append(region)
            if country:
                location_parts.append(country)
            location_str = ", ".join(location_parts) if location_parts else None

            is_remote = loc.get("remote", False) or loc.get("hybrid", False)

            # Nom de l'entreprise depuis le posting ou fallback
            company_name = posting.get("company", {}).get("name", company_display)

            # Domain depuis industry/function/department
            domain = self._infer_domain(posting)

            # Contract type depuis customField ou typeOfEmployment
            contract_type = self._infer_contract_type(posting)

            # URL du posting
            source_url = (
                f"https://jobs.smartrecruiters.com/"
                f"{posting.get('company', {}).get('identifier', company_id)}/{posting_id}"
            )

            return ScrapedOffer(
                external_id=f"sr-{posting_id}",
                source_platform=self.platform_name,
                source_url=source_url,
                title=posting.get("name", "Sans titre"),
                company_name=company_name,
                company_logo_url=None,
                description=description[:5000] if description else None,
                location=location_str,
                is_remote=is_remote,
                domain=domain,
                contract_type=contract_type,
                salary=None,
                required_education=None,
                raw_data={
                    "uuid": uuid,
                    "refNumber": posting.get("refNumber"),
                    "releasedDate": posting.get("releasedDate"),
                    "industry": posting.get("industry"),
                    "function": posting.get("function"),
                    "department": posting.get("department"),
                    "typeOfEmployment": posting.get("typeOfEmployment"),
                    "experienceLevel": posting.get("experienceLevel"),
                    "customField": posting.get("customField", []),
                },
            )

        except Exception as e:
            logger.warning(f"Parse error SmartRecruiters posting: {e}")
            return None

    def _fetch_description(
        self, company_id: str, posting_id: str, client: httpx.Client
    ) -> str | None:
        """Récupère la description complète depuis l'endpoint détail."""
        try:
            time.sleep(RATE_LIMIT_DELAY)
            response = client.get(
                f"{BASE_URL}/{company_id}/postings/{posting_id}",
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
            data = response.json()

            sections = data.get("jobAd", {}).get("sections", {})
            parts = []
            for key in ("jobDescription", "qualifications", "additionalInformation"):
                section = sections.get(key, {})
                if isinstance(section, dict):
                    text = section.get("text", "")
                    if text:
                        parts.append(text)

            return "\n\n".join(parts) if parts else None

        except Exception as e:
            logger.debug(f"Impossible de récupérer le détail {company_id}/{posting_id}: {e}")
            return None

    def _infer_domain(self, posting: dict) -> str | None:
        """Infère le domaine depuis industry, function et department."""
        texts = []
        for field in ("industry", "function", "department"):
            val = posting.get(field, {})
            if isinstance(val, dict):
                label = val.get("label", "")
                if label:
                    texts.append(label.lower())

        combined = " ".join(texts)

        if any(kw in combined for kw in ("finance", "banking", "investment", "asset")):
            return "finance"
        if any(kw in combined for kw in ("consulting", "conseil", "strategy", "advisory")):
            return "conseil"
        if any(kw in combined for kw in ("audit", "accounting", "comptab")):
            return "audit"
        if any(kw in combined for kw in ("risk", "compliance", "regulation")):
            return "risk"
        return None

    def _infer_contract_type(self, posting: dict) -> str:
        """Détermine le type de contrat (stage, alternance, etc.)."""
        # Vérifier les custom fields d'abord (plus fiable)
        for cf in posting.get("customField", []):
            label = cf.get("fieldLabel", "").lower()
            value = cf.get("valueLabel", "").lower()
            if "contrat" in label or "type" in label:
                if "alternance" in value or "apprenti" in value:
                    return "alternance"
                if "stage" in value or "intern" in value:
                    return "stage"

        # Fallback sur le titre
        name_lower = posting.get("name", "").lower()
        if "alternance" in name_lower or "apprenti" in name_lower:
            return "alternance"

        return "stage"


# Enregistrer le scraper
register_scraper(SmartRecruitersScraper())
