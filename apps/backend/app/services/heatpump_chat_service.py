import json
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx
import pytz

from app.core.config import settings
from app.core.heatpump_entity_mapping import (
    FRIENDLY_ENTITY_HINTS,
    get_intent_profile,
    get_manufacturer_aliases,
)
from app.models.device import Device
from app.schemas.analysis import ChatTurn, HeatPumpChatRequest, HeatPumpChatResponse
from app.schemas.influx import Entity, TimeSeriesResponse
from app.services.influx import influx_service

logger = logging.getLogger(__name__)

DOMAIN_CONTEXT = (
    "Ich bin ein Heizungsbauer und analysiere eine Waermepumpe. "
    "Alle relevanten Daten zur Analyse, Optimierung und Fehlerdiagnose liegen in einer InfluxDB. "
    "Fehlercodes sollen verstaendlich interpretiert werden und konkrete Handlungsempfehlungen enthalten."
)

EINSATZ_CHAT_SYSTEM_RULES = (
    "Du bist ein deutschsprachiger Analyse-Assistent fuer Heizungs- und Waermepumpendaten. "
    "Nutze ausschliesslich die bereitgestellten Messfakten aus InfluxDB-2-Auswertungen. "
    "Arbeitsprinzipien: nur InfluxDB 2, nur Flux, kein SQL, keine erfundenen Sensoren oder Fehlercodes, keine Halluzinationen. "
    "Wenn Datenbasis zu schwach ist, sage das klar und formuliere vorsichtig (z.B. 'ich sehe keinen Fehler', 'das spricht eher fuer ...', 'das laesst sich nicht sicher belegen'). "
    "Nenne keine Query-Details, ausser der Nutzer fragt explizit danach. "
    "Achte fachlich auf saubere Trennung von Stromverbrauch, Heizwaerme, Gesamtenergie, Teilzaehlern, Momentanleistung und Statussignalen. "
    "Bei COP/Effizienz nur logisch passende Zaehler nutzen; unplausible Ergebnisse als unsicher markieren und Zaehlerzuordnung hinterfragen. "
    "Bei Abschalt-/Aussetzungsfragen zwischen geregeltem Herunterfahren, harter Abschaltung, Schutzmodus und fehlender Waermeanforderung unterscheiden. "
    "Abtauvorgang nicht behaupten, wenn nicht eindeutig belegt. "
    "Wenn Zugriff auf InfluxDB-Host fehlschlaegt und Hinweise auf Mac-mini-von-Olli.local/mDNS vorliegen, benenne wahrscheinliches Hostname-/mDNS-Problem klar. "
    "Antwortstil fuer Endnutzer: kurz, direkt, verstaendlich, praxisnah, keine langen Vorreden."
)


