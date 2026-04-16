from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from datetime import timedelta
from typing import Any

from app.api import deps
from app.core.login_protection import login_rate_limiter
from app.core import security
from app.core.config import settings
from app.db.session import get_db
from app.models.user import User, UserTenantLink
from app.schemas.user import Token, User as UserSchema

router = APIRouter()


def _get_client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _build_rate_limit_keys(client_ip: str, username: str) -> tuple[str, str]:
    normalized_username = username.strip().lower()
    return (f"ip:{client_ip}", f"ip-user:{client_ip}:{normalized_username}")

@router.post("/login", response_model=Token)
async def login_access_token(
    request: Request,
    db: AsyncSession = Depends(get_db),
    form_data: OAuth2PasswordRequestForm = Depends(),
) -> Token:
    """OAuth2 compatible token login, get an access token for future requests."""
    client_ip = _get_client_ip(request)
    rate_limit_keys = _build_rate_limit_keys(client_ip, form_data.username)
    retry_after = login_rate_limiter.check_allowed(*rate_limit_keys)
    if retry_after:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Please try again later.",
            headers={"Retry-After": str(retry_after)},
        )

    result = await db.execute(select(User).where(User.email == form_data.username))
    user = result.scalar_one_or_none()
    
    if not user or not security.verify_password(form_data.password, user.hashed_password):
        retry_after = login_rate_limiter.register_failure(*rate_limit_keys)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect email or password",
            headers={"Retry-After": str(retry_after)} if retry_after else None,
        )
    elif not user.is_active:
        login_rate_limiter.register_failure(*rate_limit_keys)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user")

    login_rate_limiter.register_success(*rate_limit_keys)
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return Token(
        access_token=security.create_access_token(
            user.id, expires_delta=access_token_expires
        ),
        token_type="bearer",
    )

@router.get("/me", response_model=UserSchema)
async def read_user_me(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """Get current user with tenant roles."""
    # Ensure tenant links are loaded asynchrounously
    stmt = (
        select(User)
        .options(selectinload(User.tenant_links).selectinload(UserTenantLink.tenant))
        .where(User.id == current_user.id)
    )
    result = await db.execute(stmt)
    full_user = result.scalar_one_or_none()
    return full_user or current_user
