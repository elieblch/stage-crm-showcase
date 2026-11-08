# Stage CRM — Tracker manuel de recherche de stage

> Tracker **100 % manuel** pour organiser sa recherche de stage (finance, conseil, stratégie)
> et **ne jamais oublier une relance**. Aucun scraping, aucune IA, aucun appel réseau payant —
> l'utilisateur saisit lui-même ses offres et ses contacts.

L'ancien moteur automatique (scraping + scoring IA + génération de candidatures + Celery +
newsletter) est archivé dans la branche **`v1-full-auto-showcase`**.

> **Auto-hébergé, pas de compte.** Tu clones le dépôt et tu lances **ta propre instance**
> sur **ta** machine, avec **ta** base. Il n'y a **aucune authentification** et **aucun
> multi-tenant** : *une instance = un utilisateur*. Le dépôt ne contient que du code —
> aucune donnée n'est partagée entre instances.

## Architecture

```
stage-crm/
├── backend/                 # FastAPI + Python 3.12 (async)
│   ├── app/
│   │   ├── api/routes/      # Endpoints REST
│   │   ├── core/            # Config, DB (Alembic check au démarrage)
│   │   ├── models/          # SQLAlchemy : offers, contacts, interview_stories, settings
│   │   ├── schemas/         # Pydantic
│   │   └── services/        # relance_service (logique de relance, pure)
│   ├── tests/               # pytest (unit + intégration)
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/                # Next.js 14 + TypeScript + Tailwind
│   └── src/{app,components,lib,types}
├── docker-compose.yml       # 3 services : db, backend, frontend
├── scripts/setup.sh         # setup / mise à jour, idempotent
├── Makefile                 # raccourcis (make help)
├── .env.example
└── README.md
```

## Stack technique

| Composant | Technologie | Rôle |
|-----------|-------------|------|
| Backend API | FastAPI (Python 3.12, async) | API REST, logique de relance |
| Frontend | Next.js 14 + TypeScript + Tailwind | Interface (Dashboard, Offres, Contacts, Stories, Réglages) |
| Base de données | PostgreSQL 16 | Stockage persistant |
| Graphiques | Recharts | Répartition par statut |
| Tests | pytest + httpx | Unitaires (relance) + intégration |

## Installation (auto-hébergement)

### Prérequis

- **Docker** et **Docker Compose v2** (la commande `docker compose`, pas `docker-compose`).
  Docker Desktop sur macOS/Windows, Docker Engine sur Linux.
- Rien d'autre : ni Python, ni Node, ni clé d'API, ni compte en ligne.

### Installation en une commande

```bash
git clone <repo-url> stage-crm
cd stage-crm
./scripts/setup.sh          # ou : make setup
```

Le script est **idempotent** (relançable sans risque) et fait, dans l'ordre :

1. vérifie que Docker tourne ;
2. crée `.env` depuis `.env.example` s'il n'existe pas (valeurs par défaut utilisables telles quelles) ;
3. construit les images `backend` et `frontend` ;
4. démarre PostgreSQL et attend son *healthcheck* ;
5. applique le schéma via un conteneur **one-off** : `docker compose run --rm --no-deps backend alembic upgrade head` ;
6. démarre la stack complète.

<details>
<summary>Étapes équivalentes à la main</summary>

```bash
cp .env.example .env
docker compose build
docker compose up -d db
docker compose run --rm --no-deps backend alembic upgrade head
docker compose up -d
```
</details>

### Accès

| Service | URL par défaut |
|---------|----------------|
| Application | http://localhost:3000 |
| API | http://localhost:8000 |
| Documentation API (Swagger) | http://localhost:8000/docs |

Pas d'écran de connexion : l'application s'ouvre directement, vierge (0 offre, 0 contact).

> **Ports déjà pris ?** Modifie `FRONTEND_PORT`, `BACKEND_PORT` ou `DB_PORT` dans `.env`,
> puis relance `./scripts/setup.sh`.

### Configuration

Toutes les variables sont documentées une par une dans **`.env.example`** :
identifiants et nom de la base, ports publiés, `APP_ENV`, `FRONTEND_URL`,
répertoire et taille max des uploads. `.env` est ignoré par git et ne doit
jamais être versionné.

