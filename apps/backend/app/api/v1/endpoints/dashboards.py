from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api import deps
from app.db.session import get_db
from app.models.dashboard import Dashboard as DashboardModel
from app.models.user import User
from app.schemas.dashboard import Dashboard, DashboardCreate, DashboardUpdate

from app.services import device as device_service

router = APIRouter()

@router.get("/{device_id}", response_model=Dashboard)
async def get_dashboard(
    device_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
) -> Any:
    """
    Abrufen der Dashboard-Konfiguration für ein Gerät und den aktuellen Benutzer.
    """
    # SICHERHEIT: Prüfen ob das Gerät existiert und der User Zugriff auf den Tenant des Geräts hat.
    db_device = await device_service.get_device(db, device_id=device_id)
    if not db_device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    await deps.check_tenant_access(db_device.tenant_id, current_user, db)

    result = await db.execute(
        select(DashboardModel).where(
            DashboardModel.user_id == current_user.id,
            DashboardModel.device_id == device_id
        )
    )
    dashboard = result.scalar_one_or_none()
    
    if not dashboard:
        # Falls noch kein Dashboard existiert, geben wir ein leeres Standard-Dashboard zurück
        # (Wird aber noch nicht in DB gespeichert)
        from datetime import datetime
        return Dashboard(
            id=0,
            user_id=current_user.id,
            device_id=device_id,
            name="Standard",
            config=[],
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
    
    return dashboard

@router.put("/{device_id}", response_model=Dashboard)
async def update_dashboard(
    device_id: int,
    dashboard_in: DashboardUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
) -> Any:
    """
    Speichern oder Aktualisieren der Dashboard-Konfiguration.
    """
    # SICHERHEIT: Prüfen ob das Gerät existiert und der User Zugriff auf den Tenant des Geräts hat.
    db_device = await device_service.get_device(db, device_id=device_id)
    if not db_device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    await deps.check_tenant_access(db_device.tenant_id, current_user, db)

    result = await db.execute(
        select(DashboardModel).where(
            DashboardModel.user_id == current_user.id,
            DashboardModel.device_id == device_id
        )
    )
    db_obj = result.scalar_one_or_none()
    
    if db_obj:
        # Update existierendes Dashboard
        update_data = dashboard_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_obj, field, value)
    else:
        # Neu anlegen
        db_obj = DashboardModel(
            user_id=current_user.id,
            device_id=device_id,
            name=dashboard_in.name,
            config=dashboard_in.config
        )
    
    db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)
    return db_obj
