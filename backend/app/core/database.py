import logging
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

# Le pooling configurable n'a de sens que pour Postgres ; SQLite (tests / dev léger)
# utilise NullPool et rejette ces arguments.
_engine_kwargs: dict = {"echo": settings.app_env == "development"}
if not settings.database_url.startswith("sqlite"):
    _engine_kwargs.update(pool_size=20, max_overflow=10)

engine = create_async_engine(settings.database_url, **_engine_kwargs)

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


def _alembic_config():
    """Config Alembic résolue en chemins absolus (robuste au cwd du process)."""
    from alembic.config import Config

    backend_root = Path(__file__).resolve().parents[2]  # …/backend
    cfg = Config(str(backend_root / "alembic.ini"))
    cfg.set_main_option("script_location", str(backend_root / "alembic"))
    return cfg


def _current_db_revision(sync_conn) -> str | None:
    """Révision Alembic actuellement enregistrée dans la base (lecture seule)."""
    from alembic.runtime.migration import MigrationContext

    return MigrationContext.configure(sync_conn).get_current_revision()


async def check_migration_state(check_engine=None) -> None:
    """Vérifie — SANS muter — que le schéma est aligné sur head ; WARNING sinon.

    Remplace l'ancien auto-upgrade au démarrage. N'appelle JAMAIS
    ``command.upgrade``, ``create_all`` ni aucun DDL : au pire un warning, le
    démarrage n'échoue jamais sur ce point. Les migrations sont désormais
    explicites (``alembic upgrade head`` lancé manuellement après relecture).
    """
    from alembic.script import ScriptDirectory

    eng = check_engine or engine
    try:
        head_rev = ScriptDirectory.from_config(_alembic_config()).get_current_head()
        async with eng.connect() as conn:
            current_rev = await conn.run_sync(_current_db_revision)
    except Exception as exc:  # jamais bloquant au démarrage
        logger.warning("Vérification des migrations impossible (ignorée) : %s", exc)
        return

    if current_rev == head_rev:
        logger.info("Schéma DB à jour (alembic head=%s).", head_rev)
    else:
        logger.warning(
            "⚠️  MIGRATIONS EN ATTENTE — la base est à %s, head=%s. "
            "Lancer `alembic upgrade head` (après relecture) pour aligner le schéma. "
            "Le démarrage n'applique volontairement aucune migration.",
            current_rev,
            head_rev,
        )
