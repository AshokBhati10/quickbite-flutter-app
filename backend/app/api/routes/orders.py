"""POST /orders checkout + order reads (assignment §7)."""

from __future__ import annotations

import hashlib
import json

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.api.schemas import (
    CheckoutRequest,
    HistoryEntry,
    NotificationOut,
    OrderAccepted,
    OrderItemOut,
    OrderOut,
    Page,
)
from app.core.logging import log_event
from app.domain.models import (
    IdempotencyKey,
    MenuItem,
    Notification,
    Order,
    OrderItem,
    OrderStatusHistory,
    OutboxEvent,
    User,
    new_id,
)
from app.messaging.envelopes import build_envelope

router = APIRouter()

MAX_DISTINCT_ITEMS = 20


def canonical_hash(body: CheckoutRequest) -> str:
    canonical = {
        "restaurant_id": body.restaurant_id,
        "delivery_address": body.delivery_address.strip(),
        "items": sorted(
            [(l.menu_item_id, l.quantity) for l in body.items],
            key=lambda t: t[0],
        ),
    }
    return hashlib.sha256(
        json.dumps(canonical, separators=(",", ":")).encode()
    ).hexdigest()


def _order_out(order: Order, items: list[OrderItem]) -> OrderOut:
    return OrderOut(
        id=order.id,
        status=order.status,
        currency=order.currency,
        total_minor=order.total_minor,
        version=order.version,
        failure_code=order.failure_code,
        driver_id=order.driver_id,
        restaurant_id=order.restaurant_id,
        delivery_address=order.delivery_address,
        items=[
            OrderItemOut(
                menu_item_id=i.menu_item_id,
                name=i.name,
                unit_price_minor=i.unit_price_minor,
                quantity=i.quantity,
            )
            for i in items
        ],
        created_at=order.created_at,
        updated_at=order.updated_at,
    )


async def _load_items(db: AsyncSession, order_id: str) -> list[OrderItem]:
    return list(
        (
            await db.execute(select(OrderItem).where(OrderItem.order_id == order_id))
        ).scalars()
    )


