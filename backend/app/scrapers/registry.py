"""
Registre de scrapers — chaque plateforme est un module séparé.
Pour ajouter une plateforme : créer un fichier dans scrapers/ et l'enregistrer ici.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date


@dataclass
class ScrapedOffer:
    """Structure standardisée d'une offre scrapée."""
    external_id: str
    source_platform: str
    source_url: str
    title: str
    company_name: str
    company_logo_url: str | None = None
    description: str | None = None
    location: str | None = None
    is_remote: bool = False
    domain: str | None = None
    contract_type: str | None = None
    duration_months: int | None = None
    start_date: date | None = None
    salary: str | None = None
    required_skills: list[str] | None = None
    required_education: str | None = None
    contact_name: str | None = None
    contact_email: str | None = None
    raw_data: dict | None = None


class BaseScraper(ABC):
    """Classe de base pour tous les scrapers."""

    platform_name: str = ""

    @abstractmethod
    def scrape(self, keywords: list[str] = None, location: str = None) -> list[ScrapedOffer]:
        """Scrape la plateforme et retourne les offres standardisées."""
        pass

    def filter_finance_conseil(self, offers: list[ScrapedOffer]) -> list[ScrapedOffer]:
        """Pré-filtre pour garder uniquement les offres finance/conseil/stratégie."""
        finance_keywords = {
            "finance", "conseil", "consulting", "stratégie", "strategy",
            "m&a", "audit", "transaction", "advisory", "investment",
            "private equity", "venture capital", "asset management",
            "risk", "compliance", "corporate finance", "restructuring",
            "due diligence", "valuation", "analyst", "analyste",
        }
        filtered = []
        for offer in offers:
            text = f"{offer.title} {offer.description or ''} {offer.domain or ''}".lower()
            if any(kw in text for kw in finance_keywords):
                filtered.append(offer)
        return filtered


# ── Scrapers enregistrés ──────────────────────────────────

_scrapers: dict[str, BaseScraper] = {}


def register_scraper(scraper: BaseScraper):
    """Enregistre un scraper dans le registre."""
    _scrapers[scraper.platform_name] = scraper


def get_scraper(name: str) -> BaseScraper | None:
    """Récupère un scraper par nom de plateforme."""
    return _scrapers.get(name)


def list_scrapers() -> list[str]:
    """Liste les plateformes disponibles."""
    return list(_scrapers.keys())
