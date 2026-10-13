"""Unit: state machine, money, auth, envelopes, error envelope shape."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.domain import state_machine as sm
from app.domain.auth import (
    AuthError,
    hash_password,
    issue_token,
    verify_password,
    verify_token,
)
from app.domain.money import compute_total, format_minor
from app.messaging.envelopes import (
    EnvelopeError,
    build_envelope,
    validate_envelope,
)


class _Order:
    def __init__(self, status, version):
        self.status = status
        self.version = version


@pytest.mark.parametrize(
    "frm,to",
    [
        ("PENDING", "PAID"),
        ("PENDING", "PAYMENT_FAILED"),
        ("PAID", "CONFIRMED"),
        ("PAID", "FAILED"),
        ("CONFIRMED", "DRIVER_ASSIGNED"),
        ("CONFIRMED", "FAILED"),
    ],
)
def test_valid_transitions(frm, to) -> None:
    order = _Order(frm, 3)
    sm.apply_transition(order, to, 3)
    assert order.status == to
    assert order.version == 4


@pytest.mark.parametrize(
    "frm,to",
    [
        ("PAID", "PENDING"),
        ("CONFIRMED", "PAID"),
        ("DRIVER_ASSIGNED", "CONFIRMED"),
        ("PAYMENT_FAILED", "PAID"),
        ("FAILED", "PAID"),
        ("PENDING", "CONFIRMED"),
        ("PENDING", "DRIVER_ASSIGNED"),
        ("PAID", "PAYMENT_FAILED"),
    ],
)
def test_invalid_and_backward_transitions_rejected(frm, to) -> None:
    order = _Order(frm, 1)
    with pytest.raises(sm.InvalidTransitionError):
        sm.apply_transition(order, to, 1)
    assert order.status == frm
    assert order.version == 1


def test_stale_version_rejected() -> None:
    order = _Order("PENDING", 2)
    with pytest.raises(sm.StaleVersionError):
        sm.apply_transition(order, "PAID", 1)


def test_terminal_states_have_no_outgoing() -> None:
    for state in ("DRIVER_ASSIGNED", "PAYMENT_FAILED", "FAILED"):
        assert state in sm.TERMINAL_STATES
        assert sm.ALLOWED_TRANSITIONS[state] == frozenset()


def test_money_helpers() -> None:
    assert compute_total([(1250, 2), (400, 1)]) == 2900
    assert format_minor(2900) == "INR 29.00"
    with pytest.raises(ValueError):
        compute_total([(100, 0)])
    with pytest.raises(ValueError):
        compute_total([(100, 21)])


def test_password_hash_roundtrip() -> None:
    hashed = hash_password("Password123!")
    assert verify_password("Password123!", hashed)
    assert not verify_password("wrong", hashed)


def test_jwt_roundtrip_expiry_tamper() -> None:
    secret = "test-only-secret-1234567890"
    token, _ = issue_token(user_id="u1", role="customer", secret=secret)
    claims = verify_token(token, secret=secret, algorithms=["HS256"])
    assert claims["sub"] == "u1"

    expired_payload_token, _ = issue_token(
        user_id="u1", role="customer", secret=secret, expire_minutes=-1
    )
    # A token whose exp is in the past must be rejected.
    with pytest.raises(AuthError):
        verify_token(expired_payload_token, secret=secret, algorithms=["HS256"])

    with pytest.raises(AuthError):
        verify_token(token + "tampered", secret=secret, algorithms=["HS256"])
    with pytest.raises(AuthError):
        verify_token(token, secret="different-secret-123456", algorithms=["HS256"])


def test_envelope_build_validate() -> None:
    env = build_envelope(
        event_id="evt_1",
        event_type="order.created",
        order_id="order_1",
        order_version=1,
        correlation_id="req_1",
        data={"a": 1},
        causation_id=None,
    )
    assert validate_envelope(env) == env
    bad = dict(env)
    del bad["order_id"]
    with pytest.raises(EnvelopeError):
        validate_envelope(bad)
    bad_version = dict(env, schema_version=999)
    with pytest.raises(EnvelopeError):
        validate_envelope(bad_version)


def test_error_envelope_shape() -> None:
    from fastapi.testclient import TestClient

    from app.api.app import app

    client = TestClient(app)
    resp = client.get("/no-such-route")
    body = resp.json()
    assert resp.status_code == 404
    assert set(body) == {"code", "message", "details", "request_id"}
    resp = client.post("/api/v1/auth/login", json={"email": "x"})
    assert resp.status_code == 422
    assert resp.json()["code"] == "validation_error"
