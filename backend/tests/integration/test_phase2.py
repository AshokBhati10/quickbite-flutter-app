"""Phase 2 integration (real Postgres): validation, idempotency, access."""

from __future__ import annotations

import asyncio
import uuid

import pytest
from sqlalchemy import func, select

from app.domain.models import IdempotencyKey, Order, OutboxEvent
from tests.integration.helpers import checkout_body, client, login, make_customer


async def _seed(db_session) -> None:
    import importlib.util
    import os

    path = os.path.join(
        os.path.dirname(__file__), "..", "..", "..", "scripts", "seed.py"
    )
    spec = importlib.util.spec_from_file_location("seed", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    await module.main()


async def _counts(db_session) -> tuple[int, int]:
    orders = (
        await db_session.execute(select(func.count()).select_from(Order))
    ).scalar()
    outbox = (
        await db_session.execute(select(func.count()).select_from(OutboxEvent))
    ).scalar()
    return orders or 0, outbox or 0


@pytest.mark.asyncio
async def test_invalid_checkouts_leave_no_rows(db_session) -> None:
    from tests.integration.test_phase1 import _migrate

    await db_session.close()
    await _migrate("up")
    await _seed(db_session)
    async with client() as c:
        token = await login(c, "customer@quickbite.test")
        headers = {"Authorization": f"Bearer {token}"}

        before = await _counts(db_session)
        cases = [
            checkout_body(items=[{"menu_item_id": "nope", "quantity": 1}]),
            checkout_body(
                items=[
                    {"menu_item_id": "item_biryani", "quantity": 1},
                    {"menu_item_id": "item_pasta", "quantity": 1},
                ]
            ),  # mixed restaurants
            checkout_body(items=[{"menu_item_id": "item_kebab", "quantity": 1}]),
            checkout_body(items=[{"menu_item_id": "item_biryani", "quantity": 0}]),
            checkout_body(delivery_address="short"),
            {
                "restaurant_id": "rest_spice",
                "delivery_address": "12 Lake Road, Bengaluru",
                "items": [
                    {"menu_item_id": f"item_{i}", "quantity": 1} for i in range(21)
                ],
            },
        ]
        for body in cases:
            resp = await c.post(
                "/api/v1/orders",
                json=body,
                headers={**headers, "Idempotency-Key": str(uuid.uuid4())},
            )
            assert resp.status_code == 422, (body, resp.text)
        no_key = await c.post("/api/v1/orders", json=checkout_body(), headers=headers)
        assert no_key.status_code == 422
        assert await _counts(db_session) == before


@pytest.mark.asyncio
async def test_server_priced_total(db_session) -> None:
    from tests.integration.test_phase1 import _migrate

    await db_session.close()
    await _migrate("up")
    await _seed(db_session)
    async with client() as c:
        token = await login(c, "customer@quickbite.test")
        resp = await c.post(
            "/api/v1/orders",
            json=checkout_body(),
            headers={
                "Authorization": f"Bearer {token}",
                "Idempotency-Key": str(uuid.uuid4()),
            },
        )
        assert resp.status_code == 202, resp.text
        # 1250*2 + 400, computed server-side from the seeded menu.
        assert resp.json()["total_amount_minor"] == 2900
        assert "Location" in resp.headers


@pytest.mark.asyncio
async def test_idempotent_replay_and_conflict(db_session) -> None:
    from tests.integration.test_phase1 import _migrate

    await db_session.close()
    await _migrate("up")
    await _seed(db_session)
    async with client() as c:
        token = await login(c, "customer@quickbite.test")
        headers = {"Authorization": f"Bearer {token}"}
        key = str(uuid.uuid4())
        first = await c.post(
            "/api/v1/orders",
            json=checkout_body(),
            headers={**headers, "Idempotency-Key": key},
        )
        assert first.status_code == 202
        before = await _counts(db_session)
        replay = await c.post(
            "/api/v1/orders",
            json=checkout_body(),
            headers={**headers, "Idempotency-Key": key},
        )
        assert replay.status_code == 202
        assert replay.json()["order_id"] == first.json()["order_id"]
        assert replay.headers["Location"] == first.headers["Location"]
        assert await _counts(db_session) == before

        conflict = await c.post(
            "/api/v1/orders",
            json=checkout_body(delivery_address="99 Other Road, Bengaluru"),
            headers={**headers, "Idempotency-Key": key},
        )
        assert conflict.status_code == 409


@pytest.mark.asyncio
async def test_concurrent_identical_posts_create_one_order(db_session) -> None:
    from tests.integration.test_phase1 import _migrate

    await db_session.close()
    await _migrate("up")
    await _seed(db_session)
    async with client() as c:
        token = await login(c, "customer@quickbite.test")
        headers = {"Authorization": f"Bearer {token}"}
        key = str(uuid.uuid4())

        async def _post(_: int):
            return await c.post(
                "/api/v1/orders",
                json=checkout_body(),
                headers={**headers, "Idempotency-Key": key},
            )

        responses = await asyncio.gather(*[_post(i) for i in range(20)])
        assert all(r.status_code == 202 for r in responses), [
            (r.status_code, r.text) for r in responses
        ]
        ids = {r.json()["order_id"] for r in responses}
        assert len(ids) == 1
        order_id = ids.pop()
        n_orders = (
            await db_session.execute(
                select(func.count())
                .select_from(Order)
                .where(Order.id == order_id)
            )
        ).scalar()
        n_outbox = (
            await db_session.execute(
                select(func.count())
                .select_from(OutboxEvent)
                .where(OutboxEvent.event_type == "order.created")
            )
        ).scalar()
        assert n_orders == 1
        assert n_outbox == 1


@pytest.mark.asyncio
async def test_access_control(db_session) -> None:
    from tests.integration.test_phase1 import _migrate

    await db_session.close()
    await _migrate("up")
    await _seed(db_session)
    await make_customer(
        db_session, user_id="user_other", email="other@quickbite.test"
    )
    async with client() as c:
        customer = await login(c, "customer@quickbite.test")
        other = await login(c, "other@quickbite.test")
        admin = await login(c, "admin@quickbite.test")

        created = await c.post(
            "/api/v1/orders",
            json=checkout_body(),
            headers={
                "Authorization": f"Bearer {customer}",
                "Idempotency-Key": str(uuid.uuid4()),
            },
        )
        order_id = created.json()["order_id"]

        stranger = await c.get(
            f"/api/v1/orders/{order_id}",
            headers={"Authorization": f"Bearer {other}"},
        )
        assert stranger.status_code == 404

        as_admin = await c.get(
            f"/api/v1/orders/{order_id}",
            headers={"Authorization": f"Bearer {admin}"},
        )
        assert as_admin.status_code == 200

        forbidden = await c.get(
            "/api/v1/admin/orders", headers={"Authorization": f"Bearer {customer}"}
        )
        assert forbidden.status_code == 403

        anon = await c.get("/api/v1/orders")
        assert anon.status_code == 401

        too_big = await c.get(
            "/api/v1/restaurants?page_size=101",
            headers={"Authorization": f"Bearer {customer}"},
        )
        assert too_big.status_code == 422

        mine = await c.get(
            "/api/v1/orders", headers={"Authorization": f"Bearer {customer}"}
        )
        assert mine.json()["total"] == 1
        empty = await c.get(
            "/api/v1/orders", headers={"Authorization": f"Bearer {other}"}
        )
        assert empty.json()["total"] == 0
