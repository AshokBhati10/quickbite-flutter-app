"""Shared fixtures: env defaults, truncation cleanup."""

from __future__ import annotations

import os

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://quickbite:quickbite@localhost:5432/quickbite",
)
os.environ.setdefault(
    "SYNC_DATABASE_URL",
    "postgresql+psycopg://quickbite:quickbite@localhost:5432/quickbite",
)
os.environ.setdefault("AMQP_URL", "amqp://quickbite:quickbite@localhost:5672/%2F")
os.environ.setdefault("JWT_SECRET", "test-only-secret-1234567890")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:3000")

import pytest  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.core.db import init_db, session_factory  # noqa: E402

TABLES_IN_DELETE_ORDER = [
    "notifications",
    "driver_assignments",
    "simulated_payments",
    "order_status_history",
    "order_items",
    "idempotency_keys",
    "outbox_events",
    "retry_jobs",
    "processed_events",
    "quarantine_records",
    "orders",
    "menu_items",
    "restaurants",
    "drivers",
    "users",
]


def _db_url() -> str:
    return os.environ["DATABASE_URL"]


@pytest.fixture()
async def db_session():
    init_db(_db_url())
    factory = session_factory()
    async with factory() as session:
        yield session


@pytest.fixture()
async def clean_tables():
    init_db(_db_url())
    factory = session_factory()
    async with factory() as session:
        for table in TABLES_IN_DELETE_ORDER:
            await session.execute(text(f"DELETE FROM {table}"))
        await session.commit()
    yield
    async with factory() as session:
        for table in TABLES_IN_DELETE_ORDER:
            await session.execute(text(f"DELETE FROM {table}"))
        await session.commit()
