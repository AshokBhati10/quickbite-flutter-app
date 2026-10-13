"""Phase 1 integration (real Postgres): migrate, seed, auth, readiness."""

from __future__ import annotations

import os

import pytest
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from app.core.db import init_db
from app.domain.auth import issue_token
from app.domain.models import MenuItem, Restaurant, User

BACKEND_DIR = os.path.join(os.path.dirname(__file__), "..", "..")


def _alembic() -> Config:
    cfg = Config(os.path.join(BACKEND_DIR, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(BACKEND_DIR, "migrations"))
    return cfg


async def _migrate(direction: str) -> None:
    cfg = _alembic()
    if direction == "up":
        command.upgrade(cfg, "head")
    else:
        command.downgrade(cfg, "base")


def _client():
    from app.api.app import app

    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _seed_twice() -> None:
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "seed", os.path.join(BACKEND_DIR, "..", "scripts", "seed.py")
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    await module.main()
    await module.main()


@pytest.mark.asyncio
async def test_migrate_up_down_up(db_session) -> None:
    # Release the fixture's idle transaction: DDL takes ACCESS EXCLUSIVE
    # locks that would wait on it forever.
    await db_session.close()
    await _migrate("up")
    count = (
        await db_session.execute(select(func.count()).select_from(User))
    ).scalar()
    assert count == 0
    # The count above opened an implicit transaction: release it before DDL.
    await db_session.close()
    await _migrate("down")
    await _migrate("up")


@pytest.mark.asyncio
async def test_seed_twice_no_duplicates(db_session) -> None:
    await db_session.close()
    await _migrate("up")
    await _seed_twice()
    users = (await db_session.execute(select(func.count()).select_from(User))).scalar()
    rests = (
        await db_session.execute(select(func.count()).select_from(Restaurant))
    ).scalar()
    items = (
        await db_session.execute(select(func.count()).select_from(MenuItem))
    ).scalar()
    assert users == 2
    assert rests == 2
    assert items == 5


@pytest.mark.asyncio
async def test_login_me_and_failures(db_session) -> None:
    await db_session.close()
    await _migrate("up")
    await _seed_twice()
    async with _client() as client:
        ok = await client.post(
            "/api/v1/auth/login",
            json={"email": "customer@quickbite.test", "password": "Password123!"},
        )
        assert ok.status_code == 200, ok.text
        token = ok.json()["access_token"]

        bad = await client.post(
            "/api/v1/auth/login",
            json={"email": "customer@quickbite.test", "password": "nope"},
        )
        assert bad.status_code == 401

        me = await client.get(
            "/api/v1/me", headers={"Authorization": f"Bearer {token}"}
        )
        assert me.status_code == 200
        assert me.json()["email"] == "customer@quickbite.test"

        anon = await client.get("/api/v1/me")
        assert anon.status_code == 401

        expired, _ = issue_token(
            user_id="user_customer",
            role="customer",
            secret=os.environ["JWT_SECRET"],
            expire_minutes=-1,
        )
        stale = await client.get(
            "/api/v1/me", headers={"Authorization": f"Bearer {expired}"}
        )
        assert stale.status_code == 401


@pytest.mark.asyncio
async def test_readiness_503_when_db_down(db_session) -> None:
    await db_session.close()
    await _migrate("up")
    from app.api.app import app

    async with _client() as client:
        ready = await client.get("/health/ready")
        assert ready.status_code in (200, 503)
        assert (await client.get("/health/live")).status_code == 200
    # Point the factory at a dead port: readiness must report 503.
    init_db("postgresql+asyncpg://quickbite:quickbite@localhost:59999/quickbite")
    async with _client() as client:
        down = await client.get("/health/ready")
        assert down.status_code == 503
    init_db(os.environ["DATABASE_URL"])