### Où sont stockées les données

**Tes données restent sur ta machine, isolées.** Rien n'est envoyé nulle part :
l'application ne fait aucun appel réseau sortant.

| Donnée | Emplacement |
|--------|-------------|
| Offres, contacts, stories, entretiens, historique | Volume Docker **`pgdata`** (PostgreSQL) |
| PDF de CV / lettres de motivation | Volume Docker **`user_uploads`** |
| Configuration locale | Fichier **`.env`** (non versionné) |

Les volumes sont nommés d'après le projet Compose (par défaut `stage-crm_pgdata`,
`stage-crm_user_uploads`) : deux clones dans deux dossiers différents ont donc des
bases **physiquement séparées**.

Sauvegarde ponctuelle :

```bash
mkdir -p backups
docker compose exec -T db pg_dump -U "$DB_USER" "$DB_NAME" > backups/stage-crm_$(date +%F).sql
```

### Mise à jour

```bash
git pull
docker compose build
docker compose run --rm --no-deps backend alembic upgrade head
docker compose up -d
```

…ou simplement `./scripts/setup.sh` (équivalent, `make update`) : il détecte le
`.env` existant, reconstruit, migre et redémarre sans toucher aux données.

Le schéma est géré par **Alembic**. Le démarrage de l'API **vérifie** seulement que
la base est alignée sur `head` et logge un WARNING sinon — il n'applique **jamais**
de migration et n'exécute aucun DDL. Les migrations sont toujours explicites.

### Remise à zéro

```bash
make reset          # demande une confirmation tapée à la main
```

Équivalent à `docker compose down -v` : cela **supprime définitivement** la base
et les PDF uploadés. Relance ensuite `./scripts/setup.sh` pour repartir d'une
instance vierge.

## Fonctionnalités

### Dashboard
- Compteurs par statut (offres + contacts)
- **Relances à faire** en tête de page, triées par urgence, avec bouton « marqué comme relancé »
- Alertes des deadlines de candidature proches (≤ 3 jours)
- Répartition des offres par statut (donut)

### Offres en ligne
- Ajout manuel (intitulé, entreprise, lien, source, priorité, statut, dates, deadline, notes)
- Upload **CV + lettre de motivation (PDF)** avec lien de téléchargement
- Badge « relance nécessaire », filtres statut/priorité
- Vue liste **ou** Kanban par statut (drag & drop)
- Fiche détail avec les contacts liés

### Personnes contactées
- CRUD complet (nom, rôle, entreprise, email, LinkedIn, téléphone, statut, dates, notes)
- Lien optionnel vers une offre
- Badge + action de relance

### Stories (Story Bank STAR)
- Wizard 5 étapes (Situation / Task / Action / Result + tags)
- Filtres par tags

### Profil / Réglages
- Délai de relance par défaut (`relance_delay_days`, défaut 10 jours)

## Logique de relance

Calculée **à la volée** (pas de scheduler). Une entrée nécessite une relance si elle n'est pas
marquée « sans relance », que son statut est « en attente de réponse », et que l'échéance est
atteinte : `next_relance_date` si défini (override manuel prioritaire), sinon
`last_action_date + relance_delay_days`.

## Développement

`make help` liste toutes les cibles disponibles.

```bash
make logs                # logs du backend
make test                # pytest
make shell               # shell dans le conteneur backend
make migration-status    # révision courante vs head
make migrate             # appliquer les migrations en attente (après relecture)
make down                # arrêter la stack — les données sont CONSERVÉES
```

Générer une migration (à **relire** avant application) :

```bash
docker compose exec backend alembic revision --autogenerate -m "..."
# → relecture manuelle de backend/alembic/versions/*.py OBLIGATOIRE
make migrate
```

> ⚠️ `docker compose down -v` **détruit** les volumes `pgdata` et `user_uploads`
> (toutes les données). À n'utiliser que pour un reset volontaire — voir `make reset`.

## Licence

Tous droits réservés — voir [`LICENSE`](../LICENSE).
