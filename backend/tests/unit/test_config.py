"""Unit tests for startup config validation (Phase 0 gate)."""

import pytest
from pydantic import ValidationError

from app.core.config import Settings

VALID = dict(
    DATABASE_URL="postgresql+asyncpg://quickbite:quickbite@localhost:5432/quickbite",
    SYNC_DATABASE_URL="postgresql+psycopg://quickbite:quickbite@localhost:5432/quickbite",
    AMQP_URL="amqp://quickbite:quickbite@localhost:5672/%2F",
    JWT_SECRET="a-very-long-test-secret-12345",
)


def test_valid_config_loads() -> None:
    s = Settings(**VALID)
    assert s.JWT_ALGORITHM == "HS256"
    assert s.retry_delays() == [2.0, 10.0, 30.0]
    assert s.cors_origin_list == ["http://localhost:3000"]


def test_missing_secret_fails() -> None:
    bad = dict(VALID, JWT_SECRET="change-me-to-a-long-random-secret")
    with pytest.raises(ValidationError):
        Settings(**bad)


def test_short_secret_fails() -> None:
    bad = dict(VALID, JWT_SECRET="short")
    with pytest.raises(ValidationError):
        Settings(**bad)


def test_malformed_database_url_fails() -> None:
    bad = dict(VALID, DATABASE_URL="sqlite:///foo.db")
    with pytest.raises(ValidationError):
        Settings(**bad)


def test_malformed_amqp_url_fails() -> None:
    bad = dict(VALID, AMQP_URL="http://localhost:5672")
    with pytest.raises(ValidationError):
        Settings(**bad)


def test_wildcard_cors_fails() -> None:
    bad = dict(VALID, CORS_ORIGINS="*")
    with pytest.raises(ValidationError):
        Settings(**bad)


def test_negative_delay_fails() -> None:
    bad = dict(VALID, PAYMENT_DELAY_S=-1.0)
    with pytest.raises(ValidationError):
        Settings(**bad)


def test_retry_policy_mismatch_fails() -> None:
    s = Settings(**dict(VALID, RETRY_DELAYS_S="2,10"))
    with pytest.raises(ValueError, match="exactly RETRY_MAX_RETRIES"):
        s.retry_delays()


def test_unknown_payment_mode_fails() -> None:
    bad = dict(VALID, PAYMENT_MODE="sometimes")
    with pytest.raises(ValidationError):
        Settings(**bad)
