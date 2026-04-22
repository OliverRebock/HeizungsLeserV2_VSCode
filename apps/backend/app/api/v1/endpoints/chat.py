from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.db.session import get_db
from app.models.user import User
from app.schemas.analysis import DeviceChatHistoryResponse, DeviceChatRequest, DeviceChatResponse
from app.services import device as device_service
from app.services.device_chat_service import device_chat_service

router = APIRouter()


@router.post("/device/{device_id}", response_model=DeviceChatResponse)
async def chat_for_device(
    device_id: int,
    request: DeviceChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    db_device = await device_service.get_device(db, device_id=device_id)
    if not db_device:
        raise HTTPException(status_code=404, detail="Device not found")

    await deps.check_tenant_access(db_device.tenant_id, current_user, db)

    try:
        return await device_chat_service.ask(db_device, current_user.id, request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Chat fehlgeschlagen: {str(exc)}")


@router.get("/device/{device_id}/history", response_model=DeviceChatHistoryResponse)
async def get_device_chat_history(
    device_id: int,
    limit: int = Query(default=30, ge=1, le=120),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    db_device = await device_service.get_device(db, device_id=device_id)
    if not db_device:
        raise HTTPException(status_code=404, detail="Device not found")

    await deps.check_tenant_access(db_device.tenant_id, current_user, db)
    return device_chat_service.get_history(current_user.id, device_id, limit=limit)
