import logging
import re
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import numpy as np
from app.models.device import Device
from app.services.influx import influx_service

logger = logging.getLogger(__name__)

class HeatingSummaryService:
    def _aggregate_states(self, values: List[Any], options: Optional[str] = None) -> Dict[str, Any]:
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

    def _extract_error_candidate(self, eid: str, label: str, points: List[Any]) -> Optional[Dict[str, Any]]:
        """
        Robust extraction of error codes from timeseries points.
        Patterns: (5140), E01, F1, 5140 in suspicious strings.
        Classification: active vs. historical based on indicators like '--' or 'last'.
        """
        for p in points:
            val = p.value
            state = p.state
            
            # Check both value and state as codes can hide in either
            targets = []
            if val is not None: targets.append(str(val))
            if state is not None: targets.append(str(state))
            
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
                    
                    return {
                        "entity_id": eid,
                        "label": label,
                        "raw_value": val_str,
                        "parsed_code": code or val_str,
                        "classification": classification,
                        "confidence": confidence
                    }
        return None

    async def get_device_summary(
        self, 
        device: Device, 
        entity_ids: Optional[List[str]] = None,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Loads and aggregates data from InfluxDB 2 to provide a compact summary for the AI.
        """
        import uuid
        analysis_run_id = str(uuid.uuid4())
        
        # Default time range: last 24h
        if not end:
            end = datetime.utcnow()
        if not start:
            start = end - timedelta(days=1)

        logger.info(f"[{analysis_run_id}] Starting device summary for {device.display_name} (ID: {device.id}, {start} to {end})")
        
        # 1. Get entities if not provided
        if not entity_ids:
            logger.debug(f"No entity_ids provided, fetching all entities for device {device.id}")
            entities = await influx_service.get_entities(device)
            # Filter for relevant ones
            entity_ids = [e.entity_id for e in entities]
        
        # Ensure error-related entities are always included
        all_device_entities = await influx_service.get_entities(device)
        error_keywords = ["error", "fault", "alarm", "code", "status", "warning", "störung", "meldung", "diagnostic"]
        error_entities = [
            e.entity_id for e in all_device_entities 
            if any(kw in e.entity_id.lower() or (e.friendly_name and kw in e.friendly_name.lower()) for kw in error_keywords)
        ]
        for eeid in error_entities:
            if eeid not in entity_ids:
                entity_ids.append(eeid)

        logger.info(f"Entities to process: {len(entity_ids)} (including {len(error_entities)} error-related)")

        # 2. Load timeseries data
        series_data = await influx_service.get_timeseries(
            device, 
            entity_ids, 
            start.isoformat(), 
            end.isoformat()
        )
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
            "error_candidates": []
        }

        # We need the full entity list for labels and options
        entities_metadata = await influx_service.get_entities(device)
        entity_map = {e.entity_id: e for e in entities_metadata}

        for ts_response in series_data:
            eid = ts_response.entity_id
            meta = entity_map.get(eid)
            
            label = meta.friendly_name if meta else eid
            domain = meta.domain if meta else eid.split('.')[0]
            unit = meta.unit_of_measurement if meta else ""
            data_kind = meta.data_kind if meta else "numeric"
            options_str = getattr(meta, 'options_str', None)

            points = ts_response.points
            if not points:
                continue

            # Check if this is truly numeric or just states
            # If we have any non-floatable values, it's a state entity
            raw_values = [p.value for p in points if p.value is not None]
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
            error_candidate = self._extract_error_candidate(eid, label, points)
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
                    if p.state and p.state.strip():
                        state_values.append(p.state)
                    elif p.value is not None:
                        state_values.append(str(p.value))
                
                entity_summary["summary"] = self._aggregate_states(state_values, options_str)

            summary["entities"].append(entity_summary)

        logger.info(f"[{analysis_run_id}] Summary generated with {len(summary['entities'])} entities and {len(summary['error_candidates'])} error candidates.")
        return summary

    def _count_changes(self, values: List[Any]) -> int:
        if not values:
            return 0
        changes = 0
        for i in range(1, len(values)):
            if values[i] != values[i-1]:
                changes += 1
        return changes

heating_summary_service = HeatingSummaryService()
