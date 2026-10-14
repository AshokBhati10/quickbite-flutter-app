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


@pytest.mark.asyncio
async def test_expanded_catalog_browses_and_checks_out(db_session) -> None:
    from tests.integration.test_phase1 import _migrate

    await db_session.close()
    await _migrate("up")
    await _seed(db_session)
    async with client() as c:
        token = await login(c, "customer@quickbite.test")
        headers = {"Authorization": f"Bearer {token}"}

        listing = await c.get(
            "/api/v1/restaurants",
            params={"page": "1", "page_size": "50"},
            headers=headers,
        )
        assert listing.status_code == 200, listing.text
        restaurants = listing.json()["items"]
        assert listing.json()["total"] == 25

        # Browsing: every restaurant exposes a substantial, described menu.
        for restaurant in restaurants:
            menu = await c.get(
                f"/api/v1/restaurants/{restaurant['id']}/menu",
                params={"page": "1", "page_size": "100"},
                headers=headers,
            )
            assert menu.status_code == 200, menu.text
            items = menu.json()["items"]
            assert len(items) >= 6, restaurant["id"]
            assert all(item["description"] for item in items)

        # Checkout from a non-default restaurant priced from the real menu.
        target = next(r for r in restaurants if r["id"] != "rest_spice")
        menu = (
            await c.get(
                f"/api/v1/restaurants/{target['id']}/menu",
                params={"page": "1", "page_size": "100"},
                headers=headers,
            )
        ).json()["items"]
        chosen = [item for item in menu if item["is_active"]][:2]
        assert len(chosen) == 2
        expected_total = sum(item["price_minor"] for item in chosen)
        created = await c.post(
            "/api/v1/orders",
            json={
                "restaurant_id": target["id"],
                "delivery_address": "12 Lake Road, Bengaluru",
                "items": [
                    {"menu_item_id": item["id"], "quantity": 1} for item in chosen
                ],
            },
            headers={**headers, "Idempotency-Key": str(uuid.uuid4())},
        )
        assert created.status_code == 202, created.text
        assert created.json()["total_amount_minor"] == expected_total

        # Tracking: the created order is immediately readable.
        tracked = await c.get(
            f"/api/v1/orders/{created.json()['order_id']}", headers=headers
        )
        assert tracked.status_code == 200
        assert tracked.json()["status"] == "PENDING"


@pytest.mark.asyncio
async def test_restaurants_paginate_five_per_page(db_session) -> None:
    from tests.integration.test_phase1 import _migrate

    await db_session.close()
    await _migrate("up")
    await _seed(db_session)
    async with client() as c:
        token = await login(c, "customer@quickbite.test")
        headers = {"Authorization": f"Bearer {token}"}

        seen: list[str] = []
        page = 1
        while True:
            resp = await c.get(
                "/api/v1/restaurants",
                params={"page": str(page), "page_size": "5"},
                headers=headers,
            )
            assert resp.status_code == 200, resp.text
            body = resp.json()
            assert body["page"] == page
            assert body["page_size"] == 5
            assert body["total"] == 25
            items = body["items"]
            if not items:
                break
            # A full page holds exactly five; a short page only at the end.
            assert len(items) == 5 or page == 5
            seen.extend(r["id"] for r in items)
            assert all(r["cuisine"] and r["image_url"] for r in items)
            page += 1

        # Five pages of five and every restaurant reachable once.
        assert page == 6
        assert len(seen) == 25
        assert len(set(seen)) == 25


