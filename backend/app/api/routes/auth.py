"""POST /auth/login, GET /me."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.api.schemas import LoginRequest, LoginResponse, UserSummary
from app.core.config import Settings, get_settings
from app.core.logging import log_event
from app.domain.auth import issue_token, verify_password
from app.domain.models import User

router = APIRouter()


@router.post("/auth/login", response_model=LoginResponse)
async def login(
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    user = (
        await db.execute(select(User).where(User.email == body.email))
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
        access_token=token,
        expires_at=exp,
        role=user.role,
        user=UserSummary(
            id=user.id, email=user.email, role=user.role, name=user.name
        ),
    )


@router.get("/me", response_model=UserSummary)
async def me(user: User = Depends(get_current_user)):
    return UserSummary(id=user.id, email=user.email, role=user.role, name=user.name)
