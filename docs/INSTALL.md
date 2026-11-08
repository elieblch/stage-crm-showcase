# Stage CRM — Secrétaire IA de recherche de stage

> CRM intelligent pour automatiser la recherche de stages en finance, conseil et stratégie.

## Architecture

```
stage-crm/
├── backend/                 # FastAPI + Python
│   ├── app/
│   │   ├── api/routes/      # Endpoints REST
│   │   ├── core/            # Config, DB, Celery
│   │   ├── models/          # SQLAlchemy models
│   │   ├── schemas/         # Pydantic schemas
│   │   ├── scrapers/        # Scrapers par plateforme
│   │   ├── services/        # Logique métier + Claude AI
│   │   └── templates/       # Templates email (Jinja2)
│   ├── alembic/             # Migrations DB
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/                # Next.js + TypeScript
│   ├── src/
│   │   ├── app/             # Pages (App Router)
│   │   ├── components/      # Composants React
│   │   ├── lib/             # API client, utils
│   │   ├── hooks/           # Custom hooks
│   │   └── types/           # Types TypeScript
│   ├── Dockerfile
│   └── package.json
├── docker/
│   └── init.sql             # Schema PostgreSQL initial (non inclus dans ce snapshot)
├── scripts/
│   └── setup.sh             # Setup en une commande
├── docker-compose.yml       # Orchestration complète
├── .env.example             # Template variables d'environnement
└── README.md
```

## Stack technique

| Composant | Technologie | Rôle |
|-----------|-------------|------|
| Backend API | FastAPI (Python 3.12) | API REST, logique métier |
| Frontend | Next.js 14 + TypeScript | Interface utilisateur |
| Base de données | PostgreSQL 16 | Stockage persistant |
| Cache & Queue | Redis 7 | File de tâches Celery |
| Tâches async | Celery + Beat | Scraping quotidien, newsletter |
| Intelligence | API Claude (Anthropic) | Scoring, génération CV/LM |
| Scraping | httpx + BeautifulSoup + Playwright | Récupération des offres |
| Email | Gmail API | Envoi de candidatures et newsletters |

## Démarrage rapide

### Prérequis
- Docker & Docker Compose
- Une clé API Anthropic ([console.anthropic.com](https://console.anthropic.com))

### Installation

```bash
git clone <repo-url> stage-crm
cd stage-crm
chmod +x scripts/setup.sh
./scripts/setup.sh
```

### Configuration

Édite le fichier `.env` :

```env
# Obligatoire
ANTHROPIC_API_KEY=sk-ant-xxxxx

# Pour l'envoi d'emails (optionnel au début)
GMAIL_CLIENT_ID=xxxxx
GMAIL_CLIENT_SECRET=xxxxx
```

### Accès

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| API | http://localhost:8000 |
| Documentation API | http://localhost:8000/docs |

## Fonctionnalités

### 1. Recherche intelligente
- Scan quotidien automatique (6h) des plateformes d'emploi
- Scoring IA de chaque offre vs ton profil (0-100)
- Newsletter quotidienne (8h) avec les meilleures offres
- Préférences modifiables à tout moment

### 2. Aide à la candidature
- Upload de documents (CV, bulletins, projets, certifications)
- Suggestions d'adaptation de CV par offre
- Génération de lettres de motivation personnalisées
- Draft automatique d'emails de candidature
- Identification des contacts pertinents

### 3. Suivi (Pipeline)
- Vue kanban : Brouillon → Envoyé → Entretien → Offre → Accepté
- Fiches de préparation d'entretien générées par IA
- Système de relances automatiques
- Historique complet de chaque candidature

## Plateformes scrapées

- Welcome to the Jungle
- Indeed France
- LinkedIn Jobs
- Dogfinance
- JobTeaser
- (extensible : ajoute un fichier dans `backend/app/scrapers/`)

## Développement

```bash
# Logs en temps réel
docker compose logs -f

# Relancer le backend après modif
docker compose restart backend

# Shell dans le backend
docker compose exec backend bash

# Lancer un scraping manuellement
docker compose exec backend python -c "
from app.services.scraping_tasks import run_daily_scraping
run_daily_scraping()
"

# Reset la base de données
docker compose down -v
docker compose up -d
```

## Roadmap

- [x] Phase 1 : Setup, BDD, architecture
- [ ] Phase 2 : Scrapers + scoring IA + newsletter
- [ ] Phase 3 : Génération CV/LM + intégration Gmail
- [ ] Phase 4 : Pipeline kanban + fiches entretien
- [ ] Phase 5 : Commercialisation (multi-tenant, auth, billing)

## Licence

Projet personnel — usage privé.
