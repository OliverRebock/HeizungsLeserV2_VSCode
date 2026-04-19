from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.db.session import get_db
from app.models.user import User
from app.schemas.analysis import AnalysisRequest, AnalysisResponse, DeepAnalysisResponse, HeatPumpChatRequest, HeatPumpChatResponse
from app.services import device as device_service
from app.services.device_analysis_service import device_analysis_service
from app.services.heatpump_chat_service import heatpump_chat_service

router = APIRouter()


@router.post("/{device_id}/chat", response_model=HeatPumpChatResponse)
async def chat_with_heatpump(
    device_id: int,
    request: HeatPumpChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Intent-gesteuerter Chat-Endpunkt fuer Waermepumpen:
    - erkennt die Frage-Absicht,
    - laedt nur relevante Influx-Daten,
    - nutzt OpenAI nur fuer Klassifikation/Interpretation.
    """
    db_device = await device_service.get_device(db, device_id=device_id)
    if not db_device:
        raise HTTPException(status_code=404, detail="Device not found")

    await deps.check_tenant_access(db_device.tenant_id, current_user, db)

    try:
        return await heatpump_chat_service.answer_question(db_device, request)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import logging

        logging.error(f"Error during heat pump chat: {e}")
        raise HTTPException(status_code=500, detail=f"Chat-Antwort fehlgeschlagen: {str(e)}")

@router.post("/{device_id}", response_model=AnalysisResponse)
async def create_device_analysis(
    device_id: int,
    request: AnalysisRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Triggers a device-based KI-analysis for a specific timeframe.
    """
    # 1. Fetch device and check access (RBAC & Multi-Tenancy)
    db_device = await device_service.get_device(db, device_id=device_id)
    if not db_device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    # This checks if current_user has access to the tenant of the device
    await deps.check_tenant_access(db_device.tenant_id, current_user, db)

    # 2. Run analysis
    try:
        analysis = await device_analysis_service.run_analysis(
            device=db_device,
            request=request
        )
        return analysis
    except ValueError as e:
        # e.g. OpenAI disabled
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import logging
        logging.error(f"Error during analysis: {e}")
        raise HTTPException(status_code=500, detail=f"KI-Analyse fehlgeschlagen: {str(e)}")


@router.post("/{device_id}/deep", response_model=DeepAnalysisResponse)
async def create_deep_analysis(
    device_id: int,
    request: AnalysisRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Triggers a technical deep analysis for error diagnostics.
    """
    # 1. Fetch device and check access
    db_device = await device_service.get_device(db, device_id=device_id)
    if not db_device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    await deps.check_tenant_access(db_device.tenant_id, current_user, db)

    # 2. Run deep analysis
    try:
        analysis = await device_analysis_service.run_deep_analysis(
            device=db_device,
            request=request
        )
        return analysis
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import logging
        logging.error(f"Error during deep analysis: {e}")
        raise HTTPException(status_code=500, detail=f"Vertiefte Analyse fehlgeschlagen: {str(e)}")
