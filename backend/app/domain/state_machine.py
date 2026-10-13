"""Order state machine (assignment §6).

PENDING -> PAID -> CONFIRMED -> DRIVER_ASSIGNED
PENDING -> PAYMENT_FAILED
PAID -> FAILED
CONFIRMED -> FAILED

Terminal states: DRIVER_ASSIGNED, PAYMENT_FAILED, FAILED.
Transitions are applied under a row lock with a version check.
"""

from __future__ import annotations

PENDING = "PENDING"
PAID = "PAID"
CONFIRMED = "CONFIRMED"
DRIVER_ASSIGNED = "DRIVER_ASSIGNED"
PAYMENT_FAILED = "PAYMENT_FAILED"
FAILED = "FAILED"

TERMINAL_STATES = frozenset({DRIVER_ASSIGNED, PAYMENT_FAILED, FAILED})

ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    PENDING: frozenset({PAID, PAYMENT_FAILED}),
    PAID: frozenset({CONFIRMED, FAILED}),
    CONFIRMED: frozenset({DRIVER_ASSIGNED, FAILED}),
    DRIVER_ASSIGNED: frozenset(),
    PAYMENT_FAILED: frozenset(),
    FAILED: frozenset(),
}


class InvalidTransitionError(ValueError):
    pass


class StaleVersionError(ValueError):
    pass


def is_allowed(from_status: str, to_status: str) -> bool:
    return to_status in ALLOWED_TRANSITIONS.get(from_status, frozenset())


def check_transition(from_status: str, to_status: str) -> None:
    if not is_allowed(from_status, to_status):
        raise InvalidTransitionError(
            f"transition {from_status} -> {to_status} is not allowed"
        )


def apply_transition(order: object, to_status: str, expected_version: int) -> None:
    """Apply a transition to an ORM order row holding the row lock.

    Verifies the version (compare-and-set) and bumps it. Must be called
    inside the transaction that locked the row.
    """
    current_status = order.status  # type: ignore[attr-defined]
    current_version = order.version  # type: ignore[attr-defined]
    if current_version != expected_version:
        raise StaleVersionError(
            f"stale version: expected {expected_version}, found {current_version}"
        )
    check_transition(current_status, to_status)
    order.status = to_status  # type: ignore[attr-defined]
    order.version = current_version + 1  # type: ignore[attr-defined]