@pytest.mark.asyncio
async def test_order_history_is_scoped_and_named(db_session) -> None:
    from tests.integration.test_phase1 import _migrate

    await db_session.close()
    await _migrate("up")
    await _seed(db_session)
    async with client() as c:
        token = await login(c, "customer@quickbite.test")
        headers = {"Authorization": f"Bearer {token}"}
        created = await c.post(
            "/api/v1/orders",
            json=checkout_body(),
            headers={**headers, "Idempotency-Key": str(uuid.uuid4())},
        )
        assert created.status_code == 202, created.text

        history = await c.get("/api/v1/orders", headers=headers)
        assert history.status_code == 200, history.text
        body = history.json()
        assert body["total"] == 1
        order = body["items"][0]
        # History carries everything the My Orders page renders.
        assert order["restaurant_name"] == "Spice Route"
        assert order["status"] == "PENDING"
        assert order["total_minor"] > 0
        assert order["created_at"]
        assert [i["quantity"] for i in order["items"]] == [2, 1]
        assert all(i["name"] for i in order["items"])

        # A different authenticated user sees none of it.
        await make_customer(
            db_session, user_id="user_other2", email="other2@quickbite.test"
        )
        other = await login(c, "other2@quickbite.test")
        empty = await c.get(
            "/api/v1/orders", headers={"Authorization": f"Bearer {other}"}
        )
        assert empty.json()["total"] == 0


@pytest.mark.asyncio
async def test_restaurant_search_filter_and_cuisines(db_session) -> None:
    from tests.integration.test_phase1 import _migrate

    await db_session.close()
    await _migrate("up")
    await _seed(db_session)
    async with client() as c:
        token = await login(c, "customer@quickbite.test")
        headers = {"Authorization": f"Bearer {token}"}

        cuisines = await c.get("/api/v1/restaurants/cuisines", headers=headers)
        assert cuisines.status_code == 200, cuisines.text
        values = cuisines.json()["items"]
        assert "Italian" in values
        assert values
        assert all(values)
        assert len(values) == len(set(values))

        by_name = await c.get(
            "/api/v1/restaurants",
            params={"q": "burger", "page_size": "50"},
            headers=headers,
        )
        names = [r["name"] for r in by_name.json()["items"]]
        assert "Burger Barn" in names

        # A cuisine query matches the cuisine field, not just the name.
        by_cuisine = await c.get(
            "/api/v1/restaurants",
            params={"q": "South Indian", "page_size": "50"},
            headers=headers,
        )
        hits = by_cuisine.json()["items"]
        assert hits
        assert all(
            "south indian" in (r["name"] + r["cuisine"]).lower() for r in hits
        )

        filtered = await c.get(
            "/api/v1/restaurants",
            params={"cuisine": "Italian", "page_size": "50"},
            headers=headers,
        )
        italian = filtered.json()["items"]
        assert italian
        assert all(r["cuisine"] == "Italian" for r in italian)


@pytest.mark.asyncio
async def test_register_creates_isolated_customer(db_session) -> None:
    from tests.integration.test_phase1 import _migrate

    await db_session.close()
    await _migrate("up")
    await _seed(db_session)
    async with client() as c:
        weak = await c.post(
            "/api/v1/auth/register",
            json={"email": "new@quickbite.test", "password": "short", "name": "New"},
        )
        assert weak.status_code == 422

        bad_email = await c.post(
            "/api/v1/auth/register",
            json={
                "email": "not-an-email",
                "password": "Password123!",
                "name": "New",
            },
        )
        assert bad_email.status_code == 422

        created = await c.post(
            "/api/v1/auth/register",
            json={
                "email": "New@QuickBite.test",
                "password": "Password123!",
                "name": "New User",
            },
        )
        assert created.status_code == 201, created.text
        payload = created.json()
        assert payload["user"]["name"] == "New User"
        assert payload["user"]["email"] == "new@quickbite.test"
        assert payload["user"]["role"] == "customer"

        # The returned token authenticates the brand-new account.
        headers = {"Authorization": f"Bearer {payload['access_token']}"}
        me = await c.get("/api/v1/me", headers=headers)
        assert me.status_code == 200
        assert me.json()["email"] == "new@quickbite.test"
        assert (await c.get("/api/v1/orders", headers=headers)).json()["total"] == 0

        # Logging in works with the normalized email, and duplicates are rejected.
        assert await login(c, "new@quickbite.test")
        dup = await c.post(
            "/api/v1/auth/register",
            json={
                "email": "new@quickbite.test",
                "password": "Password123!",
                "name": "Dup",
            },
        )
        assert dup.status_code == 409
