"""GET /restaurants, GET /restaurants/{id}/menu with pagination."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.api.schemas import MenuItemOut, Page, RestaurantOut
from app.domain.models import MenuItem, Restaurant, User

router = APIRouter()


def _page_params(
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)
) -> tuple[int, int]:
    return page, page_size


@router.get("/restaurants")
async def list_restaurants(
    params: tuple[int, int] = Depends(_page_params),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    page, page_size = params
    total = (await db.execute(select(func.count()).select_from(Restaurant))).scalar()
    rows = (
        await db.execute(
            select(Restaurant)
            .order_by(Restaurant.name)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars()
    items = [
        RestaurantOut(
            id=r.id, name=r.name, description=r.description, is_active=r.is_active
        )
        for r in rows
    ]
    return Page(items=items, page=page, page_size=page_size, total=total or 0)


@router.get("/restaurants/{restaurant_id}/menu")
async def restaurant_menu(
    restaurant_id: str,
    params: tuple[int, int] = Depends(_page_params),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    page, page_size = params
    restaurant = (
        await db.execute(select(Restaurant).where(Restaurant.id == restaurant_id))
    ).scalar_one_or_none()
    if restaurant is None:
        raise HTTPException(status_code=404, detail="Restaurant not found.")
    total = (
        await db.execute(
            select(func.count())
            .select_from(MenuItem)
            .where(MenuItem.restaurant_id == restaurant_id)
        )
    ).scalar()
    rows = (
        await db.execute(
            select(MenuItem)
            .where(MenuItem.restaurant_id == restaurant_id)
            .order_by(MenuItem.name)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars()
    items = [
        MenuItemOut(
            id=m.id,
            restaurant_id=m.restaurant_id,
            name=m.name,
            description=m.description,
            price_minor=m.price_minor,
            currency=m.currency,
            is_active=m.is_active,
        )
        for m in rows
    ]
    return Page(items=items, page=page, page_size=page_size, total=total or 0)
