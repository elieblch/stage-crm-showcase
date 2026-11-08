"""
Scraper pour JobTeaser (portail emploi des grandes écoles).
Requiert une authentification via connect.jobteaser.com (OIDC/SSO).

Deux modes d'auth :
  1. Login automatique email/password via connect.jobteaser.com
  2. Fallback : cookie de session manuelle (JOBTEASER_SESSION_COOKIE)
"""

import time
import re
import logging
from html.parser import HTMLParser

import httpx
from bs4 import BeautifulSoup

from app.scrapers.registry import BaseScraper, ScrapedOffer, register_scraper
from app.core.config import get_settings

logger = logging.getLogger(__name__)

REQUEST_DELAY = 1.5  # secondes entre les requêtes
MAX_PAGES = 10
OFFERS_PER_PAGE = 30

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
}


class _HiddenInputParser(HTMLParser):
    """Parse les champs hidden d'un formulaire HTML."""

    def __init__(self) -> None:
        super().__init__()
        self.fields: dict[str, str] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "input":
            d = dict(attrs)
            if d.get("type") == "hidden" and d.get("name") and d.get("value"):
                self.fields[d["name"]] = d["value"]


def _strip_html(html: str) -> str:
    """Supprime les balises HTML et retourne du texte brut."""
    import html as html_mod
    text = html_mod.unescape(html)
    if "&lt;" in text or "&gt;" in text or "&amp;" in text:
        text = html_mod.unescape(text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


class JobTeaserScraper(BaseScraper):
    platform_name = "jobteaser"

    def __init__(self) -> None:
        settings = get_settings()
        self._base_url: str = settings.jobteaser_base_url or "https://em-lyon.jobteaser.com"
        self._email: str = settings.jobteaser_email
        self._password: str = settings.jobteaser_password
        self._session_cookie: str = settings.jobteaser_session_cookie
        # Normalise base URL (retire le slash final)
        self._base_url = self._base_url.rstrip("/")

    def _load_cookie_from_db(self) -> str | None:
        """Charge le cookie de session depuis la table user_integrations (prioritaire)."""
        try:
            from sqlalchemy import create_engine, text
            from app.core.config import get_settings
            s = get_settings()
            sync_url = s.database_url.replace("+asyncpg", "+psycopg2")
            engine = create_engine(sync_url)
            with engine.connect() as conn:
                row = conn.execute(text(
                    "SELECT session_cookie, service_url, session_expires_at "
                    "FROM user_integrations "
                    "WHERE service_name = 'jobteaser' AND is_active = true "
                    "ORDER BY updated_at DESC LIMIT 1"
                )).first()
                if row and row.session_cookie:
                    # Mettre a jour base_url si stocke en BDD
                    if row.service_url:
                        self._base_url = row.service_url.rstrip("/")
                    logger.info("JobTeaser: cookie charge depuis la BDD")
                    return row.session_cookie
        except Exception as e:
            logger.debug(f"JobTeaser: impossible de charger le cookie BDD: {e}")
        return None

    # ── Public ───────────────────────────────────────────────

    def scrape(
        self,
        keywords: list[str] | None = None,
        location: str | None = None,
    ) -> list[ScrapedOffer]:
        """Scrape les offres de stage depuis JobTeaser."""
        all_offers: list[ScrapedOffer] = []

        try:
            client = self._create_authenticated_client()
        except Exception as e:
            logger.warning(f"JobTeaser : authentification échouée — {e}")
            return []

        if client is None:
            logger.warning(
                "JobTeaser : impossible de s'authentifier. "
                "Vérifiez JOBTEASER_EMAIL/PASSWORD ou JOBTEASER_SESSION_COOKIE."
            )
            return []

        search_terms = keywords or [
            "stage",
            "internship",
            "stage finance",
            "stage conseil",
            "stage stratégie",
            "stage audit",
            "stage M&A",
            "stage trading",
            "stage analyste",
        ]

        try:
            for term in search_terms:
                try:
                    offers = self._search_offers(client, term, location)
                    all_offers.extend(offers)
                    logger.info(f"JobTeaser '{term}': {len(offers)} offres")
                except Exception as e:
                    logger.error(f"JobTeaser '{term}' erreur: {e}")
        finally:
            client.close()

        # Dédupliquer par external_id
        seen: set[str] = set()
        unique: list[ScrapedOffer] = []
        for o in all_offers:
            if o.external_id not in seen:
                seen.add(o.external_id)
                unique.append(o)

        logger.info(f"JobTeaser total: {len(unique)} offres uniques")
        return unique

    # ── Authentification ─────────────────────────────────────

    def _create_authenticated_client(self) -> httpx.Client | None:
        """Crée un client HTTP authentifié.

        Essaie dans l'ordre :
        1. Cookie stocke en BDD (via le bouton "Connecter JobTeaser" du profil)
        2. Cookie de session .env (JOBTEASER_SESSION_COOKIE)
        3. Login email/password via connect.jobteaser.com
        """
        # Methode 1 : cookie depuis la BDD (prioritaire)
        db_cookie = self._load_cookie_from_db()
        if db_cookie:
            self._session_cookie = db_cookie
            client = self._try_session_cookie()
            if client:
                logger.info("JobTeaser : authentifie via cookie BDD")
                return client

        # Methode 2 : cookie .env
        if self._session_cookie:
            client = self._try_session_cookie()
            if client:
                logger.info("JobTeaser : authentifie via cookie .env")
                return client

        # Methode 3 : login email/password
        if self._email and self._password:
            client = self._try_login()
            if client:
                logger.info("JobTeaser : authentifie via login email/password")
                return client

        return None

    def _try_session_cookie(self) -> httpx.Client | None:
        """Tente l'auth via un cookie de session fourni manuellement."""
        cookies = self._parse_cookie_string(self._session_cookie)
        if not cookies:
            return None

        client = httpx.Client(
            timeout=30,
            follow_redirects=True,
            headers=HEADERS,
            cookies=cookies,
        )

        # Vérifier que la session est valide
        try:
            time.sleep(REQUEST_DELAY)
            r = client.get(f"{self._base_url}/fr/job-offers")
            if r.status_code == 200 and "job" in r.text.lower():
                return client
            logger.warning(
                f"JobTeaser cookie invalide : status={r.status_code}"
            )
        except Exception as e:
            logger.warning(f"JobTeaser cookie test échoué : {e}")

        client.close()
        return None

    def _try_login(self) -> httpx.Client | None:
        """Tente l'auth via email/password sur connect.jobteaser.com."""
        client = httpx.Client(
            timeout=30,
            follow_redirects=True,
            headers=HEADERS,
        )

        try:
            # Étape 1 : accéder à la page de login (redirige vers connect.jobteaser.com)
            time.sleep(REQUEST_DELAY)
            r1 = client.get(f"{self._base_url}/fr/users/sign_in")
            if r1.status_code != 200:
                logger.warning(f"JobTeaser login page : status={r1.status_code}")
                client.close()
                return None

            # Parser les champs hidden du formulaire
            parser = _HiddenInputParser()
            parser.feed(r1.text)
            hidden_fields = parser.fields

            if "_csrf_token" not in hidden_fields:
                logger.warning("JobTeaser : pas de token CSRF trouvé sur la page de login")
                client.close()
                return None

            # Étape 2 : POST le formulaire de login
            form_data = {
                **hidden_fields,
                "email": self._email,
                "password": self._password,
            }

            time.sleep(REQUEST_DELAY)
            r2 = client.post(
                "https://connect.jobteaser.com/sign_in",
                data=form_data,
                headers={
                    **HEADERS,
                    "Origin": "https://connect.jobteaser.com",
                    "Referer": str(r1.url),
                    "Content-Type": "application/x-www-form-urlencoded",
                },
            )

            # Vérifier si le login a réussi (pas de message d'erreur)
            if "incorrect" in r2.text.lower() or "invalid" in r2.text.lower():
                logger.warning("JobTeaser : identifiants incorrects")
                client.close()
                return None

            # Vérifier l'accès aux offres
            time.sleep(REQUEST_DELAY)
            r3 = client.get(f"{self._base_url}/fr/job-offers")
            if r3.status_code == 200 and self._page_has_offers(r3.text):
                return client

            # Vérifier aussi sur www.jobteaser.com (le login redirige parfois ici)
            time.sleep(REQUEST_DELAY)
            r4 = client.get("https://www.jobteaser.com/fr/job-offers")
            if r4.status_code == 200 and self._page_has_offers(r4.text):
                # Mettre à jour la base URL
                self._base_url = "https://www.jobteaser.com"
                return client

            logger.warning(
                f"JobTeaser : login OK mais accès offres échoué "
                f"(status={r3.status_code}/{r4.status_code})"
            )

        except Exception as e:
            logger.warning(f"JobTeaser login échoué : {e}")

        client.close()
        return None

    # ── Scraping ─────────────────────────────────────────────

    def _search_offers(
        self,
        client: httpx.Client,
        query: str,
        location: str | None,
    ) -> list[ScrapedOffer]:
        """Cherche des offres avec un terme donné, avec pagination."""
        offers: list[ScrapedOffer] = []

        for page in range(1, MAX_PAGES + 1):
            time.sleep(REQUEST_DELAY)

            params: dict[str, str] = {
                "query": query,
                "page": str(page),
                "contractTypes[]": "internship",
            }
            if location:
                params["location"] = location

            try:
                r = client.get(
                    f"{self._base_url}/fr/job-offers",
                    params=params,
                )

                if r.status_code != 200:
                    logger.debug(
                        f"JobTeaser search page {page}: status={r.status_code}"
                    )
                    break

                page_offers = self._parse_offer_list(r.text)

                if not page_offers:
                    # Plus de résultats
                    break

                offers.extend(page_offers)
                logger.debug(
                    f"JobTeaser '{query}' page {page}: {len(page_offers)} offres"
                )

                # Si moins que le nombre attendu, c'est la dernière page
                if len(page_offers) < OFFERS_PER_PAGE // 2:
                    break

            except Exception as e:
                logger.warning(f"JobTeaser page {page} erreur: {e}")
                break

        return offers

    def _parse_offer_list(self, html: str) -> list[ScrapedOffer]:
        """Parse la liste des offres depuis le HTML de la page de résultats."""
        soup = BeautifulSoup(html, "lxml")
        offers: list[ScrapedOffer] = []

        # JobTeaser utilise des cartes d'offres avec des liens vers les détails.
        # Patterns courants : <a> avec href contenant /job-offers/ ou /jobs/
        # et des data-attributes ou des structures de carte.

        # Chercher les liens d'offres
        offer_links = soup.find_all("a", href=re.compile(r"/job-offers?/[^?]+"))
        if not offer_links:
            # Essayer un pattern alternatif
            offer_links = soup.find_all("a", href=re.compile(r"/jobs?/[^?]+"))

        # Aussi chercher les cartes d'offres via des structures connues
        if not offer_links:
            # Chercher des éléments avec des attributs data liés aux offres
            offer_cards = soup.find_all(
                attrs={"data-testid": re.compile(r"job|offer", re.I)}
            )
            if not offer_cards:
                offer_cards = soup.find_all(
                    class_=re.compile(r"job.?card|offer.?card|job.?item", re.I)
                )
            for card in offer_cards:
                link = card.find("a", href=True)
                if link:
                    offer_links.append(link)

        # Parser chaque résultat en JSON-LD si disponible
        json_ld_scripts = soup.find_all("script", type="application/ld+json")
        for script in json_ld_scripts:
            try:
                import json
                data = json.loads(script.string)
                if isinstance(data, list):
                    for item in data:
                        offer = self._parse_json_ld(item)
                        if offer:
                            offers.append(offer)
                elif isinstance(data, dict):
                    if data.get("@type") == "ItemList":
                        for item in data.get("itemListElement", []):
                            offer = self._parse_json_ld(item.get("item", item))
                            if offer:
                                offers.append(offer)
                    else:
                        offer = self._parse_json_ld(data)
                        if offer:
                            offers.append(offer)
            except Exception:
                pass

        if offers:
            return offers

        # Fallback : parser les éléments HTML directement
        # Dédupliquer les liens par href
        seen_hrefs: set[str] = set()
        unique_links = []
        for link in offer_links:
            href = link.get("href", "")
            if href and href not in seen_hrefs:
                seen_hrefs.add(href)
                unique_links.append(link)

        for link in unique_links:
            offer = self._parse_offer_card(link, soup)
            if offer:
                offers.append(offer)

        # Dernière tentative : chercher des données Next.js __NEXT_DATA__
        if not offers:
            next_data = soup.find("script", id="__NEXT_DATA__")
            if next_data and next_data.string:
                offers = self._parse_next_data(next_data.string)

        return offers

    def _parse_json_ld(self, data: dict) -> ScrapedOffer | None:
        """Parse un objet JSON-LD JobPosting en ScrapedOffer."""
        if data.get("@type") != "JobPosting":
            return None

        try:
            title = data.get("title", "Sans titre")
            description = _strip_html(data.get("description", ""))

            # Entreprise
            org = data.get("hiringOrganization", {})
            company_name = org.get("name", "Entreprise inconnue") if isinstance(org, dict) else "Entreprise inconnue"
            logo_url = org.get("logo") if isinstance(org, dict) else None

            # Localisation
            location = None
            loc_data = data.get("jobLocation", {})
            if isinstance(loc_data, dict):
                address = loc_data.get("address", {})
                if isinstance(address, dict):
                    city = address.get("addressLocality", "")
                    country = address.get("addressCountry", "")
                    location = f"{city}, {country}".strip(", ") if city else country
                elif isinstance(address, str):
                    location = address

            # URL
            source_url = data.get("url", data.get("sameAs", ""))
            if source_url and not source_url.startswith("http"):
                source_url = f"{self._base_url}{source_url}"

            # ID externe
            identifier = data.get("identifier", {})
            if isinstance(identifier, dict):
                ext_id = identifier.get("value", "")
            else:
                ext_id = str(identifier) if identifier else ""
            if not ext_id:
                # Extraire un ID de l'URL
                match = re.search(r"/(?:job-offers?|jobs?)/([^/?#]+)", source_url)
                ext_id = match.group(1) if match else title[:50]

            return ScrapedOffer(
                external_id=f"jt-{ext_id}",
                source_platform=self.platform_name,
                source_url=source_url,
                title=title,
                company_name=company_name,
                company_logo_url=logo_url,
                description=description[:5000] if description else None,
                location=location,
                is_remote="remote" in (location or "").lower()
                    or "télétravail" in (description or "").lower(),
                domain=self._detect_domain(title, description),
                contract_type="stage",
                salary=data.get("baseSalary", {}).get("value", {}).get("value")
                    if isinstance(data.get("baseSalary"), dict) else None,
                raw_data={"json_ld": data},
            )
        except Exception as e:
            logger.warning(f"JobTeaser JSON-LD parse error: {e}")
            return None

    def _parse_offer_card(self, link_tag: object, soup: object) -> ScrapedOffer | None:
        """Parse une carte d'offre depuis un élément <a>."""
        try:
            href = link_tag.get("href", "")
            if not href:
                return None

            # Construire l'URL absolue
            if href.startswith("/"):
                source_url = f"{self._base_url}{href}"
            elif href.startswith("http"):
                source_url = href
            else:
                source_url = f"{self._base_url}/{href}"

            # Extraire l'ID de l'URL
            match = re.search(r"/(?:job-offers?|jobs?)/([^/?#]+)", href)
            ext_id = match.group(1) if match else href.split("/")[-1]

            # Remonter au conteneur parent pour trouver le titre et l'entreprise
            card = link_tag
            # Chercher un conteneur parent qui ressemble à une carte
            for _ in range(5):
                parent = card.parent
                if parent and parent.name in ("div", "article", "li", "section"):
                    card = parent
                else:
                    break

            # Titre : le texte du lien ou le premier heading dans la carte
            title = ""
            heading = card.find(["h1", "h2", "h3", "h4"])
            if heading:
                title = heading.get_text(strip=True)
            if not title:
                title = link_tag.get_text(strip=True)
            if not title:
                title = ext_id

            # Entreprise
            company_name = "Entreprise inconnue"
            # Chercher un élément qui contient le nom de l'entreprise
            company_el = card.find(
                class_=re.compile(r"company|employer|organization|entreprise", re.I)
            )
            if company_el:
                company_name = company_el.get_text(strip=True)

            # Localisation
            location = None
            loc_el = card.find(
                class_=re.compile(r"location|city|lieu|localisation", re.I)
            )
            if loc_el:
                location = loc_el.get_text(strip=True)

            # Description courte
            desc_el = card.find(
                class_=re.compile(r"description|summary|excerpt|snippet", re.I)
            )
            description = desc_el.get_text(strip=True) if desc_el else None

            # Logo
            logo = None
            img = card.find("img")
            if img:
                logo = img.get("src") or img.get("data-src")

            if not title or title == ext_id:
                return None

            return ScrapedOffer(
                external_id=f"jt-{ext_id}",
                source_platform=self.platform_name,
                source_url=source_url,
                title=title,
                company_name=company_name,
                company_logo_url=logo,
                description=description[:5000] if description else None,
                location=location,
                is_remote="remote" in (location or "").lower()
                    or "télétravail" in (description or "").lower(),
                domain=self._detect_domain(title, description or ""),
                contract_type="stage",
                raw_data={"source": "html_card"},
            )
        except Exception as e:
            logger.warning(f"JobTeaser card parse error: {e}")
            return None

    def _parse_next_data(self, json_str: str) -> list[ScrapedOffer]:
        """Parse les données Next.js __NEXT_DATA__ pour extraire les offres."""
        import json
        offers: list[ScrapedOffer] = []

        try:
            data = json.loads(json_str)
            props = data.get("props", {}).get("pageProps", {})

            # Chercher des listes d'offres dans les pageProps
            offer_lists = self._find_offer_lists(props)

            for offer_data in offer_lists:
                offer = self._parse_next_offer(offer_data)
                if offer:
                    offers.append(offer)

        except Exception as e:
            logger.warning(f"JobTeaser NEXT_DATA parse error: {e}")

        return offers

    def _find_offer_lists(self, data: dict | list, depth: int = 0) -> list[dict]:
        """Cherche récursivement des listes d'offres dans un objet JSON."""
        if depth > 5:
            return []

        results: list[dict] = []

        if isinstance(data, dict):
            # Vérifier si c'est une offre
            if any(k in data for k in ("title", "name")) and any(
                k in data for k in ("company", "organization", "employer", "companyName")
            ):
                results.append(data)

            # Parcourir les valeurs
            for key, value in data.items():
                if isinstance(value, (dict, list)):
                    results.extend(self._find_offer_lists(value, depth + 1))

        elif isinstance(data, list):
            for item in data:
                if isinstance(item, (dict, list)):
                    results.extend(self._find_offer_lists(item, depth + 1))

        return results

    def _parse_next_offer(self, data: dict) -> ScrapedOffer | None:
        """Parse une offre depuis les données Next.js."""
        try:
            title = data.get("title") or data.get("name", "Sans titre")
            ext_id = str(
                data.get("id")
                or data.get("slug")
                or data.get("externalId")
                or title[:50]
            )

            company = (
                data.get("company", {})
                or data.get("organization", {})
                or data.get("employer", {})
            )
            company_name = (
                company.get("name")
                or data.get("companyName")
                or "Entreprise inconnue"
            ) if isinstance(company, dict) else str(company)

            # URL
            slug = data.get("slug") or ext_id
            source_url = data.get("url") or f"{self._base_url}/fr/job-offers/{slug}"

            # Localisation
            location = (
                data.get("location")
                or data.get("city")
                or (data.get("address", {}) or {}).get("city")
            )
            if isinstance(location, dict):
                location = location.get("name") or location.get("city")

            description = data.get("description") or data.get("summary") or ""
            if description:
                description = _strip_html(description)

            return ScrapedOffer(
                external_id=f"jt-{ext_id}",
                source_platform=self.platform_name,
                source_url=source_url,
                title=title,
                company_name=company_name,
                company_logo_url=(company.get("logo") or company.get("logoUrl"))
                    if isinstance(company, dict) else None,
                description=description[:5000] if description else None,
                location=str(location) if location else None,
                is_remote=data.get("remote", False)
                    or "remote" in str(location or "").lower(),
                domain=self._detect_domain(title, description),
                contract_type=data.get("contractType") or "stage",
                duration_months=data.get("duration") or data.get("durationMonths"),
                start_date=None,
                salary=data.get("salary") or data.get("compensation"),
                raw_data={"next_data": {k: v for k, v in data.items()
                          if k in ("id", "slug", "contractType", "sectors",
                                   "publishedAt", "updatedAt", "remote")}},
            )
        except Exception as e:
            logger.warning(f"JobTeaser Next.js offer parse error: {e}")
            return None

    # ── Helpers ───────────────────────────────────────────────

    @staticmethod
    def _page_has_offers(html: str) -> bool:
        """Vérifie si une page contient des offres d'emploi."""
        indicators = [
            "job-offer", "job_offer", "jobOffer",
            "offer-card", "offer_card", "offerCard",
            "data-job", "data-offer",
            "JobPosting",
        ]
        html_lower = html.lower()
        return any(ind.lower() in html_lower for ind in indicators)

    @staticmethod
    def _parse_cookie_string(cookie_str: str) -> dict[str, str]:
        """Parse une chaîne de cookies 'key=value; key2=value2' en dict."""
        cookies: dict[str, str] = {}
        if not cookie_str:
            return cookies
        for part in cookie_str.split(";"):
            part = part.strip()
            if "=" in part:
                key, _, value = part.partition("=")
                cookies[key.strip()] = value.strip()
        return cookies

    @staticmethod
    def _detect_domain(title: str, description: str) -> str:
        """Détecte le domaine (finance, conseil, etc.) depuis le titre/description."""
        text = f"{title} {description}".lower()

        finance_kw = {
            "finance", "trading", "m&a", "private equity", "asset management",
            "risk", "compliance", "investment", "bancaire", "banque",
            "restructuring", "valuation", "structuration", "sales",
        }
        conseil_kw = {
            "conseil", "consulting", "strategy", "stratégie",
            "advisory", "consultant", "due diligence",
        }
        audit_kw = {"audit", "contrôle de gestion", "comptabilité"}

        if any(kw in text for kw in finance_kw):
            return "finance"
        if any(kw in text for kw in conseil_kw):
            return "conseil"
        if any(kw in text for kw in audit_kw):
            return "audit"
        return "general"


# Enregistrer le scraper
register_scraper(JobTeaserScraper())
