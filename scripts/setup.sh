#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════
# Stage CRM — setup d'une instance auto-hébergée
#
# Idempotent : peut être relancé autant de fois que voulu, il ne
# détruit jamais de données. Sert aussi bien au PREMIER lancement
# qu'à une MISE À JOUR après `git pull`.
#
# Les migrations sont appliquées par un conteneur ONE-OFF
# (`docker compose run --rm backend alembic upgrade head`), jamais
# par le process backend long-running : le démarrage de l'API se
# contente de vérifier l'état du schéma et n'applique aucun DDL.
# ══════════════════════════════════════════════════════════

set -euo pipefail

cd "$(dirname "$0")/.."   # → racine du projet

info()  { printf '\033[0;36m%s\033[0m\n' "$*"; }
ok()    { printf '\033[0;32m✅ %s\033[0m\n' "$*"; }
warn()  { printf '\033[0;33m⚠️  %s\033[0m\n' "$*"; }
fail()  { printf '\033[0;31m❌ %s\033[0m\n' "$*" >&2; exit 1; }

# ── 0. Prérequis ──────────────────────────────────────────
command -v docker >/dev/null 2>&1 || fail "Docker n'est pas installé — https://docs.docker.com/get-docker/"
docker compose version >/dev/null 2>&1 || fail "Docker Compose v2 est requis (\`docker compose\`, pas \`docker-compose\`)."
docker info >/dev/null 2>&1 || fail "Le démon Docker ne tourne pas. Démarre Docker Desktop puis relance ce script."

info "🚀 Stage CRM — setup"
info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ── 1. Configuration locale ───────────────────────────────
if [ ! -f .env ]; then
    cp .env.example .env
    ok ".env créé depuis .env.example (valeurs par défaut utilisables telles quelles)"
else
    ok ".env déjà présent — laissé intact"
fi

# Ports effectifs, pour l'affichage final (respecte un .env personnalisé).
# shellcheck disable=SC1091
set -a; . ./.env; set +a
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"

# ── 2. Build des images ───────────────────────────────────
info ""
info "🔨 Build des images (backend, frontend)…"
docker compose build
ok "Images à jour"

# ── 3. Base de données ────────────────────────────────────
info ""
info "🐘 Démarrage de PostgreSQL…"
docker compose up -d db

info "   attente du healthcheck…"
for i in $(seq 1 60); do
    status=$(docker compose ps db --format '{{.Health}}' 2>/dev/null || echo "")
    [ "$status" = "healthy" ] && break
    [ "$i" = "60" ] && fail "PostgreSQL n'est pas devenu healthy en 60 s. Voir \`docker compose logs db\`."
    sleep 1
done
ok "PostgreSQL prêt"

# ── 4. Migrations (conteneur one-off, JAMAIS au démarrage de l'API) ──
info ""
info "🗄️  Application des migrations Alembic…"
docker compose run --rm --no-deps backend alembic upgrade head
ok "Schéma à head"

# ── 5. Lancement de la stack ──────────────────────────────
info ""
info "🐳 Démarrage de la stack complète…"
docker compose up -d
ok "Conteneurs démarrés"

info ""
info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
ok "Stage CRM est prêt."
info ""
info "  🌐 Application  → http://localhost:${FRONTEND_PORT}"
info "  🔌 API          → http://localhost:${BACKEND_PORT}"
info "  📚 API Docs     → http://localhost:${BACKEND_PORT}/docs"
info ""
info "Pas de compte à créer : une instance = un utilisateur."
info "Tes données vivent dans les volumes Docker locaux (pgdata, user_uploads)."
info ""
info "Commandes utiles :"
info "  docker compose logs -f backend                        # logs API"
info "  docker compose exec backend pytest -q                 # tests"
info "  docker compose down                                   # arrêter (données conservées)"
info "  ./scripts/setup.sh                                    # relancer / mettre à jour"
