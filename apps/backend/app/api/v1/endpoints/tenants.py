from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.api import deps
from app.db.session import get_db
from app.schemas.tenant import Tenant, TenantCreate, TenantUpdate, TenantWithToken
from app.services import tenant as tenant_service
from app.models.user import User

router = APIRouter()

@router.get("/", response_model=List[Tenant])
async def read_tenants(
    db: AsyncSession = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(deps.get_current_active_superuser),
):
    """Retrieve tenants. (Admin only)"""
    return await tenant_service.get_tenants(db, skip=skip, limit=limit)

@router.post("/", response_model=Tenant)
async def create_tenant(
    *,
    db: AsyncSession = Depends(get_db),
    tenant_in: TenantCreate,
    current_user: User = Depends(deps.get_current_active_superuser),
):
    """Create new tenant. (Admin only)"""
    db_tenant = await tenant_service.get_tenant_by_slug(db, slug=tenant_service.slugify(tenant_in.name))
    if db_tenant:
        raise HTTPException(status_code=400, detail="Tenant with this name already exists")
    return await tenant_service.create_tenant(db, tenant_in=tenant_in)

@router.get("/{tenant_id}", response_model=Tenant)
async def read_tenant(
    tenant_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user),
):
    """Get tenant by ID."""
    await deps.check_tenant_access(tenant_id, current_user, db)
    db_tenant = await tenant_service.get_tenant(db, tenant_id=tenant_id)
    if not db_tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return db_tenant


@router.get("/{tenant_id}/token", response_model=TenantWithToken)
async def read_tenant_with_token(
    tenant_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_superuser),
):
    """Get tenant by ID including unmasked Influx token. (Admin only)"""
    db_tenant = await tenant_service.get_tenant(db, tenant_id=tenant_id)
    if not db_tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return db_tenant

@router.put("/{tenant_id}", response_model=Tenant)
async def update_tenant(
    *,
    db: AsyncSession = Depends(get_db),
    tenant_id: int,
    tenant_in: TenantUpdate,
    current_user: User = Depends(deps.get_current_active_superuser),
):
    """Update a tenant. (Admin only)"""
    db_tenant = await tenant_service.get_tenant(db, tenant_id=tenant_id)
    if not db_tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return await tenant_service.update_tenant(db, db_obj=db_tenant, tenant_in=tenant_in)

@router.delete("/{tenant_id}", response_model=bool)
async def delete_tenant(
    tenant_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_superuser),
):
    """Delete a tenant. (Admin only)"""
    success = await tenant_service.delete_tenant(db, tenant_id=tenant_id)
    if not success:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return success
