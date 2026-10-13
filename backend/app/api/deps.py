"""Auth dependencies: 401 for missing/invalid tokens, role checks (403)."""

from __future__ import annotations

from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.db import session_factory
from app.domain.auth import AuthError, verify_token
from app.domain.models import User


async def get_db():
    factory = session_factory()
    async with factory() as session:
        yield session


def _bearer(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid credentials.")
    return authorization[len("Bearer "):]


async def get_current_user(
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
    db: AsyncSession = Depends(get_db),
) -> User:
    token = _bearer(authorization)
    try:
        claims = verify_token(
            token, secret=settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM]
        )
    except AuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    user = (
        await db.execute(select(User).where(User.id == claims["sub"]))
    ).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=401, detail="User no longer exists.")
    return user


async def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required.")
    return user
