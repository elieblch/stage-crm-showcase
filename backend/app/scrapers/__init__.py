# Import des scrapers pour les enregistrer automatiquement
from app.scrapers.registry import get_scraper, list_scrapers, register_scraper

# Import des scrapers concrets (déclenche register_scraper)
from app.scrapers import welcome_jungle  # noqa
from app.scrapers import greenhouse  # noqa
from app.scrapers import smartrecruiters  # noqa
from app.scrapers import workday  # noqa
from app.scrapers import efinancialcareers  # noqa
from app.scrapers import jobteaser  # noqa
