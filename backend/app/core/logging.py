"""Structured JSON logging. Never logs tokens, passwords, or full addresses."""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone

REDACTED = {"authorization", "password", "password_hash", "token", "delivery_address"}

logger = logging.getLogger("quickbite")


def configure_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.handlers = [handler]
    logger.setLevel(logging.INFO)
    logger.propagate = False


def _scrub(data: dict) -> dict:
    out = {}
    for key, value in data.items():
        if key.lower() in REDACTED:
            out[key] = "***"
        elif key.lower() == "delivery_address" and isinstance(value, str):
            out[key] = value[:12] + "…(truncated)"
        else:
            out[key] = value
    return out


def log_event(event: str, **fields) -> None:
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "service": fields.pop("service", "api"),
        "event": event,
        **_scrub(fields),
    }
    logger.info(json.dumps(record))
