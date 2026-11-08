"""Fixtures de test : app FastAPI branchée sur une base SQLite isolée.

L'engine in-memory est partagé (StaticPool) pour qu'une même base soit visible
à la fois par le client HTTP (`client`) et par un accès DB direct (`db_session`),
ce dernier servant à vérifier les contraintes de schéma (CHECK, CASCADE, SET NULL).
"""

from __future__ import annotations

from pathlib import Path

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.main import app
import app.api.routes.main as routes


@pytest_asyncio.fixture
async def _session_maker():
    # Une seule connexion partagée (StaticPool) → l'in-memory survit entre
    # requêtes HTTP et accès DB direct au sein d'un même test.
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )

    # SQLite n'applique les FK (ON DELETE CASCADE / SET NULL) que si le PRAGMA
    # est activé.
    @event.listens_for(engine.sync_engine, "connect")
    def _enable_fk(dbapi_conn, _record):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    await engine.dispose()


@pytest_asyncio.fixture
async def client(_session_maker, tmp_path: Path):
    async def override_get_db():
        async with _session_maker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db

    # Uploads vers un dossier temporaire.
    old_upload_dir = routes.settings.upload_dir
    routes.settings.upload_dir = str(tmp_path / "uploads")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test/api/v1") as ac:
        yield ac

    app.dependency_overrides.clear()
    routes.settings.upload_dir = old_upload_dir


@pytest_asyncio.fixture
async def db_session(_session_maker):
    """Session DB directe (même base que `client`) pour tester les contraintes."""
    async with _session_maker() as session:
        yield session
