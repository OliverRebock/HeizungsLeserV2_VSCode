import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from app.models.device import Device
from app.schemas.analysis import AnalysisRequest, AnalysisResponse, DeepAnalysisResponse
from app.services.heating_summary_service import heating_summary_service
from app.services.local_analysis_service import local_analysis_service
from app.services.openai_service import openai_service

logger = logging.getLogger(__name__)

class DeviceAnalysisService:
    def _candidate_lookup_keys(self, candidate: Dict[str, Any]) -> List[Tuple[str, str]]:
        code = str(candidate.get("parsed_code") or "").strip().lower()
        entity_id = str(candidate.get("entity_id") or "").strip().lower()
        keys: List[Tuple[str, str]] = []
        if code and entity_id:
            keys.append((code, entity_id))
        if code:
            keys.append((code, ""))
        if entity_id:
            keys.append(("", entity_id))
        return keys

    def _enrich_detected_error_codes(
        self,
        detected_error_codes: List[Dict[str, Any]],
        error_candidates: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        if not detected_error_codes:
            return detected_error_codes

        candidate_index: Dict[Tuple[str, str], Dict[str, Any]] = {}
        for candidate in error_candidates:
            for key in self._candidate_lookup_keys(candidate):
                candidate_index.setdefault(key, candidate)

        enriched_codes: List[Dict[str, Any]] = []
        for detected in detected_error_codes:
            item = dict(detected)
            code = str(item.get("code") or "").strip().lower()
            entity_id = str(item.get("source_entity") or "").strip().lower()

            matched_candidate = (
                candidate_index.get((code, entity_id))
                or candidate_index.get((code, ""))
                or candidate_index.get(("", entity_id))
            )

            if matched_candidate:
                item.setdefault("observed_value", matched_candidate.get("raw_value"))
                item.setdefault("first_seen_at", matched_candidate.get("first_seen_at"))
                item.setdefault("last_seen_at", matched_candidate.get("last_seen_at"))
                item.setdefault("seen_count", int(matched_candidate.get("seen_count", 1) or 1))

            enriched_codes.append(item)

        return enriched_codes

    async def run_analysis(self, device: Device, request: AnalysisRequest) -> AnalysisResponse:
        """
        Orchestrates the device-based KI-analysis.
        """
        # Set default time range if not provided
        if not request.end:
            request.end = datetime.now(timezone.utc)
        if not request.start:
            request.start = request.end - timedelta(days=1)

        # 1. Prepare data summary
        summary_data = await heating_summary_service.get_device_summary(
            device=device,
            entity_ids=request.entity_ids,
            start=request.start,
            end=request.end
        )

        if not summary_data.get("entities"):
            raise ValueError("Im gewählten Zeitraum wurden keine auswertbaren Daten gefunden.")

        # 2. Prefer OpenAI, but keep the feature functional with a local fallback.
        analysis_mode = "ai"
        analysis_notice = None

        if openai_service.enabled:
            try:
                analysis_result = await openai_service.analyze_heating_data(
                    summary_data=summary_data,
                    focus=request.analysis_focus,
                    language=request.language
                )
            except Exception as exc:
                logger.warning(
                    "Falling back to local device analysis for device %s after OpenAI failure: %s",
                    device.id,
                    exc,
                )
                analysis_result = local_analysis_service.build_analysis(
                    summary_data=summary_data,
                    focus=request.analysis_focus,
                    fallback_reason=str(exc),
                )
                analysis_mode = "fallback"
                analysis_notice = analysis_result.get("analysis_notice")
        else:
            fallback_reason = "KI-Analyse ist deaktiviert oder kein OpenAI API-Key konfiguriert."
            logger.info(
                "Using local device analysis fallback for device %s because OpenAI is disabled.",
                device.id,
            )
            analysis_result = local_analysis_service.build_analysis(
                summary_data=summary_data,
                focus=request.analysis_focus,
                fallback_reason=fallback_reason,
            )
            analysis_mode = "fallback"
            analysis_notice = analysis_result.get("analysis_notice")

        # 3. Create response object
        detected_error_codes = self._enrich_detected_error_codes(
            analysis_result.get("detected_error_codes", []),
            summary_data.get("error_candidates", []),
        )

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
            detected_error_codes=detected_error_codes,
            error_candidates=summary_data.get("error_candidates", []),
            recommended_followup_checks=analysis_result.get("recommended_followup_checks", []),
            confidence=analysis_result.get("confidence", "medium"),
            should_trigger_error_analysis=analysis_result.get("should_trigger_error_analysis", len(summary_data.get("error_candidates", [])) > 0),
            analysis_mode=analysis_result.get("analysis_mode", analysis_mode),
            analysis_notice=analysis_result.get("analysis_notice", analysis_notice),
            raw_summary=summary_data if request.include_raw_summary else None,
            analysis_run_id=summary_data.get("analysis_run_id")
        )

        return response

    async def run_deep_analysis(self, device: Device, request: AnalysisRequest) -> DeepAnalysisResponse:
        """
        Orchestrates a technical deep analysis for error diagnostics.
        """
        if not request.end:
            request.end = datetime.now(timezone.utc)
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

        if not summary_data.get("entities"):
            raise ValueError("Im gewählten Zeitraum wurden keine auswertbaren Daten für die vertiefte Analyse gefunden.")

        # 2. Prefer OpenAI, but keep the deep analysis available with a local fallback.
        analysis_mode = "ai"
        analysis_notice = None

        if openai_service.enabled:
            try:
                analysis_result = await openai_service.analyze_error_patterns(
                    summary_data=summary_data,
                    focus=request.analysis_focus or "Technische Fehlerdiagnose und Mustererkennung",
                    language=request.language,
                    manufacturer=request.manufacturer,
                    heat_pump_type=request.heat_pump_type
                )
            except Exception as exc:
                logger.warning(
                    "Falling back to local deep analysis for device %s after OpenAI failure: %s",
                    device.id,
                    exc,
                )
                analysis_result = local_analysis_service.build_deep_analysis(
                    summary_data=summary_data,
                    manufacturer=request.manufacturer,
                    heat_pump_type=request.heat_pump_type,
                    fallback_reason=str(exc),
                )
                analysis_mode = "fallback"
                analysis_notice = analysis_result.get("analysis_notice")
        else:
            fallback_reason = "KI-Analyse ist deaktiviert oder kein OpenAI API-Key konfiguriert."
            logger.info(
                "Using local deep analysis fallback for device %s because OpenAI is disabled.",
                device.id,
            )
            analysis_result = local_analysis_service.build_deep_analysis(
                summary_data=summary_data,
                manufacturer=request.manufacturer,
                heat_pump_type=request.heat_pump_type,
                fallback_reason=fallback_reason,
            )
            analysis_mode = "fallback"
            analysis_notice = analysis_result.get("analysis_notice")

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
            confidence=analysis_result.get("confidence", "medium"),
            analysis_mode=analysis_result.get("analysis_mode", analysis_mode),
            analysis_notice=analysis_result.get("analysis_notice", analysis_notice),
        )

        return response

device_analysis_service = DeviceAnalysisService()
