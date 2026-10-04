"""Async database engine, session factory and migration runner."""

import asyncio
from collections.abc import AsyncIterator
from pathlib import Path

import structlog
from alembic import command
from alembic.config import Config
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from codeguide.config import get_settings

log = structlog.get_logger()

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    global _engine, _session_factory
    if _engine is None:
        url = get_settings().database_url
        if url.startswith("sqlite"):
            # e.g. sqlite+aiosqlite:///./data/app.db — make sure ./data exists
            db_path = url.rsplit("///", 1)[-1]
            if db_path and db_path != ":memory:":
                Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        _engine = create_async_engine(url, echo=False)
        _session_factory = async_sessionmaker(_engine, expire_on_commit=False)
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    get_engine()
    if _session_factory is None:  # pragma: no cover - set together with the engine
        raise RuntimeError("session factory not initialised")
    return _session_factory


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency yielding one session per request."""
    async with get_session_factory()() as session:
        yield session


def _find_alembic_ini() -> Path:
    candidates = [
        Path.cwd() / "alembic.ini",
        Path(__file__).resolve().parents[2] / "alembic.ini",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"alembic.ini not found in {[str(c) for c in candidates]}")


async def run_migrations() -> None:
    """Apply pending Alembic migrations (runs at startup)."""
    ini = _find_alembic_ini()

    def _upgrade() -> None:
        cfg = Config(str(ini))
        cfg.set_main_option("script_location", str(ini.parent / "alembic"))
        command.upgrade(cfg, "head")

    get_engine()  # ensure the SQLite data directory exists before Alembic connects
    await asyncio.to_thread(_upgrade)
    log.info("migrations_applied")


async def dispose_engine() -> None:
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None
