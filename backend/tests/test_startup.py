"""Startup : vérification NON mutante des migrations (plus d'auto-upgrade).

Garde-fous :
- le lifespan n'applique jamais de migration (`command.upgrade`) ni `create_all`
  sur la base applicative ;
- quand la base n'est pas à head, un WARNING est émis SANS altérer le schéma ;
- le démarrage ne échoue jamais sur ce point (warning, pas crash).
"""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.database import _alembic_config, check_migration_state
from app.main import app, lifespan

pytestmark = pytest.mark.asyncio


def _head_revision() -> str:
    from alembic.script import ScriptDirectory

    return ScriptDirectory.from_config(_alembic_config()).get_current_head()


async def _sqlite_engine_at(revision: str | None):
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.exec_driver_sql(
            "CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"
        )
        if revision is not None:
            await conn.exec_driver_sql(
                f"INSERT INTO alembic_version (version_num) VALUES ('{revision}')"
            )
    return engine


# ─── Le lifespan ne mute jamais le schéma ─────────────────
async def test_lifespan_checks_and_never_applies_migrations():
    import alembic.command as alembic_command

    with patch("app.main.check_migration_state", new_callable=AsyncMock) as mock_check, \
         patch.object(alembic_command, "upgrade") as mock_upgrade, \
         patch("app.core.database.Base.metadata.create_all") as mock_create_all:
        async with lifespan(app):
            pass

    mock_check.assert_awaited_once()
    mock_upgrade.assert_not_called()
    mock_create_all.assert_not_called()


# ─── DB en retard → warning, schéma inchangé ──────────────
async def test_check_warns_when_behind_and_does_not_mutate(caplog):
    engine = await _sqlite_engine_at("ec7f62a56ae8")  # baseline, pas head
    async with engine.connect() as conn:
        before = (
            await conn.exec_driver_sql("SELECT version_num FROM alembic_version")
        ).scalar()

    with caplog.at_level(logging.WARNING, logger="app.core.database"):
        await check_migration_state(engine)

    assert any("MIGRATIONS EN ATTENTE" in r.getMessage() for r in caplog.records)

    # Aucune mutation : révision et table inchangées.
    async with engine.connect() as conn:
        after = (
            await conn.exec_driver_sql("SELECT version_num FROM alembic_version")
        ).scalar()
    assert before == after == "ec7f62a56ae8"
    await engine.dispose()


# ─── DB à head → pas de warning ───────────────────────────
async def test_check_silent_when_at_head(caplog):
    engine = await _sqlite_engine_at(_head_revision())
    with caplog.at_level(logging.WARNING, logger="app.core.database"):
        await check_migration_state(engine)
    assert not any("MIGRATIONS EN ATTENTE" in r.getMessage() for r in caplog.records)
    await engine.dispose()


# ─── Le démarrage ne échoue jamais sur la vérification ────
async def test_lifespan_tolerates_check_failure():
    # Même si la lecture de révision lève, le démarrage doit se poursuivre.
    with patch(
        "app.core.database._current_db_revision", side_effect=RuntimeError("boom")
    ):
        async with lifespan(app):
            pass  # ne doit pas lever


async def test_health_ok(client):
    r = await client.get("http://test/health")
    assert r.status_code == 200
