"""
Scraper pour Welcome to the Jungle.
Utilise l'API Algolia publique exposée par le frontend WTTJ.
"""

import os

import httpx
import logging

from app.scrapers.registry import BaseScraper, ScrapedOffer, register_scraper

logger = logging.getLogger(__name__)

# Identifiants Algolia de recherche WTTJ — fournis via variables d'environnement
# (non versionnés dans ce snapshot).
ALGOLIA_APP_ID = os.getenv("WTTJ_ALGOLIA_APP_ID", "")
ALGOLIA_API_KEY = os.getenv("WTTJ_ALGOLIA_API_KEY", "")
ALGOLIA_INDEX = "wttj_jobs_production_fr"
ALGOLIA_URL = f"https://{ALGOLIA_APP_ID}-dsn.algolia.net/1/indexes/{ALGOLIA_INDEX}/query"


class WelcomeToTheJungleScraper(BaseScraper):
    platform_name = "welcome_to_the_jungle"

    def scrape(
        self,
        keywords: list[str] | None = None,
        location: str | None = None,
    ) -> list[ScrapedOffer]:
        """Scrape les offres de stage WTTJ en finance via l'API Algolia."""
        offers: list[ScrapedOffer] = []

        search_terms = keywords or [
            "stage finance de marché",
            "stage trading",
            "stage sales trading",
            "stage structuration",
            "stage M&A",
            "stage conseil stratégie",
            "stage risk management",
            "stage private equity",
            "stage quantitatif",
            "stage analyste financier",
        ]

        for term in search_terms:
            try:
                page_offers = self._search_algolia(term, location or "Paris")
                offers.extend(page_offers)
                logger.info(f"WTTJ '{term}': {len(page_offers)} offres")
            except Exception as e:
                logger.error(f"WTTJ '{term}' erreur: {e}")

        # Dédupliquer par external_id
        seen: set[str] = set()
        unique: list[ScrapedOffer] = []
        for o in offers:
            if o.external_id not in seen:
                seen.add(o.external_id)
                unique.append(o)

        # Filtrer finance/conseil
        filtered = self.filter_finance_conseil(unique)
        logger.info(f"WTTJ total: {len(unique)} uniques, {len(filtered)} finance/conseil")
        return filtered

    def _search_algolia(self, query: str, location: str) -> list[ScrapedOffer]:
        """Interroge l'API Algolia de WTTJ."""
        headers = {
            "X-Algolia-Application-Id": ALGOLIA_APP_ID,
            "X-Algolia-API-Key": ALGOLIA_API_KEY,
            "Content-Type": "application/json",
            "Referer": "https://www.welcometothejungle.com/",
        }

        payload = {
            "query": query,
            "hitsPerPage": 20,
            "aroundLatLngViaIP": False,
        }

        # Paris par défaut
        if location and location.lower() == "paris":
            payload["aroundLatLng"] = "48.8566,2.3522"
            payload["aroundRadius"] = 50000  # 50km

        results: list[ScrapedOffer] = []

        try:
            with httpx.Client(timeout=30) as client:
                response = client.post(ALGOLIA_URL, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()

                for hit in data.get("hits", []):
                    offer = self._parse_hit(hit)
                    if offer:
                        results.append(offer)

        except httpx.HTTPError as e:
            logger.error(f"HTTP error WTTJ Algolia: {e}")

        return results

    def _parse_hit(self, hit: dict) -> ScrapedOffer | None:
        """Parse un résultat Algolia en ScrapedOffer."""
        try:
            reference = hit.get("wk_reference", hit.get("objectID", ""))
            org = hit.get("organization", {})
            org_slug = org.get("slug", "")
            slug = hit.get("slug", reference)

            source_url = f"https://www.welcometothejungle.com/fr/companies/{org_slug}/jobs/{slug}"

            # Localisation depuis _geoloc ou office
            location = None
            office = hit.get("office", {})
            if isinstance(office, dict):
                city = office.get("city", "")
                country = office.get("country", "")
                if city:
                    location = f"{city}, {country}".strip(", ")

            # Description
            description = hit.get("summary", "") or hit.get("description", "") or ""

            # Durée
            duration = hit.get("contract_duration_maximum")

            # Salaire
            salary = None
            sal_min = hit.get("salary_minimum")
            sal_max = hit.get("salary_maximum")
            sal_period = hit.get("salary_period", "")
            if sal_min or sal_max:
                parts = []
                if sal_min:
                    parts.append(str(int(sal_min)))
                if sal_max:
                    parts.append(str(int(sal_max)))
                salary = " - ".join(parts) + f" EUR/{sal_period}" if parts else None

            # Secteurs → domain
            sectors = hit.get("sectors", [])
            domain = "finance"
            for sector in sectors:
                if isinstance(sector, dict):
                    name = sector.get("parent_name", "").lower()
                    if any(kw in name for kw in ["finance", "banque", "assurance"]):
                        domain = "finance"
                        break
                    elif any(kw in name for kw in ["conseil", "audit", "consulting"]):
                        domain = "conseil"
                        break

            # Education
            education = hit.get("education_level")

            return ScrapedOffer(
                external_id=str(reference),
                source_platform=self.platform_name,
                source_url=source_url,
                title=hit.get("name", "Sans titre"),
                company_name=org.get("name", "Entreprise inconnue"),
                company_logo_url=org.get("logo", {}).get("url") if isinstance(org.get("logo"), dict) else None,
                description=description[:5000] if description else None,
                location=location,
                is_remote=hit.get("remote") in ("full", "partial"),
                domain=domain,
                contract_type="stage",
                duration_months=duration,
                salary=salary,
                required_education=education,
                raw_data={
                    "sectors": sectors,
                    "experience_level_minimum": hit.get("experience_level_minimum"),
                    "published_at_timestamp": hit.get("published_at_timestamp"),
                    "benefits": hit.get("benefits", []),
                },
            )
        except Exception as e:
            logger.warning(f"Parse error WTTJ hit: {e}")
            return None


# Enregistrer le scraper
register_scraper(WelcomeToTheJungleScraper())
