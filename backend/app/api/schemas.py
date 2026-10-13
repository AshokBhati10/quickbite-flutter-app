"""Pydantic request/response schemas for the /api/v1 contract."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    email: str
    password: str


class UserSummary(BaseModel):
    id: str
    email: str
    role: str
    name: str


class LoginResponse(BaseModel):
    access_token: str
    expires_at: datetime
    role: str
    user: UserSummary


class Page(BaseModel):
    items: list
    page: int
    page_size: int
    total: int


class RestaurantOut(BaseModel):
    id: str
    name: str
    description: str
    is_active: bool


class MenuItemOut(BaseModel):
    id: str
    restaurant_id: str
    name: str
    description: str
    price_minor: int
    currency: str
    is_active: bool


class CheckoutLine(BaseModel):
    menu_item_id: str
    quantity: int = Field(ge=1, le=20)


class CheckoutRequest(BaseModel):
    restaurant_id: str
    delivery_address: str = Field(min_length=8, max_length=500)
    items: list[CheckoutLine] = Field(min_length=1, max_length=20)


class OrderAccepted(BaseModel):
    order_id: str
    status: str
    currency: str
    total_amount_minor: int
    version: int
    message: str = "Order accepted for asynchronous processing."


class OrderItemOut(BaseModel):
    menu_item_id: str
    name: str
    unit_price_minor: int
    quantity: int


class OrderOut(BaseModel):
    id: str
    status: str
    currency: str
    total_minor: int
    version: int
    failure_code: str | None = None
    driver_id: str | None = None
    restaurant_id: str
    delivery_address: str
    items: list[OrderItemOut] = []
    created_at: datetime
    updated_at: datetime


class HistoryEntry(BaseModel):
    from_status: str | None
    to_status: str
    order_version: int
    created_at: datetime


class NotificationOut(BaseModel):
    event_id: str
    event_type: str
    order_id: str
    title: str
    body: str
    created_at: datetime


class SummaryOut(BaseModel):
    orders_by_status: dict[str, int]
    pending_outbox: int
    scheduled_retries: int
    quarantine_records: int
    oldest_pending_outbox_age_s: float | None
