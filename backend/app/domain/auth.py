"""Password hashing + JWT issue/verify (assignment §8)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
from passlib.context import CryptContext

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return _pwd.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return _pwd.verify(password, password_hash)


def issue_token(
    *,
    user_id: str,
    role: str,
    secret: str,
    algorithm: str = "HS256",
    expire_minutes: int = 60,
) -> tuple[str, datetime]:
    now = datetime.now(timezone.utc)
    exp = now + timedelta(minutes=expire_minutes)
    payload = {"sub": user_id, "role": role, "iat": now, "exp": exp}
    return jwt.encode(payload, secret, algorithm=algorithm), exp


class AuthError(ValueError):
    pass


def verify_token(token: str, *, secret: str, algorithms: list[str]) -> dict:
    try:
        payload = jwt.decode(token, secret, algorithms=algorithms)
    except jwt.ExpiredSignatureError as exc:
        raise AuthError("token expired") from exc
    except jwt.InvalidTokenError as exc:
        raise AuthError("invalid token") from exc
    if "sub" not in payload or "role" not in payload:
        raise AuthError("token missing required claims")
    return payload
