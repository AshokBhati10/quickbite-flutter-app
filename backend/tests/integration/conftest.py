"""Integration-only fixtures: isolated test database + broker, then
truncate tables around each test and drop the engine afterwards so pooled
connections never cross event loops.

Isolation is mandatory: the running application and its workers share the
default ``quickbite`` database and the ``/`` RabbitMQ vhost. These tests
migrate/downgrade schemas, truncate every table and purge queues, so running
them against the shared resources would destroy live data and steal messages
from the live consumers. Instead each integration run uses a dedicated
``quickbite_test`` database and a dedicated ``quickbite_test`` vhost, both
created idempotently on the already-running Postgres/RabbitMQ containers.
"""

from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.request
from urllib.parse import quote

import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url

from app.core import db as db_module
from tests.conftest import TABLES_IN_DELETE_ORDER, _db_url
from app.core.db import init_db, session_factory

# --- Isolated test endpoints ------------------------------------------------
# Overridable, but default to dedicated resources so a developer running the
# suite locally can never accidentally target the live database or broker.
TEST_DB_NAME = os.environ.get("QUICKBITE_TEST_DB", "quickbite_test")
TEST_VHOST = os.environ.get("QUICKBITE_TEST_VHOST", "quickbite_test")
PG_HOST = os.environ.get("QUICKBITE_TEST_PG_HOST", "localhost")
PG_PORT = os.environ.get("QUICKBITE_TEST_PG_PORT", "5432")
PG_USER = os.environ.get("QUICKBITE_TEST_PG_USER", "quickbite")
PG_PASSWORD = os.environ.get("QUICKBITE_TEST_PG_PASSWORD", "quickbite")
AMQP_HOST = os.environ.get("QUICKBITE_TEST_AMQP_HOST", "localhost")
AMQP_PORT = os.environ.get("QUICKBITE_TEST_AMQP_PORT", "5672")
MGMT_URL = os.environ.get(
    "QUICKBITE_TEST_RABBITMQ_MGMT_URL", "http://localhost:15672"
)

_TEST_DATABASE_URL = (
    f"postgresql+asyncpg://{PG_USER}:{PG_PASSWORD}@{PG_HOST}:{PG_PORT}/{TEST_DB_NAME}"
)
_TEST_SYNC_DATABASE_URL = (
    f"postgresql+psycopg://{PG_USER}:{PG_PASSWORD}@{PG_HOST}:{PG_PORT}/{TEST_DB_NAME}"
)
_TEST_AMQP_URL = (
    f"amqp://{PG_USER}:{PG_PASSWORD}@{AMQP_HOST}:{AMQP_PORT}/{TEST_VHOST}"
)

# Point the application (Settings, Alembic, workers, API) at the isolated
# resources *before* any app module reads the environment. Real environment
# variables outrank values from .env, so this wins over the live defaults that
# tests/conftest.py installs with setdefault().
os.environ["DATABASE_URL"] = _TEST_DATABASE_URL
os.environ["SYNC_DATABASE_URL"] = _TEST_SYNC_DATABASE_URL
os.environ["AMQP_URL"] = _TEST_AMQP_URL
os.environ["TEST_DATABASE_URL"] = (
    f"postgresql://{PG_USER}:{PG_PASSWORD}@{PG_HOST}:{PG_PORT}/{TEST_DB_NAME}"
)
os.environ["TEST_AMQP_URL"] = _TEST_AMQP_URL


def _ensure_test_database() -> None:
    """Create the throwaway test database on the running Postgres if absent."""
    import psycopg

    admin_url = make_url(_TEST_SYNC_DATABASE_URL).set(
        drivername="postgresql", database="postgres"
    )
    with psycopg.connect(
        admin_url.render_as_string(hide_password=False), autocommit=True
    ) as conn:
        exists = conn.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s", (TEST_DB_NAME,)
        ).fetchone()
        if exists is None:
            conn.execute(f'CREATE DATABASE "{TEST_DB_NAME}"')


def _ensure_test_vhost() -> None:
    """Create the dedicated test vhost + permissions via the management API.

    Additive and idempotent: the running RabbitMQ node is untouched except for
    gaining an extra vhost that only integration tests use.
    """
    auth = base64.b64encode(f"{PG_USER}:{PG_PASSWORD}".encode()).decode()
    headers = {
        "Authorization": f"Basic {auth}",
        "Content-Type": "application/json",
    }
    vhost = quote(TEST_VHOST, safe="")

    def _put(path: str, body: bytes) -> None:
        request = urllib.request.Request(
            f"{MGMT_URL}{path}", data=body, headers=headers, method="PUT"
        )
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                response.read()
        except urllib.error.HTTPError as exc:  # pragma: no cover - env failure
            if exc.code not in (201, 204):
                raise RuntimeError(
                    f"RabbitMQ management API PUT {path} failed: "
                    f"{exc.code} {exc.read()!r}"
                ) from exc

    _put(f"/api/vhosts/{vhost}", b"{}")
    _put(
        f"/api/permissions/{vhost}/{quote(PG_USER, safe='')}",
        json.dumps({"configure": ".*", "write": ".*", "read": ".*"}).encode(),
    )


@pytest.fixture(scope="session", autouse=True)
def _bootstrap_storage() -> None:
    """Ensure isolation exists before any integration test connects."""
    _ensure_test_database()
    _ensure_test_vhost()


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


@pytest.fixture(autouse=True)
async def _reset_test_queues():
    """Start every integration test from an empty isolated broker topology.

    Only the dedicated test vhost is touched, so no live queue is ever purged
    and no live consumer can compete for these messages.
    """
    import aio_pika

    from app.messaging.topology import (
        DELIVERY_QUEUE,
        NOTIFICATION_QUEUE,
        PAYMENT_QUEUE,
        RESTAURANT_QUEUE,
        declare_topology,
    )

    await declare_topology(_TEST_AMQP_URL)
    connection = await aio_pika.connect_robust(_TEST_AMQP_URL)
    try:
        channel = await connection.channel()
        for queue_name in (
            PAYMENT_QUEUE,
            RESTAURANT_QUEUE,
            DELIVERY_QUEUE,
            NOTIFICATION_QUEUE,
        ):
            queue = await channel.declare_queue(queue_name, passive=True)
            await queue.purge()
    finally:
        await connection.close()
