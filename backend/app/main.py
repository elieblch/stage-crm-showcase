from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.main import router
from app.api.routes.agenda import router as agenda_router
from app.api.routes.stats import router as stats_router
from app.core.config import get_settings
from app.core.database import check_migration_state

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Vérifie (sans muter) que le schéma est aligné sur head et AVERTIT sinon.
    # Le démarrage n'applique volontairement AUCUNE migration : plus d'auto-upgrade,
    # jamais de create_all. Les migrations sont explicites (`alembic upgrade head`
    # lancé manuellement après relecture).
    await check_migration_state()
    yield


app = FastAPI(
    title="Stage CRM — Tracker manuel de recherche de stage",
    description="Tracker 100 % manuel : offres, contacts, relances, story bank. Sans IA, sans scraping.",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS pour le frontend Next.js
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url, "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")
app.include_router(stats_router, prefix="/api/v1")
app.include_router(agenda_router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "Stage CRM API"}