@router.post("/orders", status_code=202)
async def create_order(
    body: CheckoutRequest,
    response: Response,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not idempotency_key:
        raise HTTPException(status_code=422, detail="Idempotency-Key header required.")
    if len(body.items) > MAX_DISTINCT_ITEMS:
        raise HTTPException(status_code=422, detail="Too many distinct items.")
    line_ids = [l.menu_item_id for l in body.items]
    if len(set(line_ids)) != len(line_ids):
        raise HTTPException(status_code=422, detail="Duplicate menu items.")

    menu = (
        await db.execute(select(MenuItem).where(MenuItem.id.in_(line_ids)))
    ).scalars()
    by_id = {m.id: m for m in menu}
    if len(by_id) != len(line_ids):
        raise HTTPException(status_code=422, detail="Unknown menu item.")
    first = by_id[line_ids[0]]
    for m in by_id.values():
        if m.restaurant_id != body.restaurant_id:
            raise HTTPException(status_code=422, detail="Mixed restaurants.")
        if not m.is_active:
            raise HTTPException(status_code=422, detail=f"Item unavailable: {m.name}")
    # Client-supplied totals/prices are never trusted: recompute server-side.
    total = sum(by_id[l.menu_item_id].price_minor * l.quantity for l in body.items)
    currency = first.currency
    req_hash = canonical_hash(body)
    # Stash the primitive: ORM instances expire on commit/rollback and any
    # later attribute access would trigger sync lazy IO (MissingGreenlet).
    user_id = user.id

    existing = (
        await db.execute(
            select(IdempotencyKey).where(
                IdempotencyKey.user_id == user_id,
                IdempotencyKey.key == idempotency_key,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        if existing.request_hash != req_hash:
            raise HTTPException(
                status_code=409, detail="Idempotency key reused with payload."
            )
        response.headers["Location"] = f"/api/v1/orders/{existing.order_id}"
        return existing.response_body

    order_id = new_id("order")
    event_id = new_id("evt")
    order = Order(
        id=order_id,
        customer_id=user_id,
        restaurant_id=body.restaurant_id,
        delivery_address=body.delivery_address.strip(),
        currency=currency,
        total_minor=total,
        status="PENDING",
        version=1,
    )
    db.add(order)
    # Flush the parent row first: without mapper relationships the unit of
    # work has no dependency hint and may insert children first, violating
    # the order_id foreign keys.
    await db.flush()
    for line in body.items:
        m = by_id[line.menu_item_id]
        db.add(
            OrderItem(
                id=new_id("oi"),
                order_id=order_id,
                menu_item_id=m.id,
                name=m.name,
                unit_price_minor=m.price_minor,
                quantity=line.quantity,
            )
        )
    db.add(
        OrderStatusHistory(
            id=new_id("hist"),
            order_id=order_id,
            from_status=None,
            to_status="PENDING",
            order_version=1,
        )
    )
    accepted = OrderAccepted(
        order_id=order_id,
        status="PENDING",
        currency=currency,
        total_amount_minor=total,
        version=1,
    ).model_dump(mode="json")
    db.add(
        IdempotencyKey(
            id=new_id("idem"),
            user_id=user_id,
            key=idempotency_key,
            request_hash=req_hash,
            response_body=accepted,
            order_id=order_id,
        )
    )
    db.add(
        OutboxEvent(
            id=new_id("obx"),
            event_id=event_id,
            event_type="order.created",
            exchange="quickbite.orders",
            routing_key="order.created",
            payload=build_envelope(
                event_id=event_id,
                event_type="order.created",
                order_id=order_id,
                order_version=1,
                correlation_id=idempotency_key,
                data={"customer_id": user_id, "restaurant_id": body.restaurant_id},
            ),
        )
    )
    try:
        await db.commit()
    except IntegrityError:
        # Concurrent identical submission won the race: replay stored response.
        await db.rollback()
        winner = (
            await db.execute(
                select(IdempotencyKey).where(
                    IdempotencyKey.user_id == user_id,
                    IdempotencyKey.key == idempotency_key,
                )
            )
        ).scalar_one_or_none()
        if winner is None or winner.request_hash != req_hash:
            raise HTTPException(
                status_code=409, detail="Idempotency key reused with payload."
            )
        response.headers["Location"] = f"/api/v1/orders/{winner.order_id}"
        return winner.response_body

    log_event(
        "order.accepted", order_id=order_id, customer_id=user_id, total_minor=total
    )
    response.headers["Location"] = f"/api/v1/orders/{order_id}"
    return accepted


async def _owned_order(
    db: AsyncSession, order_id: str, user: User
) -> tuple[Order, list[OrderItem]]:
    order = (
        await db.execute(select(Order).where(Order.id == order_id))
    ).scalar_one_or_none()
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found.")
    if user.role != "admin" and order.customer_id != user.id:
        # Other customers' orders are indistinguishable from unknown.
        raise HTTPException(status_code=404, detail="Order not found.")
    return order, await _load_items(db, order_id)


@router.get("/orders")
async def list_orders(
    status: str | None = Query(default=None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    stmt = select(Order).where(Order.customer_id == user.id)
    count_stmt = (
        select(func.count()).select_from(Order).where(Order.customer_id == user.id)
    )
    if status:
        stmt = stmt.where(Order.status == status)
        count_stmt = count_stmt.where(Order.status == status)
    total = (await db.execute(count_stmt)).scalar() or 0
    rows = (
        await db.execute(
            stmt.order_by(Order.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars()
    items = []
    for o in rows:
        items.append(_order_out(o, await _load_items(db, o.id)).model_dump(mode="json"))
    return Page(items=items, page=page, page_size=page_size, total=total)


@router.get("/orders/{order_id}")
async def get_order(
    order_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    order, items = await _owned_order(db, order_id, user)
    return _order_out(order, items)


@router.get("/orders/{order_id}/history")
async def get_history(
    order_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    order, _ = await _owned_order(db, order_id, user)
    rows = (
        await db.execute(
            select(OrderStatusHistory)
            .where(OrderStatusHistory.order_id == order.id)
            .order_by(OrderStatusHistory.order_version)
        )
    ).scalars()
    return [
        HistoryEntry(
            from_status=h.from_status,
            to_status=h.to_status,
            order_version=h.order_version,
            created_at=h.created_at,
        )
        for h in rows
    ]


@router.get("/orders/{order_id}/notifications")
async def get_notifications(
    order_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    order, _ = await _owned_order(db, order_id, user)
    total = (
        await db.execute(
            select(func.count())
            .select_from(Notification)
            .where(Notification.order_id == order.id)
        )
    ).scalar() or 0
    rows = (
        await db.execute(
            select(Notification)
            .where(Notification.order_id == order.id)
            .order_by(Notification.created_at)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars()
    items = [
        NotificationOut(
            event_id=n.event_id,
            event_type=n.event_type,
            order_id=n.order_id,
            title=n.title,
            body=n.body,
            created_at=n.created_at,
        )
        for n in rows
    ]
    return Page(
        items=[i.model_dump(mode="json") for i in items],
        page=page,
        page_size=page_size,
        total=total,
    )
