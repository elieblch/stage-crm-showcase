# ══════════════════════════════════════════════════════════
# Stage CRM — raccourcis
# ══════════════════════════════════════════════════════════
.PHONY: help setup update up down logs migrate migration-status test shell reset

help:                ## Affiche cette aide
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

setup:               ## Premier lancement : .env, build, migrations, démarrage
	@./scripts/setup.sh

update:              ## Mise à jour après `git pull` (identique à setup, idempotent)
	@./scripts/setup.sh

up:                  ## Démarre la stack (sans migrer)
	docker compose up -d

down:                ## Arrête la stack (les données sont CONSERVÉES)
	docker compose down

logs:                ## Suit les logs du backend
	docker compose logs -f backend

migrate:             ## Applique les migrations (conteneur one-off)
	docker compose run --rm --no-deps backend alembic upgrade head

migration-status:    ## Révision courante vs head
	docker compose run --rm --no-deps backend alembic current
	docker compose run --rm --no-deps backend alembic heads

test:                ## Tests backend
	docker compose exec backend pytest -q

shell:               ## Shell dans le conteneur backend
	docker compose exec backend bash

reset:               ## ⚠️ DESTRUCTIF : supprime la base et les PDF uploadés
	@printf '\033[0;31mCela EFFACERA définitivement toutes tes offres, contacts et PDF.\033[0m\n'
	@printf 'Tape "reset" pour confirmer : '; read -r ans; [ "$$ans" = "reset" ] || { echo "Annulé."; exit 1; }
	docker compose down -v
	@echo "Base et uploads supprimés. Relance \`make setup\` pour repartir de zéro."
