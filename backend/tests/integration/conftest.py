"""Integration-only fixtures: truncate tables around each test and drop
the engine afterwards so pooled connections never cross event loops."""

from __future__ import annotations

import pytest
from sqlalchemy import text

from app.core import db as db_module
from tests.conftest import TABLES_IN_DELETE_ORDER, _db_url
from app.core.db import init_db, session_factory


async def _truncate_existing(session) -> None:
    existing = set(
        (
            await session.execute(
                text("SELECT tablename FROM pg_tables WHERE schemaname='public'")
            )
        ).scalars()
    )
    for table in TABLES_IN_DELETE_ORDER:
        if table in existing:
            await session.execute(text(f"DELETE FROM {table}"))
    await session.commit()


@pytest.fixture(autouse=True)
async def _clean_tables():
    db_module._engine = None
    db_module._session_factory = None
    db_module._db_url = None
    init_db(_db_url())
    factory = session_factory()
    async with factory() as session:
        await _truncate_existing(session)
    yield
    async with factory() as session:
        await _truncate_existing(session)
    engine = db_module._engine
    db_module._engine = None
    db_module._session_factory = None
    db_module._db_url = None
    if engine is not None:
        await engine.dispose()
