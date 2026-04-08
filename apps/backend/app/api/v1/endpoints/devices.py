from typing import List, Optional
import datetime
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.api import deps
from app.db.session import get_db
from app.schemas.device import Device, DeviceCreate, DeviceUpdate, DeviceWithToken
from app.services import device as device_service
from app.services.influx import influx_service
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter()

async def _enrich_device_status(db_device: any, schema_type=Device) -> Device:
    """Berechnet den Online-Status basierend auf den letzten 5 Minuten."""
    device_data = schema_type.model_validate(db_device)
    try:
        last_seen = await influx_service.get_last_data_timestamp(db_device.influx_database_name)
        
        if last_seen:
            device_data.last_seen = last_seen
            # Sicherstellen, dass now und last_seen die gleiche Zeitzone haben
            now = datetime.datetime.now(datetime.timezone.utc)
            
            # Falls last_seen naive ist, UTC annehmen (InfluxDB arbeitet idR in UTC)
            if last_seen.tzinfo is None:
                last_seen = last_seen.replace(tzinfo=datetime.timezone.utc)
                
            diff = now - last_seen
            device_data.is_online = diff.total_seconds() < 300
        else:
            # Kein Zeitstempel gefunden -> offline
            device_data.is_online = False
    except Exception as e:
        logger.warning(f"Failed to enrich device status for '{db_device.display_name}': {e}")
        device_data.is_online = False
    
    return device_data

@router.get("/", response_model=List[Device])
async def read_devices(
    tenant_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user),
):
    """Retrieve devices for a tenant with live status."""
    if tenant_id:
        await deps.check_tenant_access(tenant_id, current_user, db)
        db_devices = await device_service.get_devices_by_tenant(db, tenant_id=tenant_id)
    else:
        # If no tenant_id provided, show all devices the user has access to
        if current_user.is_superuser:
            db_devices = await device_service.get_devices(db)
        else:
            # For normal users, get all their tenants first
            # We already have selectinload for tenant_links
            tenant_ids = [link.tenant_id for link in current_user.tenant_links]
            db_devices = []
            for tid in tenant_ids:
                tenant_devices = await device_service.get_devices_by_tenant(db, tenant_id=tid)
                db_devices.extend(tenant_devices)
    
    enriched = []
    for d in db_devices:
        enriched.append(await _enrich_device_status(d))
    return enriched

@router.post("/", response_model=Device)
async def create_device(
    *,
    db: AsyncSession = Depends(get_db),
    device_in: DeviceCreate,
    current_user: User = Depends(deps.get_current_user),
):
    """Create new device. (Platform admin only)"""
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Only platform admins can create devices")
    return await device_service.create_device(db, device_in=device_in)

@router.get("/{device_id}", response_model=Device)
async def read_device(
    device_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user),
):
    """Get device by ID with live status."""
    db_device = await device_service.get_device(db, device_id=device_id)
    if not db_device:
        raise HTTPException(status_code=404, detail="Device not found")
    await deps.check_tenant_access(db_device.tenant_id, current_user, db)
    return await _enrich_device_status(db_device)

@router.get("/{device_id}/token", response_model=DeviceWithToken)
async def read_device_with_token(
    device_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user),
):
    """Spezielle Abfrage des Geräts INKLUSIVE unmaskiertem Token (z.B. für HomeAssistant Setup)."""
    db_device = await device_service.get_device(db, device_id=device_id)
    if not db_device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    # Zugriff nur für platform_admin erlauben (Sicherheits-Check gemäß Fachregel)
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Only platform admins can view device tokens")
    
    return await _enrich_device_status(db_device, schema_type=DeviceWithToken)

@router.put("/{device_id}", response_model=Device)
async def update_device(
    *,
    db: AsyncSession = Depends(get_db),
    device_id: int,
    device_in: DeviceUpdate,
    current_user: User = Depends(deps.get_current_user),
):
    """Update a device. (Platform admin only)"""
    db_device = await device_service.get_device(db, device_id=device_id)
    if not db_device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Only platform admins can update devices")
        
    return await device_service.update_device(db, db_obj=db_device, device_in=device_in)

@router.delete("/{device_id}", status_code=204)
async def delete_device(
    device_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user),
):
    """Delete a device (nur Datensatz). Influx-Daten werden nicht automatisch gelöscht. (Platform admin only)"""
    db_device = await device_service.get_device(db, device_id=device_id)
    if not db_device:
        raise HTTPException(status_code=404, detail="Device not found")
        
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Only platform admins can delete devices")
        
    await device_service.delete_device(db, db_device)
    return None
