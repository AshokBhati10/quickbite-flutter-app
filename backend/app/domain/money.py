"""Money helpers: integer minor units + currency (assignment §6)."""

from __future__ import annotations

DEFAULT_CURRENCY = "INR"


def format_minor(amount_minor: int, currency: str = DEFAULT_CURRENCY) -> str:
    """Format minor units for display, e.g. 2900 -> 'INR 29.00'."""
    if amount_minor < 0:
        raise ValueError("amount_minor must be >= 0")
    return f"{currency} {amount_minor // 100}.{amount_minor % 100:02d}"


def compute_total(lines: list[tuple[int, int]]) -> int:
    """Sum (unit_price_minor, quantity) lines server-side."""
    total = 0
    for unit_price, qty in lines:
        if unit_price < 0:
            raise ValueError("unit price must be >= 0")
        if not 1 <= qty <= 20:
            raise ValueError("quantity must be within 1..20")
        total += unit_price * qty
    return total
