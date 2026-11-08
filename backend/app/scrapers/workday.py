"""
Scraper pour les sites carrière Workday (banques et institutions financières).
Utilise l'API JSON standard exposée par les sites carrière Workday.

Flux : GET la page carrière (pour obtenir le cookie de session CSRF),
puis POST sur l'endpoint /wday/cxs/{company}/{site}/jobs.

Note : De nombreuses grandes banques (Goldman Sachs, JP Morgan, Morgan Stanley,
Citi, UBS, Lazard) protègent leur site Workday via Cloudflare JS challenge,
ce qui bloque les requêtes httpx. Un test de connectivité est effectué au
démarrage du scrape pour ne garder que les sites accessibles.
"""

import time
import logging
from dataclasses import dataclass

import httpx

from app.scrapers.registry import BaseScraper, ScrapedOffer, register_scraper

logger = logging.getLogger(__name__)

# Délai entre chaque requête pour respecter les rate limits
REQUEST_DELAY_S = 0.5

# Timeout pour le test de connectivité (plus court que le scrape)
CONNECTIVITY_TIMEOUT_S = 12


@dataclass
class WorkdayConfig:
    """Configuration d'un site carrière Workday."""

    company_name: str          # Nom affiché (ex: "Morgan Stanley")
    subdomain: str             # Sous-domaine Workday (ex: "morganstanley")
    wd_instance: str           # Instance Workday (ex: "wd5")
    site_name: str             # Nom du site carrière (ex: "morganstanley", "External")
    enabled: bool = True       # Activer/désactiver sans retirer de la liste

    @property
    def base_url(self) -> str:
        return f"https://{self.subdomain}.{self.wd_instance}.myworkdayjobs.com"

    @property
    def api_url(self) -> str:
        return f"{self.base_url}/wday/cxs/{self.subdomain}/{self.site_name}/jobs"

    @property
    def career_page_url(self) -> str:
        return f"{self.base_url}/{self.site_name}"


# ── Configurations des banques ──────────────────────────────
#
# enabled=True  → sera scrapé (test de connectivité avant)
# enabled=False → ignoré (Cloudflare bloque les requêtes non-browser)
#
# Pour réactiver une banque, passer enabled=True et tester manuellement.

WORKDAY_CONFIGS: list[WorkdayConfig] = [
    # ── Banques accessibles (vérifié avril 2026) ──
    WorkdayConfig(
        company_name="Julius Baer",
        subdomain="juliusbaer",
        wd_instance="wd3",
        site_name="External",
    ),

    # ── Banques bloquées par Cloudflare (testées avril 2026) ──
    # Cloudflare block — à retenter avec Playwright stealth.
    # Retournent 422/404 sur l'API JSON même avec session cookie.
    # Couvertes partiellement via WTTJ / eFinancialCareers à la place.
    WorkdayConfig(
        company_name="Goldman Sachs",
        subdomain="goldmansachs",
        wd_instance="wd1",
        site_name="goldmansachs",
        enabled=False,
    ),
    WorkdayConfig(
        company_name="JP Morgan",
        subdomain="jpmc",
        wd_instance="wd5",
        site_name="External",
        enabled=False,
    ),
    WorkdayConfig(
        company_name="Morgan Stanley",
        subdomain="morganstanley",
        wd_instance="wd5",
        site_name="morganstanley",
        enabled=False,
    ),
    WorkdayConfig(
        company_name="Citi",
        subdomain="citi",
        wd_instance="wd5",
        site_name="External",
        enabled=False,
    ),
    WorkdayConfig(
        company_name="UBS",
        subdomain="ubs",
        wd_instance="wd3",
        site_name="careers",
        enabled=False,
    ),
    WorkdayConfig(
        company_name="Lazard",
        subdomain="lazard",
        wd_instance="wd1",
        site_name="lazard",
        enabled=False,
    ),
]

# Mots-clés de recherche ciblant les stages en finance
SEARCH_TERMS = [
    "intern",
    "internship",
    "stage",
    "stagiaire",
    "analyst intern",
    "summer analyst",
    "off-cycle",
    "graduate",
]

