from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from datetime import timedelta
from typing import List, Dict, Any

from app.api import deps
from app.core import security
from app.core.config import settings
from app.db.session import get_db
from app.models.user import User, UserTenantLink
from app.models.tenant import Tenant
from app.schemas.user import Token, User as UserSchema, UserTenantRole

router = APIRouter()

@router.post("/login", response_model=Token)
async def login_access_token(
    db: AsyncSession = Depends(get_db), form_data: OAuth2PasswordRequestForm = Depends()
) -> Token:
    """OAuth2 compatible token login, get an access token for future requests."""
    result = await db.execute(select(User).where(User.email == form_data.username))
    user = result.scalar_one_or_none()
    
    if not user or not security.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    elif not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    
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