class HeatPumpChatService:
    def __init__(self) -> None:
        self.api_key = settings.OPENAI_API_KEY
        self.model = settings.OPENAI_MODEL_PRIMARY
        self.timeout = settings.OPENAI_TIMEOUT_SECONDS
        self.openai_enabled = settings.OPENAI_ANALYSIS_ENABLED and bool(self.api_key)
        self.display_timezone_name = settings.CHAT_DISPLAY_TIMEZONE
        try:
            self.display_timezone = ZoneInfo(self.display_timezone_name)
        except ZoneInfoNotFoundError:
            try:
                self.display_timezone = pytz.timezone(self.display_timezone_name)
            except Exception:
                logger.warning("Unknown CHAT_DISPLAY_TIMEZONE '%s', falling back to UTC", self.display_timezone_name)
                self.display_timezone_name = "UTC"
                self.display_timezone = timezone.utc

    async def answer_question(self, device: Device, request: HeatPumpChatRequest) -> HeatPumpChatResponse:
        question = request.question.strip()
        if not question:
            raise ValueError("Bitte eine Frage eingeben.")

        resolved_question, forced_intent = self._resolve_follow_up_question(question, request.history)

        start_dt, end_dt = self._resolve_range(request.start, request.end)
        start_iso = start_dt.isoformat().replace("+00:00", "Z")
        end_iso = end_dt.isoformat().replace("+00:00", "Z")

        entities = await influx_service.get_entities(device)
        intent = forced_intent or await self._detect_intent(resolved_question)

        source_config = device.source_config or {}
        manufacturer = (device.manufacturer or source_config.get("manufacturer") or "").strip()
        heat_pump_type = (device.heat_pump_type or source_config.get("heat_pump_type") or "").strip()
        if heat_pump_type:
            logger.debug("Using heat pump type context for chat selection: %s", heat_pump_type)

        selected_entities = self._select_entities(intent, resolved_question, entities, manufacturer=manufacturer)

        # Fallback on broad operation intent, but still bounded entity count.
        if not selected_entities:
            selected_entities = self._fallback_entities(intent, entities)
            logger.debug("No intent match for entity selection; using bounded fallback list.")

        raw = await influx_service.get_timeseries(device, selected_entities, start_iso, end_iso)
        series: List[TimeSeriesResponse] = raw.get("series", [])

        facts = self._build_facts(intent, resolved_question, series, start_dt=start_dt, end_dt=end_dt)
        answer = await self._generate_answer(request, intent, facts, selected_entities, start_iso, end_iso, resolved_question)

        return HeatPumpChatResponse(
            intent=intent,
            answer=answer,
            used_entity_ids=selected_entities,
            evidence=facts,
            timeframe={
                "from": start_iso,
                "to": end_iso,
                "from_local": self._format_ts(start_dt),
                "to_local": self._format_ts(end_dt),
                "timezone": self.display_timezone_name,
            },
        )

    def _resolve_follow_up_question(self, question: str, history: List[ChatTurn]) -> tuple[str, Optional[str]]:
        """Resolve shorthand follow-ups like 'mach 2' against the last assistant recommendations."""
        lowered = question.strip().lower()
        match = re.match(r"^(?:mach|gib|zeige|nimm|tu)?\s*(?:punkt\s*)?(\d)\s*$", lowered)
        if not match:
            return question, None

        point = match.group(1)
        recommendation = self._extract_recommendation_from_history(history, point)
        if not recommendation:
            return question, None

        resolved = f"Fuehre Empfehlung Punkt {point} aus: {recommendation}."
        forced_intent: Optional[str] = None

        recommendation_lower = recommendation.lower()
        if point == "2" and any(
            marker in recommendation_lower
            for marker in [
                "ereignisprotokoll",
                "fehlerzeitpunkt",
                "11:45",
                "11:55",
                "trenddaten",
                "fehler",
            ]
        ):
            resolved += " Lies die Werte zum Zeitpunkt des Fehlers aus und bewerte den Verlauf rund um den Fehlerzeitpunkt."
            forced_intent = "anomaly"

        return resolved, forced_intent

    def _extract_recommendation_from_history(self, history: List[ChatTurn], point: str) -> Optional[str]:
        recommendation_pattern = re.compile(rf"^\s*{re.escape(point)}\.\s*(.+?)\s*$", re.IGNORECASE)

        for turn in reversed(history):
            if turn.role.lower() != "assistant":
                continue

            for line in turn.content.splitlines():
                match = recommendation_pattern.match(line)
                if not match:
                    continue

                candidate = match.group(1).strip()
                candidate = candidate.strip("-* ")
                candidate = candidate.replace("**", "")
                if candidate:
                    return candidate

        return None

    def _resolve_range(self, start: Optional[datetime], end: Optional[datetime]) -> tuple[datetime, datetime]:
        now = datetime.now(timezone.utc)
        if end is None:
            end = now
        elif end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)
        else:
            end = end.astimezone(timezone.utc)

        if start is None:
            start = end - timedelta(hours=24)
        elif start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        else:
            start = start.astimezone(timezone.utc)

        if start >= end:
            start = end - timedelta(hours=24)

        return start, end

    async def _detect_intent(self, question: str) -> str:
        # Fast path: deterministic keyword routing avoids an extra OpenAI call.
        lower = question.lower()
        if any(token in lower for token in ["fehler", "error", "fault", "alarm", "stoer", "stör", "warnung", "störung", "stoerung", "fehlercode"]):
            return "anomaly"
        if "takt" in lower or "haeufig" in lower or "häufig" in lower:
            return "cycling"
        if "durchfluss" in lower or "pc0" in lower or "pc1" in lower:
            return "flow"
        if "zuletzt" in lower and ("aus" in lower or "ausgegangen" in lower or "off" in lower):
            return "last_off"
        if any(token in lower for token in ["warmwasser", "dhw", "boiler", "aufgeheiz", "aufgewärmt", "aufgewaermt"]):
            return "hot_water"
        if "auffaellig" in lower or "auffällig" in lower:
            return "anomaly"
        if any(token in lower for token in ["health-check", "healthcheck", "systemcheck", "zustandscheck", "gesamtzustand", "health"]):
            return "health"
        if "normal" in lower or "ok" in lower:
            return "health"

        if not self.openai_enabled:
            return "general"

        system_prompt = (
            f"{DOMAIN_CONTEXT}\n"
            "Klassifiziere die Frage in genau eine Kategorie und antworte nur als JSON: "
            "{\"intent\":\"cycling|flow|last_off|hot_water|anomaly|health|general\"}."
        )
        user_prompt = f"Frage: {question}"

        try:
            payload = await self._openai_chat_json(system_prompt, user_prompt, temperature=0.0)
            intent = str(payload.get("intent", "general")).strip().lower()
            allowed = {"cycling", "flow", "last_off", "hot_water", "anomaly", "health", "general"}
            return intent if intent in allowed else "general"
        except Exception:
            logger.exception("Intent detection via OpenAI failed; using general intent fallback.")
            return "general"

    def _select_entities(
        self,
        intent: str,
        question: str,
        entities: List[Entity],
        manufacturer: Optional[str] = None,
    ) -> List[str]:
        profile = get_intent_profile(intent)
        manufacturer_aliases = get_manufacturer_aliases(manufacturer, intent)
        q = question.lower()
        question_is_error_focused = self._question_is_error_focused(q)
        question_is_time_focused = self._question_is_time_focused(q)
        question_is_hot_water_focused = self._question_is_hot_water_focused(q)
        question_requests_error_window = self._question_requests_error_window_readout(q)
        question_asks_for_duration = any(token in q for token in ["wie lange", "dauer", "lang ist", "länge"])
        question_asks_for_count = any(token in q for token in ["wie viele", "wie oft", "anzahl", "zahl"])
        question_tokens = [token.strip(".,!?;:\"'()[]{}") for token in q.split() if token.strip()]

        scored: List[tuple[int, str]] = []
        error_scored: List[tuple[int, str]] = []
        for entity in entities:
            text = f"{entity.entity_id} {entity.friendly_name or ''}".lower()
            score = 0
            for kw in profile.entity_keywords:
                if kw in text:
                    score += 3

            for alias in manufacturer_aliases:
                if alias in text:
                    score += 5

            for kw in profile.question_keywords:
                if kw in q and kw in text:
                    score += 4

            for token in question_tokens:
                if len(token) >= 3 and token in text:
                    score += 1

            if self._is_error_entity_text(text):
                if question_is_error_focused:
                    score += 8
                elif intent in {"anomaly", "health", "general"}:
                    score += 2
                if score > 0:
                    error_scored.append((score, entity.entity_id))

            if question_is_time_focused and question_is_hot_water_focused and self._is_dhw_timing_entity_text(text):
                score += 9

            if question_requests_error_window and self._is_fault_window_measurement_text(text):
                score += 8
            
            # For duration questions about heating, boost heating-related entities
            if question_is_time_focused and question_asks_for_duration and "geheizt" in q:
                heating_keywords = ["modulation", "compressor", "verdichter", "activity", "active", "heating", "heizung", "vorlauf", "sollwert", "selected"]
                if any(kw in text for kw in heating_keywords):
                    score += 7
            
            # For count questions, boost counter-related entities
            if question_asks_for_count and ("start" in q or "häufig" in q or "oft" in q):
                counter_keywords = ["start", "counter", "count", "laufzeit", "runtime", "stunden", "hours"]
                if any(kw in text for kw in counter_keywords):
                    score += 8
            
            # For behavior/comparison questions, boost paired/related entities
            if "verhalten" in q or "verlauf" in q or "entwicklung" in q or "vergleich" in q:
                # If question mentions vorlauf, boost rücklauf and vice versa
                if "vorlauf" in q and ("rücklauf" in text or "return" in text):
                    score += 6
                elif "rücklauf" in q and ("vorlauf" in text or "flow_temperature" in text):
                    score += 6
                # For general behavior questions, boost temperature sensors
                elif any(kw in text for kw in ["temperatur", "temperature", "vorlauf", "rücklauf", "return"]):
                    score += 4

            if score > 0:
                scored.append((score, entity.entity_id))

        scored.sort(key=lambda item: item[0], reverse=True)

        selected: List[str] = []
        seen: set[str] = set()

        # For behavior/comparison questions with temperature keywords, guarantee selection of all temperature entities
        question_is_comparison = any(kw in q for kw in ["verhalten", "verlauf", "entwicklung", "vergleich"])
        question_mentions_temps = any(kw in q for kw in ["vorlauf", "rücklauf", "return", "temperatur", "temperature"])
        
        if question_is_comparison and question_mentions_temps:
            # Ensure all temperature-related entities are included
            for entity in entities:
                text = f"{entity.entity_id} {entity.friendly_name or ''}".lower()
                if any(kw in text for kw in ["temperature", "temperatur", "vorlauf", "rücklauf", "return"]):
                    if entity.entity_id not in seen:
                        selected.append(entity.entity_id)
                        seen.add(entity.entity_id)

        # For fault/status-centric questions, guarantee inclusion of error-like entities.
        if question_is_error_focused or intent == "anomaly":
            error_scored.sort(key=lambda item: item[0], reverse=True)
            for _, entity_id in error_scored[:6]:
                if entity_id not in seen:
                    selected.append(entity_id)
                    seen.add(entity_id)

        if question_requests_error_window:
            for entity in entities:
                text = f"{entity.entity_id} {entity.friendly_name or ''}".lower()
                if self._is_fault_window_measurement_text(text) and entity.entity_id not in seen:
                    selected.append(entity.entity_id)
                    seen.add(entity.entity_id)
                if len(selected) >= max(profile.fallback_entity_limit, 18):
                    break

        for _, entity_id in scored:
            if entity_id in seen:
                continue
            selected.append(entity_id)
            seen.add(entity_id)
            # For duration questions, allow more entities to be selected
            if question_requests_error_window:
                limit = max(profile.fallback_entity_limit, 18)
            else:
                limit = 14 if (question_is_time_focused and question_asks_for_duration) else profile.fallback_entity_limit
            if len(selected) >= limit:
                break

        # For time-focused hot water questions, ensure timeline-critical entities are present.
        if question_is_time_focused and question_is_hot_water_focused:
            for entity in entities:
                if len(selected) >= max(profile.fallback_entity_limit, 14):
                    break
                text = f"{entity.entity_id} {entity.friendly_name or ''}".lower()
                if self._is_dhw_timing_entity_text(text) and entity.entity_id not in seen:
                    selected.append(entity.entity_id)
                    seen.add(entity.entity_id)

        logger.debug(
            "Selected %s entities for intent '%s' with manufacturer '%s'",
            len(selected),
            intent,
            manufacturer or "unknown",
        )
        return selected

    def _question_is_error_focused(self, question_lower: str) -> bool:
        return any(
            token in question_lower
            for token in [
                "fehler",
                "fehlercode",
                "error",
                "fault",
                "alarm",
                "stoer",
                "stör",
                "stoerung",
                "störung",
                "warnung",
                "sperr",
                "block",
                "trip",
            ]
        )

    def _is_error_entity_text(self, entity_text_lower: str) -> bool:
        return any(
            marker in entity_text_lower
            for marker in [
                "fehler",
                "error",
                "fault",
                "alarm",
                "warn",
                "code",
                "status",
                "state",
                "stoer",
                "stör",
                "sperr",
                "lock",
                "trip",
                "protect",
                "safety",
                "diagn",
            ]
        )

    def _question_is_time_focused(self, question_lower: str) -> bool:
        return any(
            token in question_lower
            for token in [
                "wann",
                "uhrzeit",
                "uhr",
                "zeitpunkt",
                "gestern",
                "heute",
                "vorgestern",
                "zwischen",
                "wie viele",
                "wie oft",
                "anzahl",
                "zahl",
                "häufig",
                "haeufig",
                "verhalten",
                "verlauf",
                "entwicklung",
                "vergleich",
                "im zeitraum",
                "während",
                "waehrend",
            ]
        )

    def _question_is_hot_water_focused(self, question_lower: str) -> bool:
        return any(
            token in question_lower
            for token in [
                "warmwasser",
                "wasser",
                "boiler",
                "dhw",
                "ww",
                "aufgeheiz",
                "aufgewärmt",
                "aufgewaermt",
            ]
        )

    def _is_dhw_timing_entity_text(self, entity_text_lower: str) -> bool:
        return any(
            marker in entity_text_lower
            for marker in [
                "tapwater_active",
                "dhw_current_intern_temperature",
                "dhw_energy_consumption_compressor",
                "dhw_starts",
                "dhw_energy",
                "dhw_priority",
                "warmwasser",
                "ww",
            ]
        )

    def _question_requests_error_window_readout(self, question_lower: str) -> bool:
        asks_for_values = any(token in question_lower for token in ["wert", "messwert", "ausles", "lies", "lese"])
        asks_for_error_time = any(
            token in question_lower
            for token in [
                "zeitpunkt des fehlers",
                "zeitpunkt vom fehler",
                "zu dem zeitpunkt",
                "zum zeitpunkt",
                "beim fehler",
                "rund um den fehler",
            ]
        )
        return self._question_is_error_focused(question_lower) and asks_for_values and asks_for_error_time

    def _is_fault_window_measurement_text(self, entity_text_lower: str) -> bool:
        measurement_markers = [
            "temperatur",
            "temperature",
            "vorlauf",
            "ruecklauf",
            "rücklauf",
            "flow",
            "durchfluss",
            "pressure",
            "druck",
            "setpoint",
            "soll",
            "target",
            "modulation",
            "leistung",
            "compressor",
            "verdichter",
            "pump",
            "pumpe",
            "valve",
            "ventil",
        ]
        return any(marker in entity_text_lower for marker in measurement_markers)

    def _fallback_entities(self, intent: str, entities: List[Entity]) -> List[str]:
        profile = get_intent_profile(intent)

        if intent == "anomaly":
            error_first = [
                e.entity_id
                for e in entities
                if self._is_error_entity_text(f"{e.entity_id} {e.friendly_name or ''}".lower())
            ]
            if error_first:
                return error_first[: profile.fallback_entity_limit]

        return [entity.entity_id for entity in entities[: profile.fallback_entity_limit]]

    def _resolve_display_name(self, series: TimeSeriesResponse) -> str:
        candidate = (series.friendly_name or "").strip()
        if candidate:
            return candidate

        lower_entity = series.entity_id.lower()
        for marker, label in FRIENDLY_ENTITY_HINTS.items():
            if marker in lower_entity:
                return label

        return series.entity_id

    def _series_latest_value(self, series: TimeSeriesResponse) -> Optional[str]:
        for point in reversed(series.points):
            if point.state not in (None, ""):
                return str(point.state)
            if point.value is not None:
                return str(round(float(point.value), 3))
        return None

    def _build_facts(
        self,
        intent: str,
        question: str,
        series: List[TimeSeriesResponse],
        start_dt: Optional[datetime] = None,
        end_dt: Optional[datetime] = None,
    ) -> List[str]:
        facts: List[str] = []
        if not series:
            return ["Keine passenden Messwerte im gewaehlten Zeitraum gefunden."]

        q = question.lower()
        question_is_time_focused = self._question_is_time_focused(q)
        question_is_hot_water_focused = self._question_is_hot_water_focused(q)
        question_requests_error_window = self._question_requests_error_window_readout(q)
        question_asks_for_duration = any(token in q for token in ["wie lange", "dauer", "lang ist", "länge"])
        question_asks_for_count = any(token in q for token in ["wie viele", "wie oft", "anzahl", "zahl"])
        include_period_summary = self._should_include_period_summary(
            intent=intent,
            question_is_time_focused=question_is_time_focused,
            question_requests_error_window=question_requests_error_window,
            start_dt=start_dt,
            end_dt=end_dt,
            series=series,
        )
        
        if question_requests_error_window:
            facts.extend(self._extract_fault_window_values(series)[:12])
        elif question_is_time_focused and question_is_hot_water_focused:
            facts.extend(self._extract_dhw_heating_events(series)[:8])
        elif question_is_time_focused and question_asks_for_duration:
            # For duration questions, extract operating phases
            facts.extend(self._extract_operating_phases(series)[:10])
        elif question_is_time_focused and question_asks_for_count:
            # For count questions, extract counter differences
            facts.extend(self._extract_counter_differences(series)[:10])
        elif question_is_time_focused:
            # For time-focused non-DHW questions, show time series statistics instead of just current values
            facts.extend(self._extract_time_series_summary(series)[:12])
        elif include_period_summary:
            # For broad windows (e.g. 7D/30D), provide period stats even for generic questions.
            facts.extend(self._extract_time_series_summary(series)[:10])

        # Always add current values as context
        for s in series:
            latest = self._series_latest_value(s)
            if latest is None:
                continue
            unit = s.unit_of_measurement or s.meta.get("unit_of_measurement") or ""
            suffix = f" {unit}" if unit else ""
            display_name = self._resolve_display_name(s)
            facts.append(f"{display_name} ({s.entity_id}) aktuell: {latest}{suffix}")

        if intent in {"last_off", "cycling", "health", "anomaly"}:
            transitions = self._extract_state_transitions(series)
            facts.extend(transitions[:5])

        return facts[:24]

    def _should_include_period_summary(
        self,
        intent: str,
        question_is_time_focused: bool,
        question_requests_error_window: bool,
        start_dt: Optional[datetime],
        end_dt: Optional[datetime],
        series: List[TimeSeriesResponse],
    ) -> bool:
        if question_is_time_focused or question_requests_error_window:
            return False

        if start_dt is None or end_dt is None or end_dt <= start_dt:
            return False

        # 6h+ indicates the user likely wants trend context, not only latest values.
        window_hours = (end_dt - start_dt).total_seconds() / 3600
        if window_hours < 6:
            return False

        if intent not in {"general", "health", "anomaly", "flow", "cycling", "hot_water"}:
            return False

        return any(
            len(s.points) >= 2 and any(point.value is not None for point in s.points)
            for s in series
        )

    def _extract_time_series_summary(self, series: List[TimeSeriesResponse]) -> List[str]:
        """Extract min/max/average statistics for time-focused questions."""
        summaries: List[str] = []

        for s in series:
            values = [point.value for point in s.points if point.value is not None]
            if not values:
                continue

            min_val = min(values)
            max_val = max(values)
            avg_val = sum(values) / len(values)
            unit = s.unit_of_measurement or s.meta.get("unit_of_measurement") or ""
            suffix = f" {unit}" if unit else ""
            display_name = self._resolve_display_name(s)

            # Determine how many active periods (non-zero values)
            active_count = sum(1 for v in values if v > 0.1)
            active_pct = int(100 * active_count / len(values)) if values else 0

            if min_val == max_val:
                # Constant value
                summaries.append(
                    f"{display_name} ({s.entity_id}) im Zeitraum konstant: {min_val:.1f}{suffix}"
                )
            else:
                summaries.append(
                    f"{display_name} ({s.entity_id}) im Zeitraum: Min {min_val:.1f}{suffix}, Durchschnitt {avg_val:.1f}{suffix}, Max {max_val:.1f}{suffix} (aktiv {active_pct}%)"
                )

        return summaries

    def _extract_fault_window_values(self, series: List[TimeSeriesResponse]) -> List[str]:
        anchor = self._find_fault_anchor(series)
        if anchor is None:
            return ["Kein Fehlerzeitpunkt im gewaehlten Zeitraum gefunden."]

        anchor_ts, error_label, error_code = anchor
        facts = [f"Fehlerzeitpunkt erkannt: {error_label} Code {error_code} um {self._format_ts(anchor_ts)}"]

        measurement_candidates: List[tuple[float, str]] = []
        tolerance_seconds = 5 * 60

        for candidate in series:
            entity_text = f"{candidate.entity_id} {candidate.friendly_name or ''}".lower()
            if self._is_error_entity_text(entity_text):
                continue

            nearest = self._find_nearest_point(candidate, anchor_ts)
            if nearest is None:
                continue

            point, point_ts = nearest
            delta_seconds = abs((point_ts - anchor_ts).total_seconds())
            if delta_seconds > tolerance_seconds:
                continue

            point_value = point.state
            if point.value is not None:
                point_value = f"{float(point.value):.1f}"
            if point_value in (None, ""):
                continue

            unit = candidate.unit_of_measurement or candidate.meta.get("unit_of_measurement") or ""
            suffix = f" {unit}" if unit else ""
            display_name = self._resolve_display_name(candidate)
            measurement_candidates.append(
                (
                    delta_seconds,
                    f"{display_name} ({candidate.entity_id}) beim Fehlerzeitpunkt: {point_value}{suffix} um {self._format_ts(point_ts)} ({self._format_time_offset(delta_seconds)})",
                )
            )

        measurement_candidates.sort(key=lambda item: (item[0], item[1]))
        facts.extend([fact for _, fact in measurement_candidates[:10]])

        if len(facts) == 1:
            facts.append("Keine Messwerte innerhalb von +/-5 Minuten rund um den Fehlerzeitpunkt gefunden.")

        return facts

    def _extract_operating_phases(self, series: List[TimeSeriesResponse]) -> List[str]:
        """Extract heating/cooling operating phases and their durations for duration questions."""
        phases: List[str] = []
        
        # Find heating-related entities (modulation, activity, etc.)
        heating_entities = [
            s for s in series
            if any(
                marker in s.entity_id.lower()
                for marker in [
                    "modulation",
                    "activity",
                    "active",
                    "compressor",
                    "verdichter",
                    "heizung",
                ]
            )
            and "cool" not in s.entity_id.lower()
        ]
        
        total_active_minutes = 0
        phase_count = 0
        
        for s in heating_entities:
            active_start: Optional[datetime] = None
            current_phase_minutes = 0
            
            for point in s.points:
                ts = self._parse_point_ts(point.ts)
                value = self._point_numeric_state(point)
                
                if ts is None or value is None:
                    continue
                
                is_active = value >= 0.1  # Threshold for "active"
                
                if is_active and active_start is None:
                    active_start = ts
                elif not is_active and active_start is not None:
                    duration = (ts - active_start).total_seconds() / 60
                    if duration >= 1:
                        current_phase_minutes += duration
                        phase_count += 1
                    active_start = None
            
            # Handle phase that extends to end of period
            if active_start is not None and s.points:
                end_ts = self._parse_point_ts(s.points[-1].ts)
                if end_ts is not None and end_ts > active_start:
                    duration = (end_ts - active_start).total_seconds() / 60
                    if duration >= 1:
                        current_phase_minutes += duration
                        phase_count += 1
            
            if current_phase_minutes > 0:
                display_name = self._resolve_display_name(s)
                hours = int(current_phase_minutes // 60)
                minutes = int(current_phase_minutes % 60)
                total_active_minutes += current_phase_minutes
                
                if hours == 0:
                    phases.append(
                        f"{display_name} ({s.entity_id}) war {minutes} Minuten aktiv"
                    )
                elif minutes == 0:
                    phases.append(
                        f"{display_name} ({s.entity_id}) war {hours} Stunden aktiv"
                    )
                else:
                    phases.append(
                        f"{display_name} ({s.entity_id}) war {hours} h {minutes} min aktiv"
                    )
        
        # Summary of total active time
        if total_active_minutes > 0:
            total_hours = int(total_active_minutes // 60)
            total_mins = int(total_active_minutes % 60)
            if total_hours == 0:
                phases.insert(
                    0,
                    f"Gesamte Heizzeitdauer im Zeitraum: {total_mins} Minuten ({phase_count} Phasen)"
                )
            elif total_mins == 0:
                phases.insert(
                    0,
                    f"Gesamte Heizzeitdauer im Zeitraum: {total_hours} Stunden ({phase_count} Phasen)"
                )
            else:
                phases.insert(
                    0,
                    f"Gesamte Heizzeitdauer im Zeitraum: {total_hours} h {total_mins} min ({phase_count} Phasen)"
                )
        
        return phases

    def _extract_counter_differences(self, series: List[TimeSeriesResponse]) -> List[str]:
        """Extract counter increments (starts, hours, etc.) between start and end of period."""
        diffs: List[str] = []
        
        counter_keywords = ["start", "counter", "laufzeit", "runtime", "stunden", "hours", "count"]
        
        for s in series:
            if not any(kw in s.entity_id.lower() for kw in counter_keywords):
                continue
            
            if not s.points or len(s.points) < 2:
                continue
            
            # Get first and last values
            first_val = s.points[0].value
            last_val = s.points[-1].value
            
            if first_val is None or last_val is None:
                continue
            
            diff = last_val - first_val
            if diff < 0:
                # Counter reset or negative value, skip
                continue
            
            if diff == 0:
                continue
            
            display_name = self._resolve_display_name(s)
            unit = s.unit_of_measurement or s.meta.get("unit_of_measurement") or ""
            suffix = f" {unit}" if unit else ""
            
            # Format based on value magnitude
            if diff >= 1:
                if diff == int(diff):
                    diffs.append(
                        f"{display_name} ({s.entity_id}) im Zeitraum: {int(diff)}{suffix} (Start: {first_val:.0f}, Ende: {last_val:.0f})"
                    )
                else:
                    diffs.append(
                        f"{display_name} ({s.entity_id}) im Zeitraum: {diff:.1f}{suffix} (Start: {first_val:.1f}, Ende: {last_val:.1f})"
                    )
        
        return diffs

    def _extract_state_transitions(self, series: List[TimeSeriesResponse]) -> List[str]:
        transitions: List[str] = []
        off_tokens = {"off", "0", "false", "idle", "aus"}

        for s in series:
            last_state: Optional[str] = None
            last_off_ts: Optional[str] = None
            for point in s.points:
                current = (point.state or (str(int(point.value)) if point.value is not None else "")).strip().lower()
                if not current:
                    continue
                if last_state is not None and current != last_state and current in off_tokens:
                    last_off_ts = self._format_point_ts(point.ts)
                last_state = current

            if last_off_ts:
                display_name = self._resolve_display_name(s)
                transitions.append(f"{display_name} ({s.entity_id}) zuletzt AUS um: {last_off_ts}")

        return transitions

    def _extract_dhw_heating_events(self, series: List[TimeSeriesResponse]) -> List[str]:
        facts: List[str] = []

        active_series = next(
            (
                s
                for s in series
                if "tapwater_active" in s.entity_id.lower() or "dhw_active" in s.entity_id.lower()
            ),
            None,
        )
        if active_series:
            facts.extend(self._extract_active_windows(active_series)[:6])

        starts_series = next(
            (
                s
                for s in series
                if "dhw_starts" in s.entity_id.lower() or "starts_hp" in s.entity_id.lower()
            ),
            None,
        )
        if starts_series:
            facts.extend(self._extract_counter_increments(starts_series)[:5])

        temp_series = next(
            (
                s
                for s in series
                if "dhw_current_intern_temperature" in s.entity_id.lower()
                or ("dhw" in s.entity_id.lower() and "temperature" in s.entity_id.lower())
            ),
            None,
        )
        if temp_series:
            facts.extend(self._extract_temperature_ramps(temp_series)[:4])

        return facts

    def _extract_active_windows(self, series: TimeSeriesResponse) -> List[str]:
        windows: List[str] = []
        start_ts: Optional[datetime] = None

        for point in series.points:
            ts = self._parse_point_ts(point.ts)
            state_value = self._point_numeric_state(point)
            if ts is None or state_value is None:
                continue

            is_active = state_value >= 0.5
            if is_active and start_ts is None:
                start_ts = ts
            if not is_active and start_ts is not None:
                duration_min = max(1, int((ts - start_ts).total_seconds() // 60))
                windows.append(
                    f"Warmwasser-Aufheizung erkannt ({series.entity_id}): Start {self._format_ts(start_ts)}, Ende {self._format_ts(ts)}, Dauer ca. {duration_min} min"
                )
                start_ts = None

        if start_ts is not None and series.points:
            end_ts = self._parse_point_ts(series.points[-1].ts)
            if end_ts is not None and end_ts > start_ts:
                duration_min = max(1, int((end_ts - start_ts).total_seconds() // 60))
                windows.append(
                    f"Warmwasser-Aufheizung laeuft/lief bis Messende ({series.entity_id}): Start {self._format_ts(start_ts)}, Ende {self._format_ts(end_ts)}, Dauer ca. {duration_min} min"
                )

        return windows

    def _extract_counter_increments(self, series: TimeSeriesResponse) -> List[str]:
        increments: List[str] = []
        previous: Optional[float] = None

        for point in series.points:
            if point.value is None:
                continue
            current = float(point.value)
            if previous is not None and current > previous:
                ts = self._parse_point_ts(point.ts)
                if ts is not None:
                    increments.append(
                        f"Warmwasser-Start gezaehlt ({series.entity_id}): +{int(round(current - previous))} um {self._format_ts(ts)}"
                    )
            previous = current

        return increments

    def _extract_temperature_ramps(self, series: TimeSeriesResponse) -> List[str]:
        ramps: List[str] = []
        points_with_values: List[tuple[datetime, float]] = []

        for point in series.points:
            if point.value is None:
                continue
            ts = self._parse_point_ts(point.ts)
            if ts is None:
                continue
            points_with_values.append((ts, float(point.value)))

        for idx in range(1, len(points_with_values)):
            prev_ts, prev_val = points_with_values[idx - 1]
            curr_ts, curr_val = points_with_values[idx]
            delta = curr_val - prev_val
            minutes = (curr_ts - prev_ts).total_seconds() / 60.0
            if delta >= 3.0 and 0 < minutes <= 240:
                ramps.append(
                    f"WW-Temperaturanstieg ({series.entity_id}): {prev_val:.1f} -> {curr_val:.1f} zwischen {self._format_ts(prev_ts)} und {self._format_ts(curr_ts)}"
                )

        return ramps

    def _find_fault_anchor(self, series: List[TimeSeriesResponse]) -> Optional[tuple[datetime, str, str]]:
        latest_anchor: Optional[tuple[datetime, str, str]] = None

        for candidate in series:
            entity_text = f"{candidate.entity_id} {candidate.friendly_name or ''}".lower()
            if not self._is_error_entity_text(entity_text):
                continue

            for point in candidate.points:
                raw_state = point.state if point.state not in (None, "") else point.value
                if raw_state in (None, ""):
                    continue

                raw_text = str(raw_state)
                parsed_code = self._extract_error_code(raw_text)
                if parsed_code is None and not self._question_is_error_focused(raw_text.lower()):
                    continue

                point_ts = self._parse_point_ts(point.ts)
                if point_ts is None:
                    continue

                embedded_error_ts = self._extract_error_timestamp_from_state(raw_text)
                anchor_ts = embedded_error_ts or point_ts

                display_name = self._resolve_display_name(candidate)
                anchor = (anchor_ts, display_name, parsed_code or raw_text)
                if latest_anchor is None or anchor_ts > latest_anchor[0]:
                    latest_anchor = anchor

        return latest_anchor

    def _extract_error_code(self, raw_text: str) -> Optional[str]:
        paren_match = re.search(r"\(([^)]+)\)", raw_text)
        if paren_match:
            return paren_match.group(1).strip()

        alpha_num_match = re.search(r"\b([A-Z]\d{1,4}|\d{3,5})\b", raw_text)
        if alpha_num_match:
            return alpha_num_match.group(1).strip()

        return None

    def _extract_error_timestamp_from_state(self, raw_text: str) -> Optional[datetime]:
        # Example formats inside error state strings:
        # "--(6256) 03.04.2026 11:50 - now"
        # "--(6256) 03.04.2026 11:51-03.04.2026 11:51"
        match = re.search(r"(\d{2}\.\d{2}\.\d{4})\s*(\d{2}:\d{2})", raw_text)
        if not match:
            return None

        dt_str = f"{match.group(1)} {match.group(2)}"
        try:
            local_naive = datetime.strptime(dt_str, "%d.%m.%Y %H:%M")
        except ValueError:
            return None

        try:
            if hasattr(self.display_timezone, "localize"):
                # pytz timezone
                localized = self.display_timezone.localize(local_naive)
            else:
                # zoneinfo timezone
                localized = local_naive.replace(tzinfo=self.display_timezone)
            return localized.astimezone(timezone.utc)
        except Exception:
            return None

    def _find_nearest_point(self, series: TimeSeriesResponse, anchor_ts: datetime) -> Optional[tuple[Any, datetime]]:
        nearest: Optional[tuple[Any, datetime]] = None
        nearest_delta: Optional[float] = None

        for point in series.points:
            point_ts = self._parse_point_ts(point.ts)
            if point_ts is None:
                continue
            delta = abs((point_ts - anchor_ts).total_seconds())
            if nearest is None or nearest_delta is None or delta < nearest_delta:
                nearest = (point, point_ts)
                nearest_delta = delta

        return nearest

    def _format_time_offset(self, delta_seconds: float) -> str:
        if delta_seconds < 1:
            return "Messpunkt exakt am Fehlerzeitpunkt"
        if delta_seconds < 60:
            return f"Abweichung {int(delta_seconds)} s"

        minutes = int(delta_seconds // 60)
        seconds = int(delta_seconds % 60)
        if seconds == 0:
            return f"Abweichung {minutes} min"
        return f"Abweichung {minutes} min {seconds} s"

    def _parse_point_ts(self, ts: str) -> Optional[datetime]:
        try:
            normalized = ts.replace("Z", "+00:00")
            return datetime.fromisoformat(normalized).astimezone(timezone.utc)
        except Exception:
            return None

    def _format_point_ts(self, ts: str) -> str:
        dt = self._parse_point_ts(ts)
        return self._format_ts(dt) if dt is not None else ts

    def _point_numeric_state(self, point: Any) -> Optional[float]:
        if point.value is not None:
            return float(point.value)
        if point.state is None:
            return None

        state = str(point.state).strip().lower()
        if state in {"on", "true", "ein", "active"}:
            return 1.0
        if state in {"off", "false", "aus", "idle", "inactive"}:
            return 0.0
        try:
            return float(state)
        except Exception:
            return None

    def _format_ts(self, dt: datetime) -> str:
        return dt.astimezone(self.display_timezone).strftime("%Y-%m-%d %H:%M %Z")

    async def _generate_answer(
        self,
        request: HeatPumpChatRequest,
        intent: str,
        facts: List[str],
        entity_ids: List[str],
        start_iso: str,
        end_iso: str,
        resolved_question: Optional[str] = None,
    ) -> str:
        prompt_question = resolved_question or request.question
        if not self.openai_enabled:
            return self._local_answer(prompt_question, intent, facts)

        history = "\n".join([f"{turn.role}: {turn.content}" for turn in request.history[-6:]])
        system_prompt = (
            f"{DOMAIN_CONTEXT}\n"
            f"{EINSATZ_CHAT_SYSTEM_RULES}\n"
            "Erwarte als Standarddatenquelle InfluxDB 2 mit Bucket ha_Input_rebock, Org heizungsleser, URL http://Mac-mini-von-Olli.local:8086. "
            "Wenn konkrete Fakten dem widersprechen, arbeite strikt mit den gelieferten Fakten weiter."
        )
        user_prompt = (
            f"Intent: {intent}\n"
            f"Zeitraum: {start_iso} bis {end_iso}\n"
            f"Verwendete Entitaeten: {', '.join(entity_ids)}\n"
            f"Bisheriger Verlauf:\n{history or 'kein Verlauf'}\n\n"
            f"Frage: {prompt_question}\n\n"
            "Relevante Messfakten:\n"
            + "\n".join([f"- {fact}" for fact in facts])
            + "\n\nAntworte in diesem Schema:\n"
              "1) Kurzes Fazit\n"
              "2) Wichtigste Beobachtungen (3-5 Stichpunkte)\n"
              "3) Falls noetig: Unsicherheit / Datenluecke\n"
              "4) Optional: naechster sinnvoller Pruefschritt."
        )

        try:
            return await self._openai_chat_text(system_prompt, user_prompt, temperature=0.2)
        except Exception:
            logger.exception("OpenAI answer generation failed, using local fallback.")
            return self._local_answer(prompt_question, intent, facts)

    def _local_answer(self, question: str, intent: str, facts: List[str]) -> str:
        observations = [f"- {fact}" for fact in facts[:5]]
        if not observations:
            observations = ["- Keine ausreichenden Messwerte im gewaehlten Zeitraum verfuegbar."]

        lines = [
            "Fazit: Auf Basis der vorliegenden Daten ist nur eine vorsichtige Einschaetzung moeglich.",
            "Wichtigste Beobachtungen:",
            *observations,
            "Unsicherheit / Datenluecke: Falls relevante Status-, Fehler- oder Leistungswerte fehlen, ist die Ursache nicht sicher belegbar.",
            "Naechster Pruefschritt: Zeitfenster rund um das Ereignis eingrenzen und Aktivstatus, Verdichterleistung, Vorlauf/Ruecklauf sowie Volumenstroeme gemeinsam pruefen.",
        ]
        return "\n".join(lines)

    async def _openai_chat_json(self, system_prompt: str, user_prompt: str, temperature: float = 0.0) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "response_format": {"type": "json_object"},
                    "temperature": temperature,
                },
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            return json.loads(content)

    async def _openai_chat_text(self, system_prompt: str, user_prompt: str, temperature: float = 0.2) -> str:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": temperature,
                },
            )
            response.raise_for_status()
            return str(response.json()["choices"][0]["message"]["content"]).strip()


heatpump_chat_service = HeatPumpChatService()
