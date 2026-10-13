"""Database engine / session factory (async)."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

_engine = None
_session_factory = None
_db_url: str | None = None


def init_db(database_url: str) -> None:
    # Idempotent for a given URL: recreating the engine per call churns
    # pools whose connections are bound to the creating event loop.
    global _engine, _session_factory, _db_url
    if _engine is not None and _db_url == database_url:
        return
    _db_url = database_url
    # NOTE: pool_pre_ping is intentionally off. Its synchronous ping bridge
    # (await_only) raises MissingGreenlet with asyncpg in this stack, while
    # normal greenlet-wrapped queries work. Stale pooled connections surface
    # as ordinary query errors, which workers/API handle via retry/reconnect.
    _engine = create_async_engine(database_url, pool_pre_ping=False)
    _session_factory = async_sessionmaker(_engine, class_=AsyncSession)


def session_factory() -> async_sessionmaker[AsyncSession]:
    # Lazily initialise from settings so route handlers never depend on
    # import order (e.g. a cached app object after test teardown resets).
    if _session_factory is None:
        from app.core.config import get_settings

        init_db(get_settings().DATABASE_URL)
    assert _session_factory is not None, "database not initialised"
    return _session_factory


def engine():
    assert _engine is not None, "database not initialised"
    return _engine
