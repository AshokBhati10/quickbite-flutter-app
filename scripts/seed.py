"""Repeatable seed: customer + admin accounts, restaurants, menus, drivers.

Run:  .venv/bin/python scripts/seed.py
Safe to run twice: upserts by natural key, no duplicates.
"""

from __future__ import annotations

import asyncio
import os
import sys

for _candidate in (
    os.path.join(os.path.dirname(__file__), "..", "backend"),
    "/srv/app",
):
    if os.path.isdir(os.path.join(_candidate, "app")):
        sys.path.insert(0, _candidate)

from sqlalchemy import select  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.core.db import init_db, session_factory  # noqa: E402
from app.domain.auth import hash_password  # noqa: E402
from app.domain.models import Driver, MenuItem, Restaurant, User  # noqa: E402

PASSWORD = os.environ.get("SEED_PASSWORD", "Password123!")


async def upsert_user(session, *, id: str, email: str, role: str, name: str):
    user = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if user is None:
        session.add(
            User(
                id=id,
                email=email,
                password_hash=hash_password(PASSWORD),
                role=role,
                name=name,
            )
        )
        print(f"user {email} created")
    else:
        print(f"user {email} already present")


async def upsert_restaurant(session, *, id: str, name: str, description: str):
    rest = (
        await session.execute(select(Restaurant).where(Restaurant.name == name))
    ).scalar_one_or_none()
    if rest is None:
        session.add(Restaurant(id=id, name=name, description=description))
        print(f"restaurant {name} created")
        return id
    print(f"restaurant {name} already present")
    return rest.id


async def upsert_item(session, *, id: str, restaurant_id: str, name: str, price_minor: int, active: bool = True):
    item = (
        await session.execute(
            select(MenuItem).where(
                MenuItem.restaurant_id == restaurant_id, MenuItem.name == name
            )
        )
    ).scalar_one_or_none()
    if item is None:
        session.add(
            MenuItem(
                id=id,
                restaurant_id=restaurant_id,
                name=name,
                description=name,
                price_minor=price_minor,
                currency="INR",
                is_active=active,
            )
        )
        print(f"menu item {name} created")
    else:
        print(f"menu item {name} already present")


async def upsert_driver(session, *, id: str, name: str):
    driver = (
        await session.execute(select(Driver).where(Driver.name == name))
    ).scalar_one_or_none()
    if driver is None:
        session.add(Driver(id=id, name=name, is_active=True))
        print(f"driver {name} created")
    else:
        print(f"driver {name} already present")


async def main() -> None:
    settings = get_settings()
    init_db(settings.DATABASE_URL)
    factory = session_factory()
    async with factory() as session:
        async with session.begin():
            await upsert_user(
                session,
                id="user_customer",
                email="customer@quickbite.test",
                role="customer",
                name="Demo Customer",
            )
            await upsert_user(
                session,
                id="user_admin",
                email="admin@quickbite.test",
                role="admin",
                name="Demo Admin",
            )
            spice = await upsert_restaurant(
                session,
                id="rest_spice",
                name="Spice Route",
                description="Biryani and North Indian classics",
            )
            pasta = await upsert_restaurant(
                session,
                id="rest_pasta",
                name="Pasta Basta",
                description="Italian comfort food",
            )
            await upsert_item(session, id="item_biryani", restaurant_id=spice, name="Chicken Biryani", price_minor=1250)
            await upsert_item(session, id="item_lassi", restaurant_id=spice, name="Mango Lassi", price_minor=400)
            await upsert_item(
                session,
                id="item_kebab",
                restaurant_id=spice,
                name="Seekh Kebab (sold out)",
                price_minor=900,
                active=False,
            )
            await upsert_item(session, id="item_pasta", restaurant_id=pasta, name="Alfredo Pasta", price_minor=1100)
            await upsert_item(session, id="item_pizza", restaurant_id=pasta, name="Margherita Pizza", price_minor=1500)
            await upsert_driver(session, id="driver_1", name="Asha Kumar")
            await upsert_driver(session, id="driver_2", name="Ravi Singh")
    print("seed complete")


if __name__ == "__main__":
    asyncio.run(main())
