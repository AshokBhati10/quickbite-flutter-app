"""GET /admin/orders, GET /admin/summary (admin only)."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_admin
from app.api.routes.orders import _load_items, _order_out
from app.api.schemas import Page, SummaryOut
from app.domain.models import Order, OutboxEvent, QuarantineRecord, RetryJob, User

router = APIRouter()


@router.get("/admin/orders")
async def admin_orders(
    status: str | None = Query(default=None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    stmt = select(Order)
    count_stmt = select(func.count()).select_from(Order)
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


@router.get("/admin/summary", response_model=SummaryOut)
async def admin_summary(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    status_rows = (
        await db.execute(select(Order.status, func.count()).group_by(Order.status))
    ).all()
    pending_outbox = (
        await db.execute(
            select(func.count())
            .select_from(OutboxEvent)
            .where(OutboxEvent.sent_at.is_(None))
        )
    ).scalar() or 0
    scheduled = (
        await db.execute(
            select(func.count())
            .select_from(RetryJob)
            .where(RetryJob.status == "scheduled")
        )
    ).scalar() or 0
    quarantined = (
        await db.execute(select(func.count()).select_from(QuarantineRecord))
    ).scalar() or 0
    oldest = (
        await db.execute(
            select(func.min(OutboxEvent.created_at)).where(
                OutboxEvent.sent_at.is_(None)
            )
        )
    ).scalar()
    age = (
        (datetime.now(timezone.utc) - oldest).total_seconds() if oldest else None
    )
    return SummaryOut(
        orders_by_status={s: c for s, c in status_rows},
        pending_outbox=pending_outbox,
        scheduled_retries=scheduled,
        quarantine_records=quarantined,
        oldest_pending_outbox_age_s=age,
    )
