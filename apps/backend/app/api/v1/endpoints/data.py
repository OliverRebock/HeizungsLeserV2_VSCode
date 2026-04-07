from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.api import deps
from app.db.session import get_db
from app.services import device as device_service
from app.services.influx import influx_service
from app.schemas.influx import Entity, DeviceDataResponse, TimeSeriesResponse
from app.models.user import User

router = APIRouter()

@router.get("/{device_id}/entities", response_model=List[Entity])
async def read_device_entities(
    device_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user),
):
    """List entities for a device by introspecting InfluxDB."""
    db_device = await device_service.get_device(db, device_id=device_id)
    if not db_device:
        raise HTTPException(status_code=404, detail="Device not found")
    await deps.check_tenant_access(db_device.tenant_id, current_user, db)
    
    return await influx_service.get_entities(db_device)

@router.get("/{device_id}/timeseries", response_model=DeviceDataResponse)
async def read_device_timeseries(
    device_id: int,
    entity_ids: List[str] = Query(...),
    start: Optional[str] = Query(None, description="ISO-8601 start time"),
    end: Optional[str] = Query(None, description="ISO-8601 end time"),
    range: Optional[str] = Query(None, description="Relative time range (e.g. '24h', 'today')"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user),
):
    """Get timeseries data for specific entities of a device."""
    db_device = await device_service.get_device(db, device_id=device_id)
    if not db_device:
        raise HTTPException(status_code=404, detail="Device not found")
    await deps.check_tenant_access(db_device.tenant_id, current_user, db)
    
    # Use 'range' as 'start' if provided, otherwise default to last 24h
    query_start = start
    if not query_start and range:
        # Pass the range string directly to influx_service.get_timeseries which handles it
        query_start = range
    
    # query_start and end are passed to influx_service.get_timeseries which handles defaults.
    # We do NOT force -1d here if range is provided.
    
    # FastAPI Query(List[str]) handles comma-separated values poorly if sent as a single string.
    # We ensure we have a clean list of individual entity IDs.
    clean_ids = []
    for eid in entity_ids:
        if "," in eid:
            clean_ids.extend([id.strip() for id in eid.split(",") if id.strip()])
        else:
            clean_ids.append(eid.strip())
    
    series = await influx_service.get_timeseries(db_device, clean_ids, query_start, end)
    
    return DeviceDataResponse(
        device_id=device_id,
        range={"from": query_start, "to": end},
        series=series
    )
