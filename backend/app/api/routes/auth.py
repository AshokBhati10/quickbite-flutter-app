"""POST /auth/login, GET /me."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.api.schemas import (
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    UserSummary,
)
from app.core.config import Settings, get_settings
from app.core.logging import log_event
from app.domain.auth import hash_password, issue_token, verify_password
from app.domain.models import User, new_id

router = APIRouter()


def _summary(user: User) -> UserSummary:
    return UserSummary(id=user.id, email=user.email, role=user.role, name=user.name)


@router.post("/auth/register", response_model=LoginResponse, status_code=201)
async def register(
    body: RegisterRequest,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    email = body.email.strip().lower()
    local, _, domain = email.partition("@")
    if not local or "." not in domain:
        raise HTTPException(status_code=422, detail="Enter a valid email address.")
    existing = (
        await db.execute(select(User).where(func.lower(User.email) == email))
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=409, detail="An account with this email already exists."
        )
    user_id = new_id("user")
    name = body.name.strip()
    user = User(
        id=user_id,
        email=email,
        password_hash=hash_password(body.password),
        role="customer",
        name=name,
    )
    db.add(user)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=409, detail="An account with this email already exists."
        )
    # Attributes expire on commit: build the response from captured values.
    token, exp = issue_token(
        user_id=user_id,
        role="customer",
        secret=settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
        expire_minutes=settings.JWT_EXPIRE_MINUTES,
    )
    log_event("auth.register", user_id=user_id, role="customer")
    return LoginResponse(
        access_token=token,
        expires_at=exp,
        role="customer",
        user=UserSummary(id=user_id, email=email, role="customer", name=name),
    )


@router.post("/auth/login", response_model=LoginResponse)
async def login(
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    user = (
        await db.execute(
            select(User).where(func.lower(User.email) == body.email.strip().lower())
        )
    ).scalar_one_or_none()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    token, exp = issue_token(
        user_id=user.id,
        role=user.role,
        secret=settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
        expire_minutes=settings.JWT_EXPIRE_MINUTES,
    )
    log_event("auth.login", user_id=user.id, role=user.role)
    return LoginResponse(
        access_token=token, expires_at=exp, role=user.role, user=_summary(user)
    )


@router.get("/me", response_model=UserSummary)
async def me(user: User = Depends(get_current_user)):
    return _summary(user)
