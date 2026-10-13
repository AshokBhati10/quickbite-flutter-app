"""Event envelope builder/validator (assignment §9).

Required fields: event_id, schema_version, event_type, order_id,
order_version, occurred_at, correlation_id, causation_id, data.
AMQP message_id == event_id, JSON content type, persistent delivery.
"""

from __future__ import annotations

from datetime import datetime, timezone

SCHEMA_VERSION = 1

REQUIRED_FIELDS = (
    "event_id",
    "schema_version",
    "event_type",
    "order_id",
    "order_version",
    "occurred_at",
    "correlation_id",
    "causation_id",
    "data",
)


class EnvelopeError(ValueError):
    pass


def build_envelope(
    *,
    event_id: str,
    event_type: str,
    order_id: str,
    order_version: int,
    correlation_id: str,
    data: dict,
    causation_id: str | None = None,
) -> dict:
    return {
        "event_id": event_id,
        "schema_version": SCHEMA_VERSION,
        "event_type": event_type,
        "order_id": order_id,
        "order_version": order_version,
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "correlation_id": correlation_id,
        "causation_id": causation_id,
        "data": data,
    }


def validate_envelope(payload: dict) -> dict:
    if not isinstance(payload, dict):
        raise EnvelopeError("envelope must be a JSON object")
    for field in REQUIRED_FIELDS:
        if field not in payload:
            raise EnvelopeError(f"envelope missing field: {field}")
    if payload["schema_version"] != SCHEMA_VERSION:
        raise EnvelopeError(
            f"unsupported schema_version: {payload['schema_version']}"
        )
    if not payload["event_id"] or not payload["order_id"]:
        raise EnvelopeError("event_id and order_id must be non-empty")
    return payload
