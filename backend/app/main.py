from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import get_settings
from app.api.routes.main import router

settings = get_settings()

app = FastAPI(
    title="Stage CRM — Secrétaire de recherche de stage",
    description="CRM intelligent pour la recherche de stages en finance, conseil et stratégie",
    version="0.1.0",
)

# CORS pour le frontend Next.js
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url, "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "Stage CRM API"}
