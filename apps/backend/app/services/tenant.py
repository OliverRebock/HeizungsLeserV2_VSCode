from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
import re
from app.models.tenant import Tenant
from app.schemas.tenant import TenantCreate, TenantUpdate
from app.services.influx import influx_service

def slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")

async def get_tenant(db: AsyncSession, tenant_id: int) -> Optional[Tenant]:
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    return result.scalar_one_or_none()

async def get_tenant_by_slug(db: AsyncSession, slug: str) -> Optional[Tenant]:
    result = await db.execute(select(Tenant).where(Tenant.slug == slug))
    return result.scalar_one_or_none()

async def get_tenants(db: AsyncSession, skip: int = 0, limit: int = 100) -> List[Tenant]:
    result = await db.execute(select(Tenant).offset(skip).limit(limit))
    return result.scalars().all()

async def create_tenant(db: AsyncSession, tenant_in: TenantCreate) -> Tenant:
    slug = slugify(tenant_in.name)
    db_obj = Tenant(
        name=tenant_in.name,
        slug=slug,
        is_active=tenant_in.is_active
    )
    db.add(db_obj)
    await db.flush() # ID generieren
    
    # InfluxDB Provisionierung
    bucket_name = f"tenant_{db_obj.id}_{slug}"
    bucket_res = await influx_service.create_database(bucket_name, retention="365d")
    
    if bucket_res["status"] in ["ok", "exists"]:
        db_obj.influx_bucket = bucket_name
        token_res = await influx_service.create_service_token(
            bucket_name, 
            description=f"HA Token for {tenant_in.name}"
        )
        if token_res["status"] == "ok":
            db_obj.influx_token = token_res["token"]

    await db.commit()
    await db.refresh(db_obj)
    return db_obj

async def delete_tenant(db: AsyncSession, tenant_id: int) -> bool:
    db_tenant = await get_tenant(db, tenant_id)
    if not db_tenant:
        return False
    
    # Optional: InfluxDB Bucket löschen? (Lieber behalten aus Sicherheitsgründen)
    
    await db.delete(db_tenant)
    await db.commit()
    return True

async def update_tenant(db: AsyncSession, db_obj: Tenant, tenant_in: TenantUpdate) -> Tenant:
    update_data = tenant_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_obj, field, value)
        if field == "name":
            db_obj.slug = slugify(value)
    
    db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)
    return db_obj
