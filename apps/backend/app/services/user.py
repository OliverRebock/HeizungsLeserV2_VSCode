from typing import List, Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, update, insert
from sqlalchemy.orm import selectinload
from app.models.user import User, UserTenantLink
from app.models.tenant import Tenant
from app.schemas.user import UserCreate, UserUpdate
from app.core.security import get_password_hash

async def get_user(db: AsyncSession, user_id: int) -> Optional[User]:
    result = await db.execute(
        select(User)
        .options(selectinload(User.tenant_links).selectinload(UserTenantLink.tenant))
        .where(User.id == user_id)
    )
    return result.scalar_one_or_none()

async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
    result = await db.execute(
        select(User)
        .options(selectinload(User.tenant_links).selectinload(UserTenantLink.tenant))
        .where(User.email == email)
    )
    return result.scalar_one_or_none()

async def get_users(db: AsyncSession, skip: int = 0, limit: int = 100) -> List[User]:
    result = await db.execute(
        select(User)
        .options(selectinload(User.tenant_links).selectinload(UserTenantLink.tenant))
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()

async def get_users_by_tenant(db: AsyncSession, tenant_id: int, skip: int = 0, limit: int = 100) -> List[User]:
    # Join with UserTenantLink
    stmt = (
        select(User)
        .options(selectinload(User.tenant_links).selectinload(UserTenantLink.tenant))
        .join(UserTenantLink, User.id == UserTenantLink.user_id)
        .where(UserTenantLink.tenant_id == tenant_id)
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(stmt)
    return result.scalars().all()

async def create_user(db: AsyncSession, *, user_in: UserCreate) -> User:
    db_obj = User(
        email=user_in.email,
        hashed_password=get_password_hash(user_in.password),
        full_name=user_in.full_name,
        is_active=user_in.is_active,
        is_superuser=False,
    )
    db.add(db_obj)
    await db.flush() # Get ID
    
    if user_in.tenant_id:
        await db.execute(
            insert(UserTenantLink).values(
                user_id=db_obj.id,
                tenant_id=user_in.tenant_id,
                role=user_in.role or "tenant_user"
            )
        )
    
    await db.commit()
    # Explicitly load relationships before returning to avoid lazy loading issues in async context
    stmt = (
        select(User)
        .options(selectinload(User.tenant_links).selectinload(UserTenantLink.tenant))
        .where(User.id == db_obj.id)
    )
    result = await db.execute(stmt)
    return result.scalar_one()

async def update_user(db: AsyncSession, *, db_obj: User, user_in: UserUpdate) -> User:
    if user_in.password:
        db_obj.hashed_password = get_password_hash(user_in.password)
    if user_in.full_name is not None:
        db_obj.full_name = user_in.full_name
    if user_in.email is not None:
        db_obj.email = user_in.email
    if user_in.is_active is not None:
        db_obj.is_active = user_in.is_active
    
    # Update role/tenant if provided
    if user_in.tenant_id is not None:
        # Check if already exists
        stmt = select(UserTenantLink).where(
            UserTenantLink.user_id == db_obj.id,
            UserTenantLink.tenant_id == user_in.tenant_id
        )
        res = await db.execute(stmt)
        existing = res.first()
        
        if existing:
            if user_in.role:
                await db.execute(
                    update(UserTenantLink)
                    .where(UserTenantLink.user_id == db_obj.id, UserTenantLink.tenant_id == user_in.tenant_id)
                    .values(role=user_in.role)
                )
        else:
            await db.execute(
                insert(UserTenantLink).values(
                    user_id=db_obj.id,
                    tenant_id=user_in.tenant_id,
                    role=user_in.role or "tenant_user"
                )
            )

    db.add(db_obj)
    await db.commit()
    # Explicitly load relationships before returning to avoid lazy loading issues in async context
    stmt = (
        select(User)
        .options(selectinload(User.tenant_links).selectinload(UserTenantLink.tenant))
        .where(User.id == db_obj.id)
    )
    result = await db.execute(stmt)
    return result.scalar_one()

async def delete_user(db: AsyncSession, user_id: int) -> bool:
    # First delete roles
    await db.execute(delete(UserTenantLink).where(UserTenantLink.user_id == user_id))
    # Then delete user
    result = await db.execute(delete(User).where(User.id == user_id))
    await db.commit()
    return result.rowcount > 0

async def reset_password(db: AsyncSession, user_id: int, new_password: str) -> bool:
    hashed_password = get_password_hash(new_password)
    stmt = update(User).where(User.id == user_id).values(hashed_password=hashed_password)
    result = await db.execute(stmt)
    await db.commit()
    return result.rowcount > 0

async def get_user_role_in_tenant(db: AsyncSession, user_id: int, tenant_id: int) -> Optional[str]:
    stmt = select(UserTenantLink.role).where(
        UserTenantLink.user_id == user_id,
        UserTenantLink.tenant_id == tenant_id
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()
