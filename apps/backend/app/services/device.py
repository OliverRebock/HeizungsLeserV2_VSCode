from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from app.models.device import Device
from app.schemas.device import DeviceCreate, DeviceUpdate
from app.services.tenant import slugify

async def get_device(db: AsyncSession, device_id: int) -> Optional[Device]:
    result = await db.execute(select(Device).where(Device.id == device_id))
    return result.scalar_one_or_none()

async def get_devices(db: AsyncSession, skip: int = 0, limit: int = 100) -> List[Device]:
    result = await db.execute(select(Device).offset(skip).limit(limit))
    return result.scalars().all()

async def get_devices_by_tenant(db: AsyncSession, tenant_id: int) -> List[Device]:
    result = await db.execute(select(Device).where(Device.tenant_id == tenant_id))
    return result.scalars().all()

async def create_device(db: AsyncSession, device_in: DeviceCreate) -> Device:
    device_slug = slugify(device_in.display_name)
    influx_db_name = device_in.influx_database_name
    generated_token = None

    print(f"PROVISIONING: Starting for device {device_in.display_name} in bucket {influx_db_name}")

    # Automatische Influx-DB-Anlage und Token-Generierung
    try:
        from app.services.influx import influx_service
        # 1. Bucket erstellen (Default 90 Tage)
        retention = device_in.retention_policy or "90d"
        bucket_res = await influx_service.create_database(influx_db_name, retention)
        print(f"PROVISIONING: Bucket result: {bucket_res}")
        
        # 2. Spezifischen Service-Token generieren
        if bucket_res["status"] in ["ok", "exists"]:
            token_res = await influx_service.create_service_token(
                influx_db_name, 
                description=f"HA Token for device {device_in.display_name}"
            )
            if token_res["status"] == "ok":
                generated_token = token_res["token"]
                print(f"PROVISIONING: Token successfully generated for device {device_in.display_name}")
            else:
                print(f"PROVISIONING ERROR: Token generation failed for {device_in.display_name}: {token_res.get('error')}")
    except Exception as e:
        print(f"PROVISIONING CRITICAL ERROR for device {device_in.display_name}: {e}")

    db_obj = Device(
        tenant_id=device_in.tenant_id,
        display_name=device_in.display_name,
        slug=device_slug,
        source_type=device_in.source_type,
        influx_database_name=influx_db_name,
        influx_token=generated_token, # Neuer Token wird hier zugewiesen
        retention_policy=device_in.retention_policy,
        source_config=device_in.source_config,
        is_active=device_in.is_active
    )
    db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)
    # Maskierter Token in Log (Sicherheits-Härtung)
    masked_token = f"{generated_token[:4]}...{generated_token[-4:]}" if generated_token and len(generated_token) > 8 else "None"
    print(f"PROVISIONING: Device persisted with ID {db_obj.id}. Token: {masked_token}")
    return db_obj

async def delete_device(db: AsyncSession, db_obj: Device) -> None:
    await db.delete(db_obj)
    await db.commit()

async def update_device(db: AsyncSession, db_obj: Device, device_in: DeviceUpdate) -> Device:
    update_data = device_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_obj, field, value)
        if field == "display_name":
            db_obj.slug = slugify(value)
    
    db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)
    return db_obj
