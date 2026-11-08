"""
Scraper pour eFinancialCareers — site spécialisé finance.
Parse le HTML SSR (Angular) des pages de résultats et extrait le JSON-LD
des pages de détail.
"""

import re
import time
import json
import logging
import html as html_mod
from dataclasses import dataclass
from datetime import date

import httpx

from app.scrapers.registry import BaseScraper, ScrapedOffer, register_scraper

logger = logging.getLogger(__name__)

BASE_URL = "https://www.efinancialcareers.fr"

# Mots-clés de recherche généralistes (stages en France)
DEFAULT_SEARCH_QUERIES: list[str] = [
    "stage",
    "internship",
    "stagiaire",
    "apprentissage",
    "alternance",
]

REQUEST_DELAY = 0.6  # secondes entre les requêtes (réduit de 1.5 → 0.6 pour perf)
MAX_PAGES = 5         # pages par requête de recherche
RESULTS_PER_PAGE = 20

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
}


@dataclass
class _CardInfo:
    """Info extraite d'une carte de résultat (listing page)."""
    job_id: str
    pla_id: str
    title: str
    company: str
    location: str
    contract_type: str
    salary: str
    url: str


def _strip_html(html: str) -> str:
    """Supprime les balises HTML et retourne du texte brut."""
    text = html_mod.unescape(html)
    if "&lt;" in text or "&gt;" in text or "&amp;" in text:
        text = html_mod.unescape(text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _parse_cards(html: str) -> list[_CardInfo]:
    """Parse les cartes de résultats depuis le HTML d'une page de listing."""
    cards_html = re.findall(
        r"<efc-job-card[^>]*>(.*?)</efc-job-card>", html, re.S
    )
    results: list[_CardInfo] = []

    for card in cards_html:
        # Titre et URL
        m_title = re.search(
            r'<a[^>]*class="[^"]*job-title[^"]*"[^>]*'
            r'href="([^"]+)"[^>]*title="([^"]+)"',
            card,
        )
        if not m_title:
            continue
        url = m_title.group(1)
        title = html_mod.unescape(m_title.group(2)).strip()

        # ID numérique depuis l'URL
        m_id = re.search(r"\.id(\d+)", url)
        job_id = m_id.group(1) if m_id else ""

        # data-pla-id
        m_pla = re.search(r'data-pla-id="([^"]+)"', card)
        pla_id = m_pla.group(1) if m_pla else ""

        # Entreprise
        m_company = re.search(r'class="[^"]*company[^"]*">\s*([^<]+)', card)
        company = m_company.group(1).strip() if m_company else ""

        # Champs dot-divider : [localisation, type contrat, ...]
        dividers = re.findall(
            r'class="dot-divider[^"]*"[^>]*>([^<]+)', card
        )
        dividers = [d.strip() for d in dividers if d.strip()]

        location = dividers[0] if len(dividers) >= 1 else ""
        contract_type = dividers[1] if len(dividers) >= 2 else ""

        # Salaire
        m_salary = re.search(
            r'class="[^"]*last-job-criteria[^"]*">([^<]+)', card
        )
        salary = m_salary.group(1).strip() if m_salary else ""

        results.append(
            _CardInfo(
                job_id=job_id,
                pla_id=pla_id,
                title=title,
                company=company,
                location=location,
                contract_type=contract_type,
                salary=salary,
                url=url,
            )
        )

    return results


def _parse_detail_jsonld(html: str) -> dict | None:
    """Extrait le bloc JSON-LD JobPosting d'une page de détail."""
    blocks = re.findall(
        r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',
        html,
        re.S,
    )
    for block in blocks:
        try:
            data = json.loads(block)
            if data.get("@type") == "JobPosting":
                return data
        except (json.JSONDecodeError, TypeError):
            continue
    return None


def _normalize_contract_type(raw: str) -> str:
    """Normalise le type de contrat affiché par eFinancialCareers."""
    raw_lower = raw.lower()
    if any(k in raw_lower for k in ("stage", "intern", "stagiaire")):
        return "stage"
    if any(k in raw_lower for k in ("apprenti", "alternance", "apprenticeship")):
        return "alternance"
    if "cdi" in raw_lower:
        return "CDI"
    if "cdd" in raw_lower or "intérim" in raw_lower or "contract" in raw_lower:
        return "CDD"
    return raw


class EFinancialCareersScraper(BaseScraper):
    platform_name = "efinancialcareers"

    def scrape(
        self,
        keywords: list[str] | None = None,
        location: str | None = None,
    ) -> list[ScrapedOffer]:
        """Scrape eFinancialCareers pour les offres de stage en France."""
        search_queries = keywords or DEFAULT_SEARCH_QUERIES
        all_cards: dict[str, _CardInfo] = {}  # job_id -> CardInfo (dedup)

        # Charger les offres déjà en BDD pour éviter de re-fetcher leurs détails
        known_ids = self._load_known_external_ids()
        logger.info(
            f"eFinancialCareers: {len(known_ids)} offres déjà en BDD (skip détail)"
        )

        t0 = time.time()
        with httpx.Client(
            timeout=20, headers=HEADERS, follow_redirects=True
        ) as client:
            # Phase 1 : collecter les cartes depuis les pages de listing
            t_phase1 = time.time()
            for query in search_queries:
                self._collect_cards(client, query, all_cards)
            logger.info(
                f"eFinancialCareers phase 1 (listings): "
                f"{len(all_cards)} cartes uniques en {time.time()-t_phase1:.1f}s"
            )

            # Filtrer par pays France
            france_cards = {
                k: v
                for k, v in all_cards.items()
                if "france" in v.location.lower() or ", fr" in v.location.lower()
            }
            logger.info(
                f"eFinancialCareers: {len(france_cards)} cartes en France"
            )

            # Construire les offres : détail léger depuis la carte pour les connues,
            # fetch complet uniquement pour les nouvelles
            t_phase2 = time.time()
            offers: list[ScrapedOffer] = []
            new_count = 0
            skipped_count = 0
            for card in france_cards.values():
                ext_id = f"efc-{card.job_id}"
                if ext_id in known_ids:
                    skipped_count += 1
                    continue
                try:
                    offer = self._fetch_detail(client, card)
                    if offer:
                        offers.append(offer)
                        new_count += 1
                except Exception as e:
                    logger.warning(
                        f"eFinancialCareers détail {card.job_id}: {e}"
                    )
            logger.info(
                f"eFinancialCareers phase 2 (détails): "
                f"{new_count} nouvelles fetchées, {skipped_count} skip (déjà BDD) "
                f"en {time.time()-t_phase2:.1f}s"
            )

        # Filtrer finance/conseil (uniquement sur les nouvelles offres)
        filtered = self.filter_finance_conseil(offers)
        logger.info(
            f"eFinancialCareers total: {len(offers)} offres nouvelles, "
            f"{len(filtered)} après filtre finance/conseil | "
            f"durée totale: {time.time()-t0:.1f}s"
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
                    "WHERE source_platform = 'efinancialcareers'"
                )).fetchall()
                return {r[0] for r in rows}
        except Exception as e:
            logger.warning(f"eFinancialCareers: impossible de charger les IDs BDD: {e}")
            return set()

    def _collect_cards(
        self,
        client: httpx.Client,
        query: str,
        cards_dict: dict[str, _CardInfo],
    ) -> None:
        """Collecte les cartes pour une requête, avec pagination."""
        for page in range(1, MAX_PAGES + 1):
            url = (
                f"{BASE_URL}/jobs"
                f"?q={query}&countryCode=FR&page={page}"
            )
            time.sleep(REQUEST_DELAY)
            try:
                resp = client.get(url)
                if resp.status_code != 200:
                    logger.warning(
                        f"eFinancialCareers listing {resp.status_code}: {url}"
                    )
                    break

                page_cards = _parse_cards(resp.text)
                if not page_cards:
                    logger.debug(
                        f"eFinancialCareers: plus de résultats pour "
                        f"'{query}' page {page}"
                    )
                    break

                new_count = 0
                for card in page_cards:
                    if card.job_id and card.job_id not in cards_dict:
                        cards_dict[card.job_id] = card
                        new_count += 1

                logger.debug(
                    f"eFinancialCareers '{query}' p{page}: "
                    f"{len(page_cards)} cartes, {new_count} nouvelles"
                )

                # Arrêter si page incomplète (dernière page)
                if len(page_cards) < RESULTS_PER_PAGE:
                    break

            except httpx.HTTPError as e:
                logger.error(
                    f"eFinancialCareers requête échouée '{query}' p{page}: {e}"
                )
                break

    def _fetch_detail(
        self,
        client: httpx.Client,
        card: _CardInfo,
    ) -> ScrapedOffer | None:
        """Récupère la page de détail et construit un ScrapedOffer."""
        time.sleep(REQUEST_DELAY)
        resp = client.get(card.url)
        if resp.status_code != 200:
            logger.warning(
                f"eFinancialCareers détail {resp.status_code}: {card.url}"
            )
            return None

        jsonld = _parse_detail_jsonld(resp.text)

        # Extraire la description (JSON-LD ou fallback HTML)
        description = None
        if jsonld and jsonld.get("description"):
            description = _strip_html(jsonld["description"])
        else:
            # Fallback: chercher la section description dans le HTML
            m = re.search(
                r'class="[^"]*job-description[^"]*"[^>]*>(.*?)</(?:div|section)>',
                resp.text,
                re.S,
            )
            if m:
                description = _strip_html(m.group(1))

        # Titre propre (JSON-LD inclut parfois la ville)
        title = card.title
        if jsonld:
            raw_title = jsonld.get("title", "")
            # Format: "Titre | Ville, CC" — on garde la partie avant le pipe
            clean = raw_title.split("|")[0].strip()
            if clean:
                title = clean

        # Entreprise
        company = card.company
        if jsonld:
            company = (
                jsonld.get("hiringOrganization", {}).get("name") or company
            )

        # Logo
        logo_url = None
        if jsonld:
            logo_url = jsonld.get("hiringOrganization", {}).get("logo")

        # Localisation enrichie
        location = card.location
        if jsonld:
            addr = jsonld.get("jobLocation", {}).get("address", {})
            city = addr.get("addressLocality", "")
            region = addr.get("addressRegion", "")
            country = addr.get("addressCountry", "")
            parts = [p for p in (city, region, country) if p]
            if parts:
                location = ", ".join(parts)

        # Salaire
        salary = card.salary if card.salary and card.salary != "Competitive" else None
        if jsonld:
            base_salary = jsonld.get("baseSalary", {})
            val = base_salary.get("value", {})
            if isinstance(val, dict):
                amount = val.get("value", "")
                unit = val.get("unitText", "")
                currency = base_salary.get("currency", "")
                if amount and amount != "Competitive":
                    salary = f"{amount} {currency}/{unit}".strip()

        # Date de publication
        start_date = None
        if jsonld and jsonld.get("datePosted"):
            try:
                date_str = jsonld["datePosted"][:10]
                start_date = date.fromisoformat(date_str)
            except (ValueError, TypeError):
                pass

        # Type de contrat
        contract_type = _normalize_contract_type(card.contract_type)

        # Remote
        is_remote = False
        if location and "remote" in location.lower():
            is_remote = True
        if description and "télétravail" in description.lower():
            is_remote = True

        return ScrapedOffer(
            external_id=f"efc-{card.job_id}",
            source_platform=self.platform_name,
            source_url=card.url,
            title=title,
            company_name=company,
            company_logo_url=logo_url,
            description=description[:5000] if description else None,
            location=location,
            is_remote=is_remote,
            domain="finance",
            contract_type=contract_type,
            salary=salary,
            raw_data={
                "efc_job_id": card.job_id,
                "efc_pla_id": card.pla_id,
                "date_posted": (
                    jsonld.get("datePosted") if jsonld else None
                ),
                "valid_through": (
                    jsonld.get("validThrough") if jsonld else None
                ),
                "employment_type": (
                    jsonld.get("employmentType") if jsonld else None
                ),
                "skills": (
                    jsonld.get("skills") if jsonld else None
                ),
            },
        )


# Enregistrer le scraper
register_scraper(EFinancialCareersScraper())
