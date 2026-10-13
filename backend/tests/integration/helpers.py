"""Shared integration helpers: auth, checkout payloads."""

from __future__ import annotations

from httpx import ASGITransport, AsyncClient

from app.domain.auth import hash_password
from app.domain.models import User


def client():
    from app.api.app import app

    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def login(client: AsyncClient, email: str, password: str = "Password123!") -> str:
    resp = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


async def make_customer(db_session, *, user_id: str, email: str):
    db_session.add(
        User(
            id=user_id,
            email=email,
            password_hash=hash_password("Password123!"),
            role="customer",
            name=email,
        )
    )
    await db_session.commit()


def checkout_body(**overrides) -> dict:
    body = {
        "restaurant_id": "rest_spice",
        "delivery_address": "12 Lake Road, Bengaluru",
        "items": [
            {"menu_item_id": "item_biryani", "quantity": 2},
            {"menu_item_id": "item_lassi", "quantity": 1},
        ],
    }
    body.update(overrides)
    return body
