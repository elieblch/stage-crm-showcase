# Stage CRM — v1 : moteur automatique (snapshot archivé)

> **Snapshot archivé du moteur automatique** (scraping multi-plateformes, scoring hybride
> 8 dimensions, intégration IA, Celery). Fourni à titre de **démonstration d'architecture** ;
> peut ne pas tourner tel quel (dépendances/API non fournies).

La version active du projet (tracker manuel) et l'histoire du pivot sont sur la branche
**[`main`](../../tree/main)**.

## Ce que contient cette branche

| Zone | Fichiers | Rôle |
|---|---|---|
| Scraping | `backend/app/scrapers/` | 6 sources (Welcome to the Jungle, JobTeaser, eFinancialCareers, Greenhouse, SmartRecruiters, Workday) derrière une interface `BaseScraper` + registre |
| Scoring | `backend/app/services/scoring_service.py` | Scoring hybride sur 8 dimensions, poids configurables |
| IA | `backend/app/services/claude_service.py` | Score de correspondance, lettres, emails, adaptation du CV, préparation d'entretien |
| Asynchrone | `backend/app/core/celery_app.py`, `*_tasks.py` | Scraping planifié, relances, newsletter (Celery + Redis) |
| Frontend | `frontend/src/` | Next.js + TypeScript : recherche, radar de score, suivi, profil |

## Différences avec le code d'origine

Ce snapshot a été nettoyé avant publication :

- identité personnelle retirée du code (nom, email, formation) → placeholders ou
  variables d'environnement (`USER_EDUCATION`) ;
- identifiants Algolia de Welcome to the Jungle sortis du code → `WTTJ_ALGOLIA_APP_ID` /
  `WTTJ_ALGOLIA_API_KEY` ;
- schéma SQL initial (`docker/init.sql`) et état du scheduler Celery non inclus.

La documentation technique d'origine se trouve dans [`docs/INSTALL.md`](docs/INSTALL.md).

## Licence

© 2026 Elie Blecher. Tous droits réservés. Voir [`LICENSE`](LICENSE).
