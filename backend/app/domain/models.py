"""SQLAlchemy models for all assignment §6 tables."""

from __future__ import annotations

import secrets
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(8)}"


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False, default="customer")
    name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )


class Restaurant(Base):
    __tablename__ = "restaurants"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    cuisine: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    image_url: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    menu_items: Mapped[list["MenuItem"]] = relationship(back_populates="restaurant")


class MenuItem(Base):
    __tablename__ = "menu_items"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    restaurant_id: Mapped[str] = mapped_column(
        ForeignKey("restaurants.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    category: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    image_url: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    price_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="INR")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    restaurant: Mapped[Restaurant] = relationship(back_populates="menu_items")


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    customer_id: Mapped[str] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    restaurant_id: Mapped[str] = mapped_column(
        ForeignKey("restaurants.id"), nullable=False
    )
    delivery_address: Mapped[str] = mapped_column(String(500), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="INR")
    total_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    failure_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    driver_id: Mapped[str | None] = mapped_column(
        ForeignKey("drivers.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    order_id: Mapped[str] = mapped_column(
        ForeignKey("orders.id"), nullable=False, index=True
    )
    menu_item_id: Mapped[str] = mapped_column(
        ForeignKey("menu_items.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    unit_price_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)


class OrderStatusHistory(Base):
    __tablename__ = "order_status_history"
    __table_args__ = (UniqueConstraint("order_id", "order_version"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    order_id: Mapped[str] = mapped_column(
        ForeignKey("orders.id"), nullable=False, index=True
    )
    from_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    to_status: Mapped[str] = mapped_column(String(32), nullable=False)
    order_version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )


class SimulatedPayment(Base):
    __tablename__ = "simulated_payments"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    order_id: Mapped[str] = mapped_column(
        ForeignKey("orders.id"), unique=True, nullable=False
    )
    idempotency_id: Mapped[str] = mapped_column(
        String(128), unique=True, nullable=False
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )


class Driver(Base):
    __tablename__ = "drivers"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class DriverAssignment(Base):
    __tablename__ = "driver_assignments"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    order_id: Mapped[str] = mapped_column(
        ForeignKey("orders.id"), unique=True, nullable=False
    )
    driver_id: Mapped[str] = mapped_column(ForeignKey("drivers.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (UniqueConstraint("customer_id", "event_id"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    customer_id: Mapped[str] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    event_id: Mapped[str] = mapped_column(String(128), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    order_id: Mapped[str] = mapped_column(
        ForeignKey("orders.id"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )


class ProcessedEvent(Base):
    __tablename__ = "processed_events"
    __table_args__ = (UniqueConstraint("consumer_name", "event_id"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    consumer_name: Mapped[str] = mapped_column(String(64), nullable=False)
    event_id: Mapped[str] = mapped_column(String(128), nullable=False)
    order_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    result: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )


class OutboxEvent(Base):
    __tablename__ = "outbox_events"
    __table_args__ = (
        UniqueConstraint("event_id", "exchange", "routing_key", "attempt"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    event_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    exchange: Mapped[str] = mapped_column(String(128), nullable=False)
    routing_key: Mapped[str] = mapped_column(String(128), nullable=False)
    # Delivery attempt this row represents: 1 for first domain delivery,
    # N+1 for the retry scheduled after attempt N failed. Part of the
    # unique publication identity so consecutive retries never collide.
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )


class RetryJob(Base):
    __tablename__ = "retry_jobs"
    __table_args__ = (UniqueConstraint("consumer_name", "event_id", "attempt"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    consumer_name: Mapped[str] = mapped_column(String(64), nullable=False)
    event_id: Mapped[str] = mapped_column(String(128), nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False)
    run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="scheduled")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )


class QuarantineRecord(Base):
    __tablename__ = "quarantine_records"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    event_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    consumer_name: Mapped[str] = mapped_column(String(64), nullable=False)
    source_queue: Mapped[str] = mapped_column(String(128), nullable=False)
    event_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    failure_code: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )


class IdempotencyKey(Base):
    __tablename__ = "idempotency_keys"
    __table_args__ = (UniqueConstraint("user_id", "key"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    key: Mapped[str] = mapped_column(String(128), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    response_body: Mapped[dict] = mapped_column(JSON, nullable=False)
    order_id: Mapped[str | None] = mapped_column(
        ForeignKey("orders.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
