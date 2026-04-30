import logging
import re
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta, timezone
import numpy as np
from app.models.device import Device
from app.services.influx import influx_service

logger = logging.getLogger(__name__)

class HeatingSummaryService:
    def _get_point_attr(self, point: Any, field: str) -> Any:
        if isinstance(point, dict):
            return point.get(field)
        return getattr(point, field, None)

    def _normalize_point_timestamp(self, raw_ts: Any) -> Optional[str]:
        if raw_ts is None:
            return None

        if isinstance(raw_ts, datetime):
            dt = raw_ts
        else:
            ts_str = str(raw_ts).strip()
            if not ts_str:
                return None
            if ts_str.endswith("Z"):
                ts_str = ts_str[:-1] + "+00:00"
            try:
                dt = datetime.fromisoformat(ts_str)
            except ValueError:
                return str(raw_ts)

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        return dt.isoformat()

    def _parse_point_ts(self, raw_ts: Any) -> Optional[datetime]:
        normalized = self._normalize_point_timestamp(raw_ts)
        if not normalized:
            return None
        try:
            dt = datetime.fromisoformat(normalized)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except Exception:
            return None

    def _point_numeric_state(self, point: Any) -> Optional[float]:
        state = self._get_point_attr(point, "state")
        if state not in (None, ""):
            s = str(state).strip().lower()
            if s in {
                "on", "true", "ein", "active", "running", "heizen", "warmwasser",
                "abtauen", "heating", "dhw", "defrost",
            }:
                return 1.0
            if s in {"off", "false", "aus", "idle", "inactive", "stopped"}:
                return 0.0
            try:
                return float(s)
            except Exception:
                pass

        value = self._get_point_attr(point, "value")
        if value is None:
            return None
        try:
            return float(str(value).replace(',', '.'))
        except Exception:
            return None

    def _detect_operating_status_category(self, entity_id: str, label: str, data_kind: str, domain: str) -> Optional[str]:
        text = f"{entity_id} {label}".lower()
        kind = (data_kind or "").lower()
        dom = (domain or "").lower()

        is_state_like = kind in {"binary", "enum", "string", "state"} or dom in {
            "binary_sensor", "switch", "lock", "input_boolean", "select", "input_select"
        }
        has_state_marker = any(marker in text for marker in ["status", "state", "mode", "zustand", "aktiv", "activity", "active", "betrieb"])

        # Priority flags (WW-Vorrang/Priority) are often control hints, not real activity state.
        if any(marker in text for marker in ["priority", "vorrang"]) and not has_state_marker:
            return None

        if not is_state_like and not has_state_marker:
            return None

        if any(marker in text for marker in ["compressor", "kompressor", "verdichter"]):
            return "compressor"
        if any(marker in text for marker in ["warmwasser", "dhw", "tapwater", "speicher", "ww"]):
            return "hot_water"
        if any(marker in text for marker in ["heating", "heizen", "heizbetrieb", "raumheizen"]):
            return "heating"
        if any(marker in text for marker in ["defrost", "abtau"]):
            return "defrost"

        return None

    def _collect_active_windows(self, points: List[Any]) -> List[Tuple[datetime, datetime, int]]:
        windows: List[Tuple[datetime, datetime, int]] = []
        start_ts: Optional[datetime] = None

        for point in points:
            ts = self._parse_point_ts(self._get_point_attr(point, "ts"))
            value = self._point_numeric_state(point)
            if ts is None or value is None:
                continue

            is_active = value >= 0.5
            if is_active and start_ts is None:
                start_ts = ts
            elif not is_active and start_ts is not None:
                duration_min = max(1, int((ts - start_ts).total_seconds() // 60))
                windows.append((start_ts, ts, duration_min))
                start_ts = None

        if start_ts is not None and points:
            end_ts = self._parse_point_ts(self._get_point_attr(points[-1], "ts"))
            if end_ts is not None and end_ts > start_ts:
                duration_min = max(1, int((end_ts - start_ts).total_seconds() // 60))
                windows.append((start_ts, end_ts, duration_min))

        return windows

    def _find_max_numeric_point(self, points: List[Any]) -> Optional[Tuple[datetime, float]]:
        best: Optional[Tuple[datetime, float]] = None
        for point in points:
            ts = self._parse_point_ts(self._get_point_attr(point, "ts"))
            value = self._point_numeric_state(point)
            if ts is None or value is None:
                continue
            if best is None or value > best[1]:
                best = (ts, value)
        return best

    def _timestamp_in_windows(self, ts: datetime, windows: List[Tuple[datetime, datetime, int]]) -> bool:
        return any(start <= ts <= end for start, end, _ in windows)

    def _nearest_window_relation(self, ts: datetime, windows: List[Tuple[datetime, datetime, int]]) -> Optional[str]:
        nearest: Optional[Tuple[float, str]] = None
        for start, end, _ in windows:
            if ts < start:
                delta_seconds = (start - ts).total_seconds()
                relation = f"{int(delta_seconds // 60)} min vor Start"
            elif ts > end:
                delta_seconds = (ts - end).total_seconds()
                relation = f"{int(delta_seconds // 60)} min nach Ende"
            else:
                continue

            if delta_seconds > 5 * 60:
                continue

            if nearest is None or delta_seconds < nearest[0]:
                nearest = (delta_seconds, relation)

        return nearest[1] if nearest else None

    def _aggregate_states(self, values: List[Any], options: Optional[Any] = None) -> Dict[str, Any]:
        from collections import Counter
        counts = Counter([str(v) for v in values])
        total = len(values)
        summary = {
            "states_seen": list(counts.keys()),
            "most_recent_state": str(values[-1]) if values else None,
            "most_frequent_state": counts.most_common(1)[0][0] if counts else None,
            "changes": self._count_changes(values),
            "count": total
        }
        if options:
            summary["options"] = options
        return summary

    def _normalize_entity_meta(self, raw_entity: Any) -> Optional[Dict[str, Any]]:
        """
        Normalize entity metadata from multiple shapes.
        Supports pydantic Entity objects, dict payloads and plain entity_id strings.
        """
        if raw_entity is None:
            return None

        if isinstance(raw_entity, str):
            eid = raw_entity.strip()
            if not eid:
                return None
            return {
                "entity_id": eid,
                "friendly_name": None,
                "domain": eid.split('.')[0] if '.' in eid else "sensor",
                "data_kind": "numeric",
                "unit_of_measurement": "",
                "options": None,
            }

        if isinstance(raw_entity, dict):
            eid = str(raw_entity.get("entity_id") or raw_entity.get("id") or "").strip()
            if not eid:
                return None
            return {
                "entity_id": eid,
                "friendly_name": raw_entity.get("friendly_name"),
                "domain": raw_entity.get("domain") or (eid.split('.')[0] if '.' in eid else "sensor"),
                "data_kind": raw_entity.get("data_kind") or "numeric",
                "unit_of_measurement": raw_entity.get("unit_of_measurement") or raw_entity.get("unit") or "",
                "options": raw_entity.get("options_str") if raw_entity.get("options_str") is not None else raw_entity.get("options"),
            }

        eid = str(getattr(raw_entity, "entity_id", "") or "").strip()
        if not eid:
            return None

        options = getattr(raw_entity, "options_str", None)
        if options is None:
            options = getattr(raw_entity, "options", None)

        return {
            "entity_id": eid,
            "friendly_name": getattr(raw_entity, "friendly_name", None),
            "domain": getattr(raw_entity, "domain", None) or (eid.split('.')[0] if '.' in eid else "sensor"),
            "data_kind": getattr(raw_entity, "data_kind", None) or "numeric",
            "unit_of_measurement": getattr(raw_entity, "unit_of_measurement", None) or "",
            "options": options,
        }

    def _extract_error_candidate(self, eid: str, label: str, points: List[Any]) -> Optional[Dict[str, Any]]:
        """
        Robust extraction of error codes from timeseries points.
        Patterns: (5140), E01, F1, 5140 in suspicious strings.
        Classification: active vs. historical based on indicators like '--' or 'last'.
        """
        candidate: Optional[Dict[str, Any]] = None

        for p in points:
            val = self._get_point_attr(p, "value")
            state = self._get_point_attr(p, "state")
            point_ts = self._normalize_point_timestamp(self._get_point_attr(p, "ts"))
            
            # Check both value and state as codes can hide in either
            targets = []
            if val is not None:
                targets.append(str(val))
            if state is not None:
                targets.append(str(state))
            targets = list(dict.fromkeys(targets))
            
            for val_str in targets:
                # 1. Look for technical codes in parentheses: (5140)
                paren_match = re.search(r'\((\d+)\)', val_str)
                # 2. Look for alphanumeric codes: E12, F101, A01
                alpha_match = re.search(r'([A-Z]\d{1,4})', val_str)
                # 3. Look for numeric sequences (3+ digits) in strings that aren't purely numeric
                numeric_match = re.search(r'(\d{3,})', val_str) if not re.match(r'^-?\d+(\.\d+)?$', val_str) else None
                
                code = None
                confidence = "medium"
                if paren_match:
                    code = paren_match.group(1)
                    confidence = "high"
                elif alpha_match:
                    code = alpha_match.group(1)
                    confidence = "high"
                elif numeric_match:
                    code = numeric_match.group(1)
                    confidence = "medium"
                
                # If we found a code OR the string explicitly mentions error/fault
                if code or any(kw in val_str.lower() for kw in ["fault", "alarm", "error", "störung", "störung"]):
                    classification = "active"
                    # Indicators for historical/previous errors
                    historical_indicators = ["--", "last", "historisch", "vorheriger", "previous", "history"]
                    if any(ind in val_str.lower() for ind in historical_indicators) or "last" in eid.lower():
                        classification = "historical"

                    parsed_code = code or val_str

                    if candidate is None:
                        candidate = {
                            "entity_id": eid,
                            "label": label,
                            "raw_value": val_str,
                            "parsed_code": parsed_code,
                            "classification": classification,
                            "confidence": confidence,
                            "first_seen_at": point_ts,
                            "last_seen_at": point_ts,
                            "seen_count": 1,
                        }
                        break

                    if str(candidate.get("parsed_code")) != str(parsed_code):
                        continue

                    candidate["seen_count"] = int(candidate.get("seen_count", 1) or 1) + 1
                    if point_ts:
                        if not candidate.get("first_seen_at"):
                            candidate["first_seen_at"] = point_ts
                        candidate["last_seen_at"] = point_ts
                    break

        return candidate

    def _is_in_time_window(self, dt: Optional[datetime], start: datetime, end: datetime) -> bool:
        if dt is None:
            return False
        return start <= dt <= end

    async def get_device_summary(
        self, 
        device: Device, 
        entity_ids: Optional[List[str]] = None,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        apply_timeframe_filter: bool = False,
    ) -> Dict[str, Any]:
        """
        Loads and aggregates data from InfluxDB 2 to provide a compact summary for the AI.
        """
        import uuid
        analysis_run_id = str(uuid.uuid4())
        
        # Default time range: last 24h
        if not end:
            end = datetime.now(timezone.utc)
        if not start:
            start = end - timedelta(days=1)

        logger.info(f"[{analysis_run_id}] Starting device summary for {device.display_name} (ID: {device.id}, {start} to {end})")
        
        # 1. Get entities if not provided
        if not entity_ids:
            logger.debug(f"No entity_ids provided, fetching all entities for device {device.id}")
            entities_raw = await influx_service.get_entities(device)
            entities = [meta for entity in entities_raw if (meta := self._normalize_entity_meta(entity))]
            # Filter for relevant ones
            entity_ids = [e["entity_id"] for e in entities]
        
        # Ensure error-related entities are always included
        all_device_entities_raw = await influx_service.get_entities(device)
        all_device_entities = [
            meta for entity in all_device_entities_raw if (meta := self._normalize_entity_meta(entity))
        ]
        error_keywords = ["error", "fault", "alarm", "code", "status", "warning", "störung", "meldung", "diagnostic"]
        error_entities = [
            e["entity_id"] for e in all_device_entities
            if any(
                kw in e["entity_id"].lower()
                or (e.get("friendly_name") and kw in str(e["friendly_name"]).lower())
                for kw in error_keywords
            )
        ]
        for eeid in error_entities:
            if eeid not in entity_ids:
                entity_ids.append(eeid)

        logger.info(f"Entities to process: {len(entity_ids)} (including {len(error_entities)} error-related)")

        # 2. Load timeseries data
        series_payload = await influx_service.get_timeseries(
            device, 
            entity_ids, 
            start.isoformat(), 
            end.isoformat()
        )

        # Backward-compatible handling: get_timeseries can return either a plain list
        # or a payload dict with the list under "series".
        if isinstance(series_payload, dict):
            series_data = series_payload.get("series", [])
        elif isinstance(series_payload, list):
            series_data = series_payload
        else:
            logger.warning(
                "Unexpected timeseries payload type for device %s: %s",
                device.id,
                type(series_payload).__name__,
            )
            series_data = []

        logger.info(f"Received data for {len(series_data)} entities from InfluxDB")

        # 3. Process and Aggregate
        summary = {
            "analysis_run_id": analysis_run_id,
            "device_id": device.id,
            "device_name": device.display_name,
            "period": {
                "start": start.isoformat(),
                "end": end.isoformat()
            },
            "entities": [],
            "error_candidates": [],
            "operating_context": {
                "status_windows": [],
                "temperature_peak_contexts": [],
            },
        }

        raw_series_context: List[Dict[str, Any]] = []

        # We need the full entity list for labels and options
        entities_metadata_raw = await influx_service.get_entities(device)
        entities_metadata = [meta for entity in entities_metadata_raw if (meta := self._normalize_entity_meta(entity))]
        entity_map = {e["entity_id"]: e for e in entities_metadata}

        for ts_response in series_data:
            if isinstance(ts_response, dict):
                eid = ts_response.get("entity_id")
                points = ts_response.get("points") or []
            else:
                eid = getattr(ts_response, "entity_id", None)
                points = getattr(ts_response, "points", None) or []

            if not eid:
                continue

            meta = entity_map.get(eid)
            
            label = meta["friendly_name"] if meta and meta.get("friendly_name") else eid
            domain = meta["domain"] if meta and meta.get("domain") else eid.split('.')[0]
            unit = meta["unit_of_measurement"] if meta else ""
            data_kind = meta["data_kind"] if meta else "numeric"
            options_str = meta.get("options") if meta else None

            if not points:
                continue

            raw_series_context.append(
                {
                    "entity_id": eid,
                    "label": label,
                    "domain": domain,
                    "data_kind": data_kind,
                    "unit": unit,
                    "points": points,
                }
            )

            # Check if this is truly numeric or just states
            # If we have any non-floatable values, it's a state entity
            raw_values = [self._get_point_attr(p, "value") for p in points if self._get_point_attr(p, "value") is not None]
            if not raw_values:
                continue

            entity_summary = {
                "entity_id": eid,
                "label": label,
                "domain": domain,
                "data_kind": data_kind,
                "unit": unit,
            }

            # 4. Deep Error Code Extraction & Candidate Identification
            filtered_points = points
            if apply_timeframe_filter:
                filtered_points = []
                for point in points:
                    point_dt = self._parse_point_ts(self._get_point_attr(point, "ts"))
                    if self._is_in_time_window(point_dt, start, end):
                        filtered_points.append(point)

            error_candidate = self._extract_error_candidate(eid, label, filtered_points)
            if error_candidate:
                summary["error_candidates"].append(error_candidate)
                logger.info(f"[{analysis_run_id}] Identified error candidate: {error_candidate['parsed_code']} in {eid} ({error_candidate['classification']})")

            # 5. Type-specific aggregation
            # Check if all values are numeric
            is_truly_numeric = True
            numeric_values = []
            for v in raw_values:
                try:
                    if v is None or v == "":
                        continue
                    # Clean strings that might be numbers (e.g. "21.5")
                    if isinstance(v, str):
                        v = v.replace(',', '.')
                    numeric_values.append(float(v))
                except (ValueError, TypeError):
                    is_truly_numeric = False
                    break

            # FORCED STATE DATA: If it's an operating mode, activity, or error-related, we WANT states
            # This prevents converting "Heizen"/"aus" or error strings to 0.0
            state_keywords = ["mode", "activity", "status", "state", "betrieb", "error", "fault", "alarm", "code"]
            is_forced_state = any(kw in eid.lower() or (label and kw in label.lower()) for kw in state_keywords)

            if data_kind == "numeric" and is_truly_numeric and not is_forced_state:
                entity_summary["summary"] = {
                    "min": round(min(numeric_values), 2),
                    "max": round(max(numeric_values), 2),
                    "avg": round(sum(numeric_values) / len(numeric_values), 2),
                    "count": len(numeric_values)
                }
                if len(numeric_values) > 10:
                    step = len(numeric_values) // 5
                    entity_summary["trend_sample"] = numeric_values[::step][:5]
            elif data_kind == "binary" and all(isinstance(v, (bool, int, float)) for v in raw_values):
                bool_values = [bool(v) for v in raw_values]
                true_count = sum(bool_values)
                entity_summary["summary"] = {
                    "active_ratio": round(true_count / len(bool_values), 2),
                    "changes": self._count_changes(bool_values),
                    "count": len(bool_values),
                    "most_recent_state": "on" if bool_values[-1] else "off"
                }
            else: # enum / string / forced_state fallback
                entity_summary["data_kind"] = "state"
                # Use points[].state if available and not empty, otherwise raw_values
                state_values = []
                for p in points:
                    point_state = self._get_point_attr(p, "state")
                    point_value = self._get_point_attr(p, "value")
                    if point_state and str(point_state).strip():
                        state_values.append(str(point_state))
                    elif point_value is not None:
                        state_values.append(str(point_value))
                
                entity_summary["summary"] = self._aggregate_states(state_values, options_str)

            summary["entities"].append(entity_summary)

        status_context: List[Dict[str, Any]] = []
        for item in raw_series_context:
            category = self._detect_operating_status_category(
                item["entity_id"], item["label"], item["data_kind"], item["domain"]
            )
            if not category:
                continue

            windows = self._collect_active_windows(item["points"])
            numeric_values = [self._point_numeric_state(point) for point in item["points"]]
            numeric_values = [value for value in numeric_values if value is not None]
            active_ratio = 0.0
            if numeric_values:
                active_ratio = round(sum(1 for value in numeric_values if value >= 0.5) / len(numeric_values), 2)

            status_context.append(
                {
                    "entity_id": item["entity_id"],
                    "label": item["label"],
                    "category": category,
                    "active_ratio": active_ratio,
                    "window_count": len(windows),
                    "recent_windows": [
                        {
                            "start": start.isoformat(),
                            "end": end.isoformat(),
                            "duration_min": duration,
                        }
                        for start, end, duration in windows[-3:]
                    ],
                    "_windows": windows,
                }
            )

        peak_contexts: List[Dict[str, Any]] = []
        for item in raw_series_context:
            text = f"{item['entity_id']} {item['label']}".lower()
            if not any(keyword in text for keyword in ["temperatur", "temperature", "vorlauf", "ruecklauf", "rücklauf", "tr1", "tc"]):
                continue

            max_point = self._find_max_numeric_point(item["points"])
            if not max_point:
                continue

            max_ts, max_value = max_point
            active_labels: List[str] = []
            nearby_labels: List[str] = []

            for status in status_context:
                windows = status.get("_windows", [])
                if self._timestamp_in_windows(max_ts, windows):
                    active_labels.append(status["label"])
                else:
                    relation = self._nearest_window_relation(max_ts, windows)
                    if relation:
                        nearby_labels.append(f"{status['label']} ({relation})")

            peak_contexts.append(
                {
                    "entity_id": item["entity_id"],
                    "label": item["label"],
                    "max_value": round(float(max_value), 2),
                    "unit": item["unit"],
                    "max_ts": max_ts.isoformat(),
                    "active_modes": active_labels[:3],
                    "nearby_modes": nearby_labels[:3],
                }
            )

        summary["operating_context"]["status_windows"] = [
            {
                key: value
                for key, value in status.items()
                if key != "_windows"
            }
            for status in status_context
        ]
        summary["operating_context"]["temperature_peak_contexts"] = peak_contexts[:8]

        # === NEW: HVAC-Fachmann-Metriken ===
        efficiency_metrics = self._calculate_efficiency_metrics(
            raw_series_context, status_context, start, end, analysis_run_id
        )
        summary["operating_context"]["efficiency_metrics"] = efficiency_metrics

        logger.info(f"[{analysis_run_id}] Summary generated with {len(summary['entities'])} entities and {len(summary['error_candidates'])} error candidates.")
        return summary

    def _calculate_efficiency_metrics(
        self, 
        raw_series_context: List[Dict[str, Any]], 
        status_context: List[Dict[str, Any]], 
        start: datetime, 
        end: datetime,
        run_id: str
    ) -> Dict[str, Any]:
        """
        Calculate HVAC-Technician-relevant metrics:
        - Spreizung (Supply-Return differential)
        - Average phase length
        - DHW ratio
        - Cycling frequency
        """
        metrics = {}
        
        # === 1. Spreizung (Supply vs Return temperature) ===
        supply_temps = []
        return_temps = []
        for item in raw_series_context:
            is_supply = any(kw in item["entity_id"].lower() or kw in item["label"].lower() 
                          for kw in ["vorlauf", "supply", "flow_temp", "tc1", "current_flow"])
            is_return = any(kw in item["entity_id"].lower() or kw in item["label"].lower() 
                          for kw in ["rücklauf", "return", "return_temp"])
            
            numeric_values = [self._point_numeric_state(p) for p in item["points"]]
            numeric_values = [v for v in numeric_values if v is not None and v > 0]
            
            if is_supply and numeric_values:
                supply_temps.extend(numeric_values)
            elif is_return and numeric_values:
                return_temps.extend(numeric_values)
        
        if supply_temps and return_temps:
            avg_supply = np.mean(supply_temps)
            avg_return = np.mean(return_temps)
            spreizung = round(avg_supply - avg_return, 2)
            metrics["spreizung_k"] = spreizung
            
            # Assess spreizung quality
            if spreizung < 3:
                metrics["spreizung_assessment"] = "Zu klein — möglicherweise zu hoher Volumenstrom"
            elif spreizung > 8:
                metrics["spreizung_assessment"] = "Gut für Wärmepumpe"
            else:
                metrics["spreizung_assessment"] = "Normal"
        
        # === 2. Durchschnittliche Phasenlänge & Start-Häufigkeit ===
        compressor_status = next(
            (s for s in status_context if "kompressor" in s["label"].lower() or "compressor" in s["entity_id"].lower()), 
            None
        )
        if compressor_status:
            windows = compressor_status.get("_windows", []) if "_windows" in compressor_status else []
            if windows:
                total_runtime_min = sum(duration for _, _, duration in windows)
                phase_count = len(windows)
                avg_phase_length_min = total_runtime_min / phase_count if phase_count > 0 else 0
                
                metrics["compressor_phase_count"] = phase_count
                metrics["compressor_avg_phase_length_min"] = round(avg_phase_length_min, 1)
                
                # Calculate days in period
                period_days = (end - start).days or 1
                starts_per_day = phase_count / period_days
                metrics["compressor_starts_per_day"] = round(starts_per_day, 2)
                
                # Assess cycling
                if starts_per_day > 8:
                    metrics["cycling_assessment"] = "Auffällig häufiges Takten"
                elif starts_per_day > 4:
                    metrics["cycling_assessment"] = "Erhöhte Taktung"
                else:
                    metrics["cycling_assessment"] = "Normal — wenig Takten"
        
        # === 3. DHW (WW) Anteil ===
        dhw_status = next(
            (s for s in status_context if any(kw in s["entity_id"].lower() or kw in s["label"].lower() 
                                              for kw in ["ww", "dhw", "warm", "tapwater", "hot_water"])),
            None
        )
        if dhw_status:
            dhw_ratio = dhw_status.get("active_ratio", 0)
            metrics["dhw_active_ratio"] = round(dhw_ratio * 100, 1)
            
            if dhw_ratio > 0.35:
                metrics["dhw_assessment"] = "Warmwasser nimmt viel Zeit ein — WW-Solltemperatur prüfen?"
            elif dhw_ratio > 0.15:
                metrics["dhw_assessment"] = "Warmwasser normal"
            else:
                metrics["dhw_assessment"] = "Wenig Warmwasser"
        
        # === 4. Compressor activity ratio ===
        if compressor_status:
            comp_ratio = compressor_status.get("active_ratio", 0)
            metrics["compressor_active_ratio"] = round(comp_ratio * 100, 1)
        
        logger.info(f"[{run_id}] Efficiency metrics calculated: {metrics}")
        return metrics
    
    def _count_changes(self, values: List[Any]) -> int:
        if not values:
            return 0
        changes = 0
        for i in range(1, len(values)):
            if values[i] != values[i-1]:
                changes += 1
        return changes

heating_summary_service = HeatingSummaryService()
