import logging
from datetime import datetime, timedelta
from typing import Optional
from app.models.device import Device
from app.schemas.analysis import AnalysisRequest, AnalysisResponse, DeepAnalysisResponse
from app.services.heating_summary_service import heating_summary_service
from app.services.openai_service import openai_service

logger = logging.getLogger(__name__)

class DeviceAnalysisService:
    async def run_analysis(self, device: Device, request: AnalysisRequest) -> AnalysisResponse:
        """
        Orchestrates the device-based KI-analysis.
        """
        # Set default time range if not provided
        if not request.end:
            request.end = datetime.utcnow()
        if not request.start:
            request.start = request.end - timedelta(days=1)

        # 1. Prepare data summary
        summary_data = await heating_summary_service.get_device_summary(
            device=device,
            entity_ids=request.entity_ids,
            start=request.start,
            end=request.end
        )

        # 2. Call OpenAI
        analysis_result = await openai_service.analyze_heating_data(
            summary_data=summary_data,
            focus=request.analysis_focus,
            language=request.language
        )

        # 3. Create response object
        response = AnalysisResponse(
            device_id=device.id,
            device_name=device.display_name,
            start=request.start,
            end=request.end,
            summary=analysis_result.get("summary", "Keine Zusammenfassung verfügbar."),
            overall_status=analysis_result.get("overall_status", "unbekannt"),
            findings=analysis_result.get("findings", []),
            anomalies=analysis_result.get("anomalies", []),
            optimization_hints=analysis_result.get("optimization_hints", []),
            detected_error_codes=analysis_result.get("detected_error_codes", []),
            error_candidates=summary_data.get("error_candidates", []),
            recommended_followup_checks=analysis_result.get("recommended_followup_checks", []),
            confidence=analysis_result.get("confidence", "medium"),
            should_trigger_error_analysis=analysis_result.get("should_trigger_error_analysis", len(summary_data.get("error_candidates", [])) > 0),
            raw_summary=summary_data if request.include_raw_summary else None,
            analysis_run_id=summary_data.get("analysis_run_id")
        )

        return response

    async def run_deep_analysis(self, device: Device, request: AnalysisRequest) -> DeepAnalysisResponse:
        """
        Orchestrates a technical deep analysis for error diagnostics.
        """
        if not request.end:
            request.end = datetime.utcnow()
        if not request.start:
            request.start = request.end - timedelta(days=7) # Default to 7 days for deep analysis to find patterns

        # 1. Prepare data summary (focused on technical aspects)
        if not request.manufacturer or not request.heat_pump_type:
             raise ValueError("Hersteller und Wärmepumpentyp sind für die vertiefte Fehleranalyse erforderlich.")

        summary_data = await heating_summary_service.get_device_summary(
            device=device,
            entity_ids=request.entity_ids,
            start=request.start,
            end=request.end
        )

        # 2. Call OpenAI with Deep Analysis Prompt
        analysis_result = await openai_service.analyze_error_patterns(
            summary_data=summary_data,
            focus=request.analysis_focus or "Technische Fehlerdiagnose und Mustererkennung",
            language=request.language,
            manufacturer=request.manufacturer,
            heat_pump_type=request.heat_pump_type
        )

        # 3. Create response object
        response = DeepAnalysisResponse(
            device_id=device.id,
            device_name=device.display_name,
            start=request.start,
            end=request.end,
            technical_summary=analysis_result.get("technical_summary", "Keine technische Zusammenfassung verfügbar."),
            diagnostic_steps=analysis_result.get("diagnostic_steps", []),
            suspected_causes=analysis_result.get("suspected_causes", []),
            technical_findings=analysis_result.get("technical_findings", []),
            confidence=analysis_result.get("confidence", "medium")
        )

        return response

device_analysis_service = DeviceAnalysisService()