# Mots-clés pour détecter un stage/internship dans le titre
INTERN_KEYWORDS = {
    "intern", "internship", "stage", "stagiaire",
    "summer analyst", "summer associate",
    "off-cycle", "graduate program", "apprenti",
    "alternance", "werkstudent", "praktikum",
}


class WorkdayScraper(BaseScraper):
    platform_name = "workday"

    # Headers communs imitant un navigateur Chrome
    _browser_headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9,fr;q=0.8",
    }

    def scrape(
        self,
        keywords: list[str] | None = None,
        location: str | None = None,
    ) -> list[ScrapedOffer]:
        """Scrape les offres de stage sur les sites carrière Workday des banques."""
        all_offers: list[ScrapedOffer] = []
        succeeded: list[str] = []
        failed: list[str] = []
        skipped: list[str] = []

        active_configs = [c for c in WORKDAY_CONFIGS if c.enabled]
        disabled_configs = [c for c in WORKDAY_CONFIGS if not c.enabled]

        for cfg in disabled_configs:
            skipped.append(cfg.company_name)

        logger.info(
            f"Workday: {len(active_configs)} banque(s) active(s), "
            f"{len(disabled_configs)} désactivée(s) (Cloudflare)"
        )

        for config in active_configs:
            try:
                if not self._test_connectivity(config):
                    logger.warning(
                        f"Workday {config.company_name}: API inaccessible "
                        f"(probablement Cloudflare), skip"
                    )
                    failed.append(config.company_name)
                    continue

                company_offers = self._scrape_company(config, keywords)
                all_offers.extend(company_offers)
                succeeded.append(config.company_name)
                logger.info(
                    f"Workday {config.company_name}: {len(company_offers)} offres"
                )
            except Exception as e:
                logger.error(f"Workday {config.company_name} erreur: {e}")
                failed.append(config.company_name)

            time.sleep(REQUEST_DELAY_S)

        # Dédupliquer par external_id
        seen: set[str] = set()
        unique: list[ScrapedOffer] = []
        for o in all_offers:
            if o.external_id not in seen:
                seen.add(o.external_id)
                unique.append(o)

        # Filtrer finance/conseil
        filtered = self.filter_finance_conseil(unique)

        # Résumé final
        logger.info(
            f"Workday résumé: {len(unique)} uniques, "
            f"{len(filtered)} finance/conseil | "
            f"OK={succeeded or 'aucun'} | "
            f"ECHEC={failed or 'aucun'} | "
            f"DESACTIVE={skipped or 'aucun'}"
        )
        return filtered

    def _test_connectivity(self, config: WorkdayConfig) -> bool:
        """Teste si l'API Workday d'une banque est accessible (pas de Cloudflare).

        Envoie une requête minimale (limit=1) et vérifie qu'on reçoit un 200.
        """
        try:
            with httpx.Client(
                timeout=CONNECTIVITY_TIMEOUT_S, follow_redirects=True
            ) as client:
                # GET la page carrière pour les cookies de session
                client.get(
                    config.career_page_url,
                    headers={
                        **self._browser_headers,
                        "Accept": "text/html,application/xhtml+xml",
                    },
                )
                time.sleep(0.3)

                # POST minimal sur l'API
                resp = client.post(
                    config.api_url,
                    json={"appliedFacets": {}, "limit": 1, "offset": 0, "searchText": "intern"},
                    headers={
                        **self._browser_headers,
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                        "Referer": config.career_page_url,
                        "Origin": config.base_url,
                    },
                )
                if resp.status_code == 200:
                    return True
                logger.debug(
                    f"Workday connectivity {config.company_name}: "
                    f"HTTP {resp.status_code}"
                )
                return False
        except Exception as e:
            logger.debug(
                f"Workday connectivity {config.company_name}: {e}"
            )
            return False

    def _scrape_company(
        self,
        config: WorkdayConfig,
        keywords: list[str] | None = None,
    ) -> list[ScrapedOffer]:
        """Scrape un site carrière Workday donné."""
        offers: list[ScrapedOffer] = []
        search_terms = keywords or SEARCH_TERMS

        with httpx.Client(timeout=30, follow_redirects=True) as client:
            # Étape 1 : GET la page carrière pour obtenir le cookie de session
            try:
                session_resp = client.get(
                    config.career_page_url,
                    headers={
                        **self._browser_headers,
                        "Accept": "text/html,application/xhtml+xml",
                    },
                )
                # On accepte aussi les 500 temporaires ; les cookies sont
                # souvent positionnés même en cas de maintenance Workday.
                logger.debug(
                    f"Workday session {config.company_name}: "
                    f"HTTP {session_resp.status_code}"
                )
            except httpx.HTTPError as e:
                logger.warning(
                    f"Workday session {config.company_name} échouée: {e}"
                )
                # On tente quand même le POST au cas où

            # Étape 2 : POST sur l'API jobs pour chaque terme de recherche
            for term in search_terms:
                try:
                    term_offers = self._fetch_jobs(client, config, term)
                    offers.extend(term_offers)
                except Exception as e:
                    logger.warning(
                        f"Workday {config.company_name} '{term}': {e}"
                    )
                time.sleep(REQUEST_DELAY_S)

        return offers

    def _fetch_jobs(
        self,
        client: httpx.Client,
        config: WorkdayConfig,
        search_text: str,
        max_pages: int = 5,
    ) -> list[ScrapedOffer]:
        """Récupère les offres pour un terme de recherche avec pagination."""
        offers: list[ScrapedOffer] = []
        limit = 20
        offset = 0

        headers = {
            **self._browser_headers,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Referer": config.career_page_url,
            "Origin": config.base_url,
        }

        for _page in range(max_pages):
            payload = {
                "appliedFacets": {},
                "limit": limit,
                "offset": offset,
                "searchText": search_text,
            }

            response = client.post(
                config.api_url,
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()

            job_postings = data.get("jobPostings", [])
            if not job_postings:
                break

            for posting in job_postings:
                offer = self._parse_posting(posting, config)
                if offer and self._is_internship(offer.title):
                    offers.append(offer)

            # Vérifier s'il reste des résultats
            total = data.get("total", 0)
            offset += limit
            if offset >= total:
                break

            time.sleep(REQUEST_DELAY_S)

        return offers

    def _parse_posting(
        self,
        posting: dict,
        config: WorkdayConfig,
    ) -> ScrapedOffer | None:
        """Parse un job posting Workday en ScrapedOffer."""
        try:
            title = posting.get("title", "")
            if not title:
                return None

            # Identifiant externe unique
            external_path = posting.get("externalPath", "")
            external_id = (
                f"workday_{config.subdomain}_{external_path}"
                if external_path
                else f"workday_{config.subdomain}_{posting.get('bulletFields', [''])[0]}_{title}"
            )

            # URL de l'offre
            source_url = f"{config.base_url}{external_path}" if external_path else config.career_page_url

            # Localisation (souvent dans bulletFields)
            bullet_fields = posting.get("bulletFields", [])
            location = bullet_fields[0] if bullet_fields else None

            # Date de publication (souvent dans bulletFields)
            posted_on = None
            if len(bullet_fields) > 1:
                posted_on = bullet_fields[1]

            # Description courte
            description = posting.get("descriptionTeaser", "")

            return ScrapedOffer(
                external_id=external_id,
                source_platform=self.platform_name,
                source_url=source_url,
                title=title,
                company_name=config.company_name,
                company_logo_url=None,
                description=description[:5000] if description else None,
                location=location,
                is_remote=False,
                domain="finance",
                contract_type="stage",
                salary=None,
                raw_data={
                    "bullet_fields": bullet_fields,
                    "posted_on": posted_on,
                    "external_path": external_path,
                    "workday_site": config.site_name,
                    "workday_subdomain": config.subdomain,
                },
            )
        except Exception as e:
            logger.warning(f"Parse error Workday posting: {e}")
            return None

    @staticmethod
    def _is_internship(title: str) -> bool:
        """Vérifie si le titre correspond à un stage/internship."""
        title_lower = title.lower()
        return any(kw in title_lower for kw in INTERN_KEYWORDS)


# Enregistrer le scraper
register_scraper(WorkdayScraper())
