# Stage CRM — du moteur automatique au tracker manuel

> Un CRM pour piloter une recherche de stage en finance de marché, de la première offre
> repérée jusqu'à la signature. Et l'histoire d'un pivot : j'ai construit un moteur
> automatique complet (scraping, scoring, IA, tâches asynchrones), puis j'ai choisi de
> le remplacer par un outil plus simple, qui m'apportait davantage.

![Dashboard — offres et contacts par statut, relances à faire](Installation%20et%20captures%20d'%C3%A9cran%20du%20projet/screenshots/dashboard.png)

---

## Le projet

Une recherche de stage en finance, ce sont des dizaines d'offres, autant de contacts
(analystes, RH, alumni), des deadlines, des entretiens en plusieurs tours et surtout des
**relances** à ne pas oublier. Un tableur ne suffit plus assez vite : on perd le fil de
qui a été contacté, quand, et ce qu'il faut faire ensuite.

L'objectif : **un seul outil pour piloter la recherche de A à Z** (offres, contacts,
documents envoyés, entretiens, relances, statistiques), auto-hébergé, sans compte et sans
donnée partagée.

---

## v1 — le moteur automatique

👉 Code archivé sur la branche **[`v1-full-auto-showcase`](../../tree/v1-full-auto-showcase)**.

La première version cherchait à **automatiser toute la chaîne** :

- **Scraping de 6 sources** : Welcome to the Jungle, JobTeaser, eFinancialCareers, et les
  ATS Greenhouse, SmartRecruiters et Workday. Chaque scraper est un module séparé derrière
  une interface commune (`BaseScraper` + registre), qui produit une offre normalisée.
- **Scoring hybride sur 8 dimensions** : règles déterministes (mots-clés, domaine,
  localisation, durée, formation…) plus une dimension évaluée par IA, avec des poids
  réglables depuis l'interface et un radar de score par offre.
- **IA (API Claude)** pour le score de correspondance offre / profil, la génération de
  lettres de motivation et d'emails, des suggestions d'adaptation du CV et la préparation
  d'entretiens (avec cache des réponses). L'extraction du CV, elle, reste à base de règles.
- **Pipeline asynchrone Celery** (worker + beat) : scraping planifié, relances automatiques,
  newsletter HTML récapitulative par email.

Techniquement, ça marchait. C'est justement ce qui a rendu la décision suivante
intéressante.

---

## La décision : pourquoi j'ai pivoté

Après quelques semaines d'usage réel, j'ai fait le bilan honnête de **ce que le moteur
coûtait par rapport à ce qu'il m'apportait** :

- **Coût** : chaque offre scorée ou chaque candidature générée consommait des tokens. Sur des
  centaines d'offres scrapées, dont l'immense majorité n'était pas pertinente, la facture
  augmentait pour un gain marginal.
- **Complexité** : six scrapers, un broker, un worker, un scheduler, des templates
  d'emails. Beaucoup de pièces mobiles à maintenir pour un outil personnel, et chaque
  évolution du produit touchait toute la chaîne.
- **Fiabilité** : les sites changent leur HTML, ajoutent des protections anti-bot, modifient
  leurs API. Un scraper cassé échoue *en silence*, et je ne pouvais pas faire confiance à
  un pipeline dont les entrées se dégradaient sans prévenir.
- **Valeur réelle** : la partie qui comptait vraiment, c'était le **suivi**. Savoir où
  j'en suis avec chaque offre et chaque personne, ne jamais rater une relance, préparer
  mes entretiens. Je trouvais les offres pertinentes moi-même, via mon réseau et des sites
  ciblés. L'automatisation optimisait la mauvaise étape.

**La décision : supprimer ce qui ne créait pas de valeur et investir sur ce qui en créait.**
J'ai archivé le moteur (rien n'est perdu, la branche v1 est là) et reconstruit l'application
autour d'un tracker manuel, déterministe, sans dépendance payante.

Ce que j'en retiens : un système plus sophistiqué n'est pas forcément meilleur.
Savoir **mesurer le rapport valeur / effort, puis simplifier**, y compris son propre code,
fait partie du travail d'ingénieur.

---

## v2 — le tracker manuel (branche `main`)

Zéro scraping, zéro IA, zéro appel réseau payant. L'utilisateur saisit ses offres et ses
contacts, l'outil se charge du suivi.

- **Timeline d'activité** : chaque action (candidature, relance, entretien, réponse…) est
  journalisée par offre et par contact. L'historique sert de source de vérité pour les
  statistiques.
- **Statistiques et funnel** : conversion candidature → entretien → offre, taux de réponse,
  performance par version de CV, activité hebdomadaire.
- **Agenda et export `.ics`** : deadlines, relances et entretiens dans une vue calendrier,
  exportable vers n'importe quel agenda (généré localement).
- **Suivi d'entretiens** : tours, format, issue, et lien vers la *Story Bank* (méthode STAR)
  pour préparer les questions comportementales.
- **Ajout rapide déterministe (0 token)** : on colle un bloc structuré et le bon formulaire
  est pré-rempli par un parseur local, testé unitairement. Aucune IA requise.
- **Bibliothèque de documents** : CV et lettres de motivation (PDF) étiquetés, réutilisables
  sur les offres et les contacts. Alimente les statistiques par version de CV.
- **Relances calculées à la volée** : pas de scheduler, une règle pure et testée
  (échéance manuelle prioritaire, sinon dernière action + délai configurable).
- **Self-host Docker** : une instance = un utilisateur, installation en une commande
  (`./scripts/setup.sh`, idempotent).
- **Garde-fou migrations** : schéma géré exclusivement par Alembic, jamais de
  `create_all`. Au démarrage, l'API vérifie, sans rien modifier, que la base est alignée
  sur la dernière révision et avertit sinon.

![Offres — vue liste avec filtres, priorité et statut (données anonymisées)](Installation%20et%20captures%20d'%C3%A9cran%20du%20projet/screenshots/offres.png)

![Fiche offre — détail, statut et notes (données anonymisées)](Installation%20et%20captures%20d'%C3%A9cran%20du%20projet/screenshots/offre-detail.png)

![Documents — bibliothèque de CV et lettres de motivation](Installation%20et%20captures%20d'%C3%A9cran%20du%20projet/screenshots/documents.png)

Installation, architecture détaillée et commandes de développement :
**[`Installation et captures d'écran du projet/INSTALL.md`](Installation%20et%20captures%20d'%C3%A9cran%20du%20projet/INSTALL.md)**.

---

## Stack

| Couche | Technologies |
|---|---|
| Backend | **FastAPI** (Python 3.12, async), SQLAlchemy 2 async, Pydantic |
| Base de données | **PostgreSQL 16**, migrations **Alembic** |
| Frontend | **Next.js 14**, **TypeScript**, **Tailwind CSS**, Recharts |
| Infra | **Docker** / Docker Compose (db, backend, frontend), Makefile |
| Tests | pytest + httpx (unitaires et intégration), tests du parseur côté front |
| v1 uniquement | Celery + Redis, API Claude, scrapers HTTP / HTML |

---

## Auteur

Conçu et développé par **Elie Blecher**.

Contact : elie.blecher@gmail.com

© 2026 Elie Blecher. Tous droits réservés. Voir [`LICENSE`](LICENSE).
