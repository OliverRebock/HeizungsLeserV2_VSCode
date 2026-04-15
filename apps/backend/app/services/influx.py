from influxdb_client import InfluxDBClient
from influxdb_client.domain.bucket_retention_rules import BucketRetentionRules
from influxdb_client.domain.bucket import Bucket
from influxdb_client.domain.permission import Permission
from influxdb_client.domain.permission_resource import PermissionResource
from influxdb_client.domain.authorization import Authorization
from app.core.config import settings
from app.models.device import Device
from app.schemas.influx import Entity, DataPoint, TimeSeriesResponse, DashboardEntityData, DashboardDataPoint
import json
import pytz
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

class InfluxService:
    def __init__(self, host: str, token: str, org: str):
        self.host = host
        self.token = token
        self.org = org
        self._client = None
        self._admin_token = settings.INFLUXDB_ADMIN_TOKEN

    @property
    def client(self):
        if not self._client:
            self._client = InfluxDBClient(
                url=self.host,
                token=self.token,
                org=self.org
            )
        return self._client

    async def create_database(self, db_name: str, retention: Optional[str] = None) -> Dict[str, Any]:
        """
        Erstellt einen InfluxDB 2 Bucket.
        """
        try:
            logger.info(f"INFLUX_SERVICE: Creating bucket '{db_name}' in org '{self.org}'")
            buckets_api = self.client.buckets_api()
            # Prüfen ob Bucket existiert
            try:
                existing = buckets_api.find_bucket_by_name(db_name)
                if existing:
                    logger.info(f"INFLUX_SERVICE: Bucket '{db_name}' already exists (ID: {existing.id})")
                    return {"status": "exists", "id": existing.id}
            except Exception as e:
                logger.debug(f"INFLUX_SERVICE: Bucket check error (safe to ignore): {e}")
            
            # Retention konfigurieren (für v2 API über PostBucketRequest oder Bucket Objekt)
            retention_rules = []
            if retention:
                if retention.endswith('d'):
                    seconds = int(retention[:-1]) * 24 * 3600
                    retention_rules.append(BucketRetentionRules(type="expire", every_seconds=seconds))

            # Organisation finden
            org_api = self.client.organizations_api()
            orgs = org_api.find_organizations(org=self.org)
            if not orgs:
                logger.error(f"INFLUX_SERVICE ERROR: Organization '{self.org}' not found!")
                return {"status": "error", "error": f"Organization {self.org} not found"}
            org_id = orgs[0].id
            logger.debug(f"INFLUX_SERVICE: Found Org ID {org_id}")

            # Bucket erstellen (In v2 nutzt man oft das Bucket Objekt direkt)
            bucket_obj = Bucket(name=db_name, org_id=org_id, retention_rules=retention_rules)
            
            bucket = buckets_api.create_bucket(bucket=bucket_obj)
            logger.info(f"INFLUX_SERVICE SUCCESS: Bucket '{db_name}' created with ID {bucket.id}")
            return {"status": "ok", "id": bucket.id}
        except Exception as e:
            logger.exception(f"INFLUX_SERVICE CRITICAL ERROR creating bucket {db_name}")
            return {"status": "error", "error": str(e)}

    async def create_service_token(self, bucket_name: str, description: str) -> Dict[str, Any]:
        """
        Erstellt einen Token mit Read/Write Berechtigungen für einen spezifischen Bucket.
        """
        try:
            logger.info(f"INFLUX_SERVICE: Generating token for bucket '{bucket_name}'")
            authorizations_api = self.client.authorizations_api()
            
            # Org ID finden
            org_api = self.client.organizations_api()
            orgs = org_api.find_organizations(org=self.org)
            if not orgs:
                return {"status": "error", "error": "Organization not found"}
            org_id = orgs[0].id
            
            # Bucket ID finden
            buckets_api = self.client.buckets_api()
            bucket = buckets_api.find_bucket_by_name(bucket_name)
            if not bucket:
                logger.error(f"INFLUX_SERVICE ERROR: Cannot generate token, bucket '{bucket_name}' not found!")
                return {"status": "error", "error": f"Bucket {bucket_name} not found"}
            
            # Berechtigungen definieren
            read_perm = Permission(action="read", resource=PermissionResource(type="buckets", id=bucket.id, org_id=org_id))
            write_perm = Permission(action="write", resource=PermissionResource(type="buckets", id=bucket.id, org_id=org_id))
            
            auth = Authorization(
                org_id=org_id,
                description=description,
                permissions=[read_perm, write_perm]
            )
            
            created_auth = authorizations_api.create_authorization(authorization=auth)
            logger.info(f"INFLUX_SERVICE SUCCESS: Token generated for bucket '{bucket_name}'")
            return {"status": "ok", "token": created_auth.token}
        except Exception as e:
            logger.exception(f"INFLUX_SERVICE CRITICAL ERROR creating token for {bucket_name}")
            return {"status": "error", "error": str(e)}

    async def get_last_data_timestamp(self, bucket: str) -> Optional[datetime]:
        """
        Ermittelt den Zeitstempel des absolut letzten Datenpunkts in einem Bucket.
        Prüft die letzten 24 Stunden für maximale Performance.
        """
        # DEBUG: logge den bucket-namen
        logger.debug(f"INFLUX_SERVICE: Getting last data timestamp for bucket: '{bucket}'")

        if bucket == "demo":
            # demo-Daten liegen in der Vergangenheit oder sind simuliert
            # hier ist kein fester timestamp nötig, falls der bucket leer ist.
            # wir geben nur dann now() zurück, wenn wirklich keine daten da sind und es 'demo' ist.
            # aber besser: wir entfernen diesen sonderfall, damit leere demo-geräte auch 'offline' sind.
            pass

        try:
            query_api = self.client.query_api()
            # Wir suchen in allen Measurements nach dem letzten Punkt.
            # Um "Schema Collision" Fehler (String vs Float in _value) zu vermeiden,
            # gruppieren wir nach Datentyp (_value column type) oder wir ignorieren _value komplett.
            # Da 'max()' auf _time auch ohne _value funktioniert wenn wir es vorher droppen.
            flux_query = f'''
                from(bucket: "{bucket}")
                |> range(start: -24h)
                |> filter(fn: (r) => r["_field"] == "value" or r["_field"] == "state")
                |> drop(columns: ["_value"])
                |> group()
                |> max(column: "_time")
            '''
            
            tables = query_api.query(query=flux_query)
            for table in tables:
                for record in table.records:
                    ts = record.get_time()
                    # InfluxDB gibt typischerweise aware UTC zurück, 
                    # aber falls das Plugin ein naive datetime liefert, hier absichern.
                    if ts and ts.tzinfo is None:
                        import datetime
                        ts = ts.replace(tzinfo=datetime.timezone.utc)
                    logger.debug(f"INFLUX_SERVICE: Found last timestamp for '{bucket}': {ts}")
                    return ts
            
            logger.debug(f"INFLUX_SERVICE: No data found for bucket '{bucket}' in the last 24h")
        except Exception as e:
            logger.warning(f"INFLUX_SERVICE: Error getting last seen for bucket {bucket}: {e}")
            
        return None

    def _clean_friendly_name(self, name: str) -> str:
        """
        Removes device prefixes like 'ems-esp', 'ebusd', etc. from the friendly name,
        similar to how Home Assistant does it in its UI.
        """
        if not name:
            return name
            
        prefixes_to_remove = [
            "ems-esp", "ebusd", "rpi", "homeassistant", "ha", 
            "zigbee2mqtt", "tasmota", "shelly", "esphome"
        ]
        
        cleaned_name = name.strip()
        lower_name = cleaned_name.lower()
        
        for prefix in prefixes_to_remove:
            if lower_name.startswith(prefix):
                # Remove prefix + potential separator like ": ", " - ", " " 
                start_index = len(prefix)
                # Check for common separators
                if len(cleaned_name) > start_index:
                    if cleaned_name[start_index] in [":", "-", " "]:
                        start_index += 1
                        # Check for another space after ":" or "-"
                        if len(cleaned_name) > start_index and cleaned_name[start_index] == " ":
                            start_index += 1
                
                cleaned_name = cleaned_name[start_index:].strip()
                # If name became empty or too short, revert to original (fallback)
                if not cleaned_name:
                    cleaned_name = name.strip()
                break
        
        # Capitalize first letter if it was lower-cased after prefix removal
        if cleaned_name and cleaned_name[0].islower():
            cleaned_name = cleaned_name[0].upper() + cleaned_name[1:]
            
        return cleaned_name

    def _get_value_semantics(
        self,
        domain: str,
        unit: Optional[str] = None,
        data_kind: Optional[str] = None,
        state_class: Optional[str] = None,
        device_class: Optional[str] = None,
    ) -> str:
        """
        Derives value semantics from generic metadata instead of entity-specific names.
        """
        lower_domain = (domain or "sensor").lower()
        lower_unit = (unit or "").strip().lower()
        normalized_state_class = (state_class or "").strip().lower()
        normalized_device_class = (device_class or "").strip().lower()

        if data_kind in {"binary", "enum", "string"}:
            return "stateful"

        if lower_domain in {"binary_sensor", "switch", "lock", "input_boolean"}:
            return "stateful"

        instant_device_classes = {
            "apparent_power",
            "current",
            "current_phase",
            "frequency",
            "power",
            "power_factor",
            "reactive_power",
            "signal_strength",
            "speed",
            "voltage",
            "volume_flow_rate",
            "wind_speed",
        }
        instant_units = {
            "a",
            "hz",
            "kw",
            "l/h",
            "m3/h",
            "ma",
            "mw",
            "rpm",
            "v",
            "va",
            "var",
            "w",
        }
        stateful_device_classes = {
            "aqi",
            "atmospheric_pressure",
            "battery",
            "carbon_dioxide",
            "carbon_monoxide",
            "distance",
            "duration",
            "energy",
            "energy_storage",
            "gas",
            "humidity",
            "illuminance",
            "irradiance",
            "moisture",
            "monetary",
            "nitrogen_dioxide",
            "nitrogen_monoxide",
            "nitrous_oxide",
            "ozone",
            "pm1",
            "pm10",
            "pm25",
            "precipitation",
            "precipitation_intensity",
            "pressure",
            "temperature",
            "volatile_organic_compounds",
            "volume",
            "volume_storage",
            "water",
            "weight",
        }
        stateful_units = {
            "%",
            "°c",
            "bar",
            "c",
            "kwh",
            "l",
            "m3",
            "psi",
            "wh",
        }

        if normalized_state_class in {"total", "total_increasing"}:
            return "stateful"

        if normalized_device_class in instant_device_classes:
            return "instant"

        if normalized_device_class in stateful_device_classes:
            return "stateful"

        if normalized_state_class == "measurement":
            if lower_unit in instant_units:
                return "instant"
            if lower_unit in stateful_units:
                return "stateful"
            return "instant"

        if lower_unit in instant_units:
            return "instant"

        if lower_unit in stateful_units:
            return "stateful"

        return "default"

    def _format_utc_timestamp(self, value: datetime) -> str:
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')

    def _parse_duration(self, value: str) -> Optional[timedelta]:
        if not value:
            return None

        normalized = value.strip().lower()
        if normalized.startswith('-'):
            normalized = normalized[1:]

        if len(normalized) < 2:
            return None

        try:
            amount = int(normalized[:-1])
        except ValueError:
            return None

        unit = normalized[-1]
        if unit == 's':
            return timedelta(seconds=amount)
        if unit == 'm':
            return timedelta(minutes=amount)
        if unit == 'h':
            return timedelta(hours=amount)
        if unit == 'd':
            return timedelta(days=amount)
        if unit == 'w':
            return timedelta(weeks=amount)
        return None

    def _resolve_time_range(
        self,
        start: Optional[str],
        end: Optional[str],
        tz_local: Any,
    ) -> Tuple[datetime, datetime]:
        now_utc = datetime.now(timezone.utc)
        now_local = now_utc.astimezone(tz_local)

        def parse_absolute(value: str) -> datetime:
            normalized = value.strip()
            parsed = datetime.fromisoformat(normalized.replace('Z', '+00:00'))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)

        end_dt = now_utc
        if end and end != "now()":
            duration = self._parse_duration(end)
            if duration is not None:
                end_dt = now_utc - duration
            else:
                end_dt = parse_absolute(end)

        if not start:
            start_dt = end_dt - timedelta(hours=24)
        elif start == 'today':
            start_dt = now_local.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)
        elif start == 'yesterday':
            yesterday_start = (now_local - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            start_dt = yesterday_start.astimezone(timezone.utc)
            if not end:
                end_dt = (yesterday_start + timedelta(days=1)).astimezone(timezone.utc)
        elif start == 'this_week':
            monday_start = (now_local - timedelta(days=now_local.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
            start_dt = monday_start.astimezone(timezone.utc)
        elif start == 'this_month':
            month_start = now_local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            start_dt = month_start.astimezone(timezone.utc)
        else:
            duration = self._parse_duration(start)
            if duration is not None:
                start_dt = end_dt - duration
            else:
                start_dt = parse_absolute(start)

        if end_dt <= start_dt:
            end_dt = start_dt + timedelta(seconds=1)

        return start_dt.astimezone(timezone.utc), end_dt.astimezone(timezone.utc)

    def _parse_numeric_value(self, raw_value: Any) -> Optional[float]:
        if raw_value is None:
            return None
        if isinstance(raw_value, bool):
            return 1.0 if raw_value else 0.0
        if isinstance(raw_value, (int, float)):
            return float(raw_value)
        if isinstance(raw_value, str):
            normalized = raw_value.strip()
            lowered = normalized.lower()
            if lowered in {'on', 'true', 'active', 'heating', 'an', 'open'}:
                return 1.0
            if lowered in {'off', 'false', 'inactive', 'idle', 'aus', 'closed'}:
                return 0.0
            try:
                return float(normalized.replace(',', '.'))
            except ValueError:
                return None
        return None

    def _stringify_state_value(self, raw_value: Any) -> Optional[str]:
        if raw_value is None:
            return None
        if isinstance(raw_value, bool):
            return 'on' if raw_value else 'off'
        return str(raw_value)

    def _is_strict_numeric_value(self, raw_value: Any) -> bool:
        if raw_value is None or isinstance(raw_value, bool):
            return False
        if isinstance(raw_value, (int, float)):
            return True
        if isinstance(raw_value, str):
            try:
                float(raw_value.strip().replace(',', '.'))
                return True
            except ValueError:
                return False
        return False

    def _is_binary_state_value(self, raw_value: Any) -> bool:
        if isinstance(raw_value, bool):
            return True
        if not isinstance(raw_value, str):
            return False
        return raw_value.strip().lower() in {
            'on', 'off', 'true', 'false', 'active', 'inactive', 'an', 'aus', 'open', 'closed'
        }

    def _build_sample_point(self, point_dt: datetime, raw_value: Any) -> Dict[str, Any]:
        if point_dt.tzinfo is None:
            point_dt = point_dt.replace(tzinfo=timezone.utc)
        point_dt = point_dt.astimezone(timezone.utc)
        return {
            'dt': point_dt,
            'raw_value': raw_value,
            'numeric_value': self._parse_numeric_value(raw_value),
            'state': self._stringify_state_value(raw_value),
            'strict_numeric': self._is_strict_numeric_value(raw_value),
            'binary_like': self._is_binary_state_value(raw_value),
        }

    def _parse_options(self, raw_options: Any) -> Optional[List[str]]:
        if raw_options is None:
            return None
        if isinstance(raw_options, list):
            return [str(item) for item in raw_options]

        text = str(raw_options).strip()
        if not text:
            return None

        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return [str(item) for item in parsed]
        except Exception:
            pass

        if ',' in text:
            items = [item.strip() for item in text.split(',') if item.strip()]
            return items or None

        return [text]

    def _is_monotonic_counter(self, samples: List[Dict[str, Any]]) -> bool:
        numeric_values = [sample['numeric_value'] for sample in samples if sample.get('strict_numeric') and sample.get('numeric_value') is not None]
        if len(numeric_values) < 3:
            return False

        if any(abs(value - round(value)) > 1e-9 for value in numeric_values):
            return False

        if not any(current > previous for previous, current in zip(numeric_values, numeric_values[1:])):
            return False

        return all(current >= previous for previous, current in zip(numeric_values, numeric_values[1:]))

    def _classify_data_kind(
        self,
        domain: str,
        state_class: Optional[str] = None,
        device_class: Optional[str] = None,
        unit_of_measurement: Optional[str] = None,
        options: Optional[List[str]] = None,
        samples: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        lower_domain = (domain or 'sensor').lower()
        normalized_state_class = (state_class or '').lower()
        normalized_device_class = (device_class or '').lower()
        samples = [sample for sample in (samples or []) if sample]

        domain_kind = self._get_data_kind(lower_domain)

        if domain_kind in {'binary', 'enum', 'string'}:
            return domain_kind

        if options:
            return 'enum'

        if normalized_state_class in {'measurement', 'total', 'total_increasing'}:
            return 'numeric'

        if normalized_device_class in {
            'apparent_power',
            'aqi',
            'atmospheric_pressure',
            'battery',
            'carbon_dioxide',
            'carbon_monoxide',
            'current',
            'data_rate',
            'distance',
            'duration',
            'energy',
            'energy_storage',
            'frequency',
            'gas',
            'humidity',
            'illuminance',
            'irradiance',
            'moisture',
            'monetary',
            'nitrogen_dioxide',
            'nitrogen_monoxide',
            'nitrous_oxide',
            'ozone',
            'pm1',
            'pm10',
            'pm25',
            'power',
            'power_factor',
            'precipitation',
            'precipitation_intensity',
            'pressure',
            'reactive_power',
            'signal_strength',
            'speed',
            'sulphur_dioxide',
            'temperature',
            'volatile_organic_compounds',
            'voltage',
            'volume',
            'volume_flow_rate',
            'volume_storage',
            'water',
            'weight',
            'wind_speed',
        }:
            return 'numeric'

        if unit_of_measurement:
            return 'numeric'

        if samples and all(sample.get('strict_numeric') for sample in samples):
            return 'numeric'

        if samples and all(sample.get('binary_like') for sample in samples):
            return 'binary'

        if samples and any(sample.get('state') for sample in samples):
            unique_states = {
                sample.get('state')
                for sample in samples
                if sample.get('state') not in {None, ''}
            }
            if unique_states and len(unique_states) <= 16:
                return 'enum'
            return 'string'

        return domain_kind

    def _get_render_mode(
        self,
        data_kind: str,
        state_class: Optional[str] = None,
        samples: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """
        Derives the render mode for frontend.
        - history_counter: For monotonic counters (Treppendarstellung).
        - history_line: For continuous values (Line chart).
        - state_timeline: For binary/enum/string states.
        """
        if data_kind in ("binary", "enum", "string"):
            return "state_timeline"

        normalized_state_class = (state_class or '').lower()
        if normalized_state_class in {"total", "total_increasing"}:
            return "history_counter"

        if normalized_state_class == "measurement":
            return "history_line"

        if self._is_monotonic_counter(samples or []):
            return "history_counter"

        return "history_line"

    def _derive_series_characteristics(
        self,
        domain: str,
        state_class: Optional[str] = None,
        device_class: Optional[str] = None,
        unit_of_measurement: Optional[str] = None,
        options: Optional[List[str]] = None,
        samples: Optional[List[Dict[str, Any]]] = None,
    ) -> Tuple[str, str, str]:
        data_kind = self._classify_data_kind(
            domain,
            state_class=state_class,
            device_class=device_class,
            unit_of_measurement=unit_of_measurement,
            options=options,
            samples=samples,
        )
        value_semantics = self._get_value_semantics(
            domain,
            unit_of_measurement,
            data_kind,
            state_class,
            device_class,
        )
        render_mode = self._get_render_mode(
            data_kind,
            state_class=state_class,
            samples=samples,
        )
        return data_kind, value_semantics, render_mode

    def _get_data_kind(self, domain: str) -> str:
        """
        Derives a generic base data kind from the domain only.
        """
        lower_domain = (domain or 'sensor').lower()

        if lower_domain in {"binary_sensor", "switch", "lock", "input_boolean"}:
            return "binary"

        if lower_domain in {"select", "input_select", "device_tracker", "person", "update"}:
            return "enum"

        if lower_domain in {"text", "input_text"}:
            return "string"

        if lower_domain in {"sensor", "number", "input_number"}:
            return "numeric"

        return "string"

    def _extract_record_value(self, record: Any) -> Any:
        raw_value = record.values.get("value")
        if raw_value is None:
            raw_value = record.values.get("state")
        return raw_value

    def _read_entity_metadata(
        self,
        query_api: Any,
        bucket: str,
        eid: str,
        end_dt: datetime,
    ) -> Dict[str, Any]:
        metadata: Dict[str, Any] = {}
        end_ts = self._format_utc_timestamp(end_dt)
        metadata_query = f'''
            from(bucket: "{bucket}")
            |> range(start: 0, stop: time(v: "{end_ts}"))
            |> filter(fn: (r) => r["_measurement"] == "{eid}" or r["entity_id"] == "{eid}")
            |> filter(fn: (r) =>
                r["_field"] == "friendly_name_str" or
                r["_field"] == "unit_of_measurement_str" or
                r["_field"] == "state_class_str" or
                r["_field"] == "device_class_str" or
                r["_field"] == "options_str"
            )
            |> last()
            |> pivot(rowKey:["_measurement"], columnKey: ["_field"], valueColumn: "_value")
        '''

        try:
            tables = query_api.query(query=metadata_query)
            for table in tables:
                for record in table.records:
                    values = record.values
                    if values.get("friendly_name_str"):
                        metadata["friendly_name"] = self._clean_friendly_name(str(values.get("friendly_name_str")))
                    if values.get("unit_of_measurement_str"):
                        metadata["unit_of_measurement"] = str(values.get("unit_of_measurement_str"))
                    if values.get("state_class_str"):
                        metadata["state_class"] = str(values.get("state_class_str"))
                    if values.get("device_class_str"):
                        metadata["device_class"] = str(values.get("device_class_str"))
                    if values.get("options_str"):
                        metadata["options"] = self._parse_options(values.get("options_str"))
                    if values.get("domain"):
                        metadata["domain"] = str(values.get("domain"))
        except Exception as exc:
            logger.debug(f"Metadata query failed for {eid}: {exc}")

        return metadata

    def _read_last_sample_before(
        self,
        query_api: Any,
        bucket: str,
        eid: str,
        start_dt: datetime,
    ) -> Optional[Dict[str, Any]]:
        start_ts = self._format_utc_timestamp(start_dt)
        last_query = f'''
            from(bucket: "{bucket}")
            |> range(start: 0, stop: time(v: "{start_ts}"))
            |> filter(fn: (r) => r["_measurement"] == "{eid}" or r["entity_id"] == "{eid}")
            |> filter(fn: (r) => r["_field"] == "value" or r["_field"] == "state")
            |> last()
            |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
        '''

        try:
            tables = query_api.query(query=last_query)
            for table in tables:
                for record in table.records:
                    raw_value = self._extract_record_value(record)
                    if raw_value is None:
                        continue
                    return self._build_sample_point(record.get_time(), raw_value)
        except Exception as exc:
            logger.debug(f"Last sample query failed for {eid}: {exc}")

        return None

    def _read_samples_in_range(
        self,
        query_api: Any,
        bucket: str,
        eid: str,
        start_dt: datetime,
        end_dt: datetime,
    ) -> List[Dict[str, Any]]:
        start_ts = self._format_utc_timestamp(start_dt)
        end_ts = self._format_utc_timestamp(end_dt)
        flux_query = f'''
            from(bucket: "{bucket}")
            |> range(start: time(v: "{start_ts}"), stop: time(v: "{end_ts}"))
            |> filter(fn: (r) => r["_measurement"] == "{eid}" or r["entity_id"] == "{eid}")
            |> filter(fn: (r) => r["_field"] == "value" or r["_field"] == "state")
            |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
        '''

        samples: List[Dict[str, Any]] = []
        try:
            tables = query_api.query(query=flux_query)
            for table in tables:
                for record in table.records:
                    raw_value = self._extract_record_value(record)
                    if raw_value is None:
                        continue
                    samples.append(self._build_sample_point(record.get_time(), raw_value))
        except Exception as exc:
            logger.warning(f"Query failed for {eid}: {exc}")

        samples.sort(key=lambda sample: sample['dt'])
        return samples

    def _append_history_point(
        self,
        points: List[DataPoint],
        point_dt: datetime,
        value: Optional[float],
        state: Optional[str],
        is_actual: bool = True,
    ) -> None:
        if value is None and state is None:
            return

        point = DataPoint(
            ts=self._format_utc_timestamp(point_dt),
            value=value,
            state=state,
            is_actual=is_actual,
        )

        if points and points[-1].ts == point.ts:
            if point.is_actual or not points[-1].is_actual:
                points[-1] = point
            return

        points.append(point)

    def _build_history_counter_points(
        self,
        start_dt: datetime,
        end_dt: datetime,
        previous_sample: Optional[Dict[str, Any]],
        actual_samples: List[Dict[str, Any]],
    ) -> List[DataPoint]:
        points: List[DataPoint] = []

        if previous_sample and previous_sample.get('numeric_value') is not None:
            if not actual_samples or actual_samples[0]['dt'] > start_dt:
                self._append_history_point(
                    points,
                    start_dt,
                    previous_sample['numeric_value'],
                    previous_sample.get('state'),
                    is_actual=False,
                )

        for sample in actual_samples:
            if sample.get('numeric_value') is None:
                continue
            self._append_history_point(
                points,
                sample['dt'],
                sample['numeric_value'],
                sample.get('state'),
                is_actual=True,
            )

        if not points and previous_sample and previous_sample.get('numeric_value') is not None:
            self._append_history_point(
                points,
                start_dt,
                previous_sample['numeric_value'],
                previous_sample.get('state'),
                is_actual=False,
            )

        if points and points[-1].value is not None:
            self._append_history_point(
                points,
                end_dt,
                points[-1].value,
                points[-1].state,
                is_actual=False,
            )

        return points

    def _build_history_line_points(
        self,
        start_dt: datetime,
        end_dt: datetime,
        previous_sample: Optional[Dict[str, Any]],
        actual_samples: List[Dict[str, Any]],
    ) -> List[DataPoint]:
        points: List[DataPoint] = []

        if previous_sample and previous_sample.get('numeric_value') is not None:
            if not actual_samples or actual_samples[0]['dt'] > start_dt:
                self._append_history_point(
                    points,
                    start_dt,
                    previous_sample['numeric_value'],
                    previous_sample.get('state'),
                    is_actual=False,
                )

        for sample in actual_samples:
            if sample.get('numeric_value') is None:
                continue
            self._append_history_point(
                points,
                sample['dt'],
                sample['numeric_value'],
                sample.get('state'),
                is_actual=True,
            )

        if not points and previous_sample and previous_sample.get('numeric_value') is not None:
            self._append_history_point(
                points,
                start_dt,
                previous_sample['numeric_value'],
                previous_sample.get('state'),
                is_actual=False,
            )

        if points and points[-1].value is not None:
            self._append_history_point(
                points,
                end_dt,
                points[-1].value,
                points[-1].state,
                is_actual=False,
            )

        return points

    def _build_state_timeline_points(
        self,
        start_dt: datetime,
        end_dt: datetime,
        previous_sample: Optional[Dict[str, Any]],
        actual_samples: List[Dict[str, Any]],
    ) -> List[DataPoint]:
        points: List[DataPoint] = []

        if previous_sample:
            if not actual_samples or actual_samples[0]['dt'] > start_dt:
                self._append_history_point(
                    points,
                    start_dt,
                    previous_sample.get('numeric_value'),
                    previous_sample.get('state'),
                    is_actual=False,
                )

        for sample in actual_samples:
            self._append_history_point(
                points,
                sample['dt'],
                sample.get('numeric_value'),
                sample.get('state'),
                is_actual=True,
            )

        if not points and previous_sample:
            self._append_history_point(
                points,
                start_dt,
                previous_sample.get('numeric_value'),
                previous_sample.get('state'),
                is_actual=False,
            )

        if points:
            self._append_history_point(
                points,
                end_dt,
                points[-1].value,
                points[-1].state,
                is_actual=False,
            )

        return points

    async def get_entities(self, device: Device) -> List[Entity]:
        """
        Dynamically introspect InfluxDB 2 to find all entities and their metadata.
        Prioritizes friendly names from 'friendly_name_str' tag if available and cleans them.
        """
        bucket = device.influx_database_name or settings.INFLUXDB_BUCKET
        
        if bucket == "demo":
            return self._get_demo_entities()

        try:
            query_api = self.client.query_api()
            seen_ids = set()
            entities = []
            
            # Strategie 1: Wir holen alle eindeutigen entity_id Tags im Bucket ÜBERHAUPT.
            # Das ist der sicherste Weg, um wirklich ALLES zu finden, unabhängig von Zeitfiltern.
            all_entities_query = f'''
                import "influxdata/influxdb/schema"
                schema.tagValues(bucket: "{bucket}", tag: "entity_id")
            '''
            
            try:
                tag_tables = query_api.query(query=all_entities_query)
                for table in tag_tables:
                    for record in table.records:
                        eid = record.get_value()
                        if not eid or eid in seen_ids:
                            continue
                        
                        seen_ids.add(eid)
                        
                        # Basis-Entität hinzufügen
                        domain = eid.split('.')[0] if '.' in eid else "sensor"
                        data_kind = self._get_data_kind(domain)
                        render_mode = self._get_render_mode(data_kind)
                        entities.append(Entity(
                            entity_id=eid,
                            domain=domain,
                            friendly_name=eid.split('.')[-1].replace('_', ' ').title(),
                            data_kind=data_kind,
                            value_semantics=self._get_value_semantics(domain, data_kind=data_kind),
                            render_mode=render_mode,
                            chartable=True,
                            source_table="multiple"
                        ))
            except Exception as e:
                logger.debug(f"Primary entity discovery (tagValues) failed: {e}")

            # Strategie 2: Metadaten und Live-Werte Update für die gefundenen Entitäten (letzte 30 Tage)
            # Wir holen friendly_name_str, unit_of_measurement_str UND den eigentlichen Wert (value oder _value).
            metadata_query = f'''
                from(bucket: "{bucket}")
                |> range(start: -30d)
                |> filter(fn: (r) => r["_field"] == "friendly_name_str" or 
                                     r["_field"] == "unit_of_measurement_str" or 
                                     r["_field"] == "state_class_str" or
                                     r["_field"] == "device_class_str" or
                                     r["_field"] == "options_str" or
                                     r["_field"] == "value" or 
                                     r["_field"] == "state" or
                                     r["_field"] == "_value")
                |> last()
                |> pivot(rowKey:["entity_id"], columnKey: ["_field"], valueColumn: "_value")
            '''
            
            try:
                meta_tables = query_api.query(query=metadata_query)
                meta_map = {}
                for table in meta_tables:
                    for record in table.records:
                        row = record.values
                        eid = row.get("entity_id")
                        if eid:
                            meta_map[eid] = row
                
                # Metadaten und Live-Werte in die Entitäten-Liste einarbeiten
                for ent in entities:
                    m = meta_map.get(ent.entity_id)
                    if m:
                        state_class = str(m.get("state_class_str")) if m.get("state_class_str") else None
                        device_class = str(m.get("device_class_str")) if m.get("device_class_str") else None
                        options = self._parse_options(m.get("options_str"))

                        # Friendly Name
                        f_name = m.get("friendly_name_str")
                        if f_name:
                            ent.friendly_name = self._clean_friendly_name(str(f_name))
                        
                        # Unit
                        unit = m.get("unit_of_measurement_str")
                        if not unit:
                            # Fallback: In manchen Setups ist die Einheit im _measurement Tag
                            unit = m.get("_measurement")
                        
                        if unit and unit != "multiple": # "multiple" ist ein Influx-Artefakt beim Pivot
                            ent.unit_of_measurement = str(unit)

                        ent.state_class = state_class
                        ent.device_class = device_class
                        ent.options = options
                        
                        # Domain Update
                        if m.get("domain"):
                            ent.domain = m.get("domain")
                        
                        # LAST VALUE LOGIK
                        # Wir probieren verschiedene Felder für den aktuellen Wert
                        val = m.get("value")
                        if val is None: val = m.get("_value")
                        if val is None: val = m.get("state")
                        
                        if val is not None:
                            ent.last_value = val
                            # Zeitstempel aus den Rohdaten holen, falls vorhanden
                            if "_time" in m:
                                ent.last_seen = m["_time"].isoformat()

                        sample_values = []
                        if val is not None:
                            sample_dt = m.get("_time") if isinstance(m.get("_time"), datetime) else datetime.now(timezone.utc)
                            sample_values.append(self._build_sample_point(sample_dt, val))

                        ent.data_kind, ent.value_semantics, ent.render_mode = self._derive_series_characteristics(
                            ent.domain,
                            state_class=state_class,
                            device_class=device_class,
                            unit_of_measurement=ent.unit_of_measurement,
                            options=options,
                            samples=sample_values,
                        )

            except Exception as e:
                logger.debug(f"Metadata enrichment failed: {e}")

            # Fallback Strategie: Measurements (falls keine entity_id Tags vorhanden sind)
            if not entities:
                flux_query = f'''
                    import "influxdata/influxdb/schema"
                    schema.measurements(bucket: "{bucket}")
                '''
                tables = query_api.query(query=flux_query)
                for table in tables:
                    for record in table.records:
                        eid = record.get_value()
                        if not eid or '.' not in eid or eid in seen_ids:
                            continue
                        seen_ids.add(eid)
                        domain = eid.split('.')[0]
                        data_kind = self._get_data_kind(domain)
                        entities.append(Entity(
                            entity_id=eid,
                            domain=domain,
                            friendly_name=eid.split('.')[-1].replace('_', ' ').title(),
                            data_kind=data_kind,
                            value_semantics=self._get_value_semantics(domain, data_kind=data_kind),
                            render_mode=self._get_render_mode(data_kind),
                            chartable=True,
                            source_table=eid
                        ))
            
            return entities
                
        except Exception as e:
            logger.error(f"Error querying InfluxDB 2 for entities in bucket {bucket}: {e}")
            
        return self._get_demo_entities()

    def _get_demo_entities(self) -> List[Entity]:
        return []

    async def get_dashboard_data(
        self,
        device: Device,
        entity_ids: List[str]
    ) -> List[DashboardEntityData]:
        """
        Fetch specialized dashboard data:
        - the latest real point
        - a lightweight 24h sparkline aligned with the chart semantics
        - freshness information
        """
        bucket = device.influx_database_name or settings.INFLUXDB_BUCKET
        query_api = self.client.query_api()
        end_dt = datetime.now(timezone.utc)
        start_dt = end_dt - timedelta(hours=24)
        start_ts = self._format_utc_timestamp(start_dt)
        end_ts = self._format_utc_timestamp(end_dt)
        results = []

        for eid in entity_ids:
            try:
                domain = eid.split('.')[0] if '.' in eid else "sensor"
                latest_samples = []
                metadata = self._read_entity_metadata(query_api, bucket, eid, end_dt)
                friendly_name = metadata.get("friendly_name", eid)
                state_class = metadata.get("state_class")
                device_class = metadata.get("device_class")
                unit_of_measurement = metadata.get("unit_of_measurement")
                options = metadata.get("options")

                last_query = f'''
                    from(bucket: "{bucket}")
                    |> range(start: 0)
                    |> filter(fn: (r) => r["_measurement"] == "{eid}" or r["entity_id"] == "{eid}")
                    |> filter(fn: (r) => r["_field"] == "value" or r["_field"] == "state")
                    |> last()
                    |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
                '''

                latest_point = None
                last_tables = query_api.query(query=last_query)
                for table in last_tables:
                    for record in table.records:
                        ts = record.get_time().isoformat().replace('+00:00', 'Z')
                        if "T" in ts and not ts.endswith('Z'):
                            ts += 'Z'
                        val = record.values.get("value")
                        if val is None: val = record.values.get("state")
                        
                        num_val = 0.0
                        state = str(val) if val is not None else ""
                        if isinstance(val, (int, float)): num_val = float(val)
                        elif isinstance(val, bool): num_val = 1.0 if val else 0.0
                        elif isinstance(val, str): 
                            state = val
                            low_val = val.lower()
                            if low_val in ['on', 'true', 'active', 'heating', 'an']: num_val = 1.0
                            elif low_val in ['off', 'false', 'idle', 'inactive', 'aus']: num_val = 0.0

                        latest_samples.append(self._build_sample_point(record.get_time(), val))

                        latest_point = DashboardDataPoint(ts=ts, value=num_val, state=state, is_actual=True)

                previous_sample = self._read_last_sample_before(query_api, bucket, eid, start_dt)
                classification_samples = ([previous_sample] if previous_sample else []) + latest_samples
                data_kind, value_semantics, render_mode = self._derive_series_characteristics(
                    domain,
                    state_class=state_class,
                    device_class=device_class,
                    unit_of_measurement=unit_of_measurement,
                    options=options,
                    samples=classification_samples,
                )
                uses_held_values = render_mode == "history_counter" or value_semantics == "instant"
                agg_fn = "last" if uses_held_values or data_kind != "numeric" else "mean"

                sparkline_points = []
                if data_kind == "numeric":
                    aggregated_samples = []
                    sparkline_query = f'''
                        from(bucket: "{bucket}")
                        |> range(start: time(v: "{start_ts}"), stop: time(v: "{end_ts}"))
                        |> filter(fn: (r) => r["_measurement"] == "{eid}" or r["entity_id"] == "{eid}")
                        |> filter(fn: (r) => r["_field"] == "value" or r["_field"] == "state")
                        |> map(fn: (r) => ({{ r with _value: float(v: r._value) }}))
                        |> aggregateWindow(every: 30m, fn: {agg_fn}, createEmpty: false)
                        |> keep(columns: ["_time", "_value"])
                    '''

                    try:
                        spark_tables = query_api.query(query=sparkline_query)
                        for table in spark_tables:
                            for record in table.records:
                                aggregated_samples.append(self._build_sample_point(record.get_time(), record.get_value()))
                    except Exception as spark_err:
                        logger.warning(f"Could not fetch sparkline for {eid}: {spark_err}")

                    if render_mode == "history_counter":
                        sparkline_data = self._build_history_counter_points(
                            start_dt,
                            end_dt,
                            previous_sample,
                            aggregated_samples,
                        )
                    else:
                        sparkline_data = self._build_history_line_points(
                            start_dt,
                            end_dt,
                            previous_sample,
                            aggregated_samples,
                        )

                    sparkline_points = [
                        DashboardDataPoint(
                            ts=point.ts,
                            value=point.value,
                            state=point.state,
                            is_actual=point.is_actual,
                        )
                        for point in sparkline_data
                    ]

                is_stale = True
                freshness_info = "Keine Daten"
                if latest_point:
                    lp_dt = datetime.fromisoformat(latest_point.ts.replace('Z', '+00:00'))
                    diff = datetime.now(pytz.utc) - lp_dt
                    
                    if diff < timedelta(minutes=30):
                        is_stale = False
                        freshness_info = "Aktuell"
                    elif diff < timedelta(hours=2):
                        is_stale = False
                        freshness_info = f"Vor {int(diff.total_seconds() // 60)} Min"
                    else:
                        is_stale = True
                        if diff < timedelta(days=1):
                            freshness_info = f"Vor {int(diff.total_seconds() // 3600)} Std"
                        else:
                            freshness_info = f"Vor {int(diff.days)} Tagen"

                results.append(DashboardEntityData(
                    entity_id=eid,
                    friendly_name=friendly_name,
                    domain=eid.split('.')[0] if '.' in eid else "sensor",
                    data_kind=data_kind,
                    value_semantics=value_semantics,
                    render_mode=render_mode,
                    state_class=state_class,
                    device_class=device_class,
                    unit_of_measurement=unit_of_measurement,
                    latest_point=latest_point,
                    sparkline=sparkline_points,
                    is_stale=is_stale,
                    freshness_info=freshness_info
                ))

            except Exception as e:
                logger.error(f"Error fetching dashboard data for {eid}: {e}")
                
        return results

    async def get_timeseries(
        self, 
        device: Device, 
        entity_ids: List[str], 
        start: str, 
        end: str
    ) -> Dict[str, Any]:
        """
        Fetch timeseries data from InfluxDB 2 using Flux.
        Returns a dict containing 'series' and 'range_resolved'.
        """
        bucket = device.influx_database_name or settings.INFLUXDB_BUCKET
        query_api = self.client.query_api()
        results = []
        tz_berlin = pytz.timezone("Europe/Berlin")
        start_dt, end_dt = self._resolve_time_range(start, end, tz_berlin)
        resolved_from = self._format_utc_timestamp(start_dt)
        resolved_to = self._format_utc_timestamp(end_dt)

        for eid in entity_ids:
            default_domain = eid.split('.')[0] if '.' in eid else "sensor"
            metadata = self._read_entity_metadata(query_api, bucket, eid, end_dt)
            previous_sample = self._read_last_sample_before(query_api, bucket, eid, start_dt)
            actual_samples = self._read_samples_in_range(query_api, bucket, eid, start_dt, end_dt)

            classification_samples = ([] if previous_sample is None else [previous_sample]) + actual_samples
            friendly_name = metadata.get("friendly_name") or eid.replace('_', ' ').replace('.', ' ').title()
            domain = metadata.get("domain") or default_domain
            unit_of_measurement = metadata.get("unit_of_measurement")
            state_class = metadata.get("state_class")
            device_class = metadata.get("device_class")
            options = metadata.get("options")

            data_kind, value_semantics, render_mode = self._derive_series_characteristics(
                domain,
                state_class=state_class,
                device_class=device_class,
                unit_of_measurement=unit_of_measurement,
                options=options,
                samples=classification_samples,
            )

            if render_mode == "history_counter":
                points = self._build_history_counter_points(start_dt, end_dt, previous_sample, actual_samples)
            elif render_mode == "state_timeline":
                points = self._build_state_timeline_points(start_dt, end_dt, previous_sample, actual_samples)
            else:
                points = self._build_history_line_points(start_dt, end_dt, previous_sample, actual_samples)

            last_seen = None
            if actual_samples:
                last_seen = self._format_utc_timestamp(actual_samples[-1]['dt'])
            elif previous_sample:
                last_seen = self._format_utc_timestamp(previous_sample['dt'])

            results.append(TimeSeriesResponse(
                entity_id=eid,
                friendly_name=friendly_name,
                domain=domain,
                data_kind=data_kind,
                value_semantics=value_semantics,
                render_mode=render_mode,
                chartable=True,
                state_class=state_class,
                device_class=device_class,
                unit_of_measurement=unit_of_measurement,
                points=points,
                meta={
                    "unit_of_measurement": unit_of_measurement,
                    "state_class": state_class,
                    "device_class": device_class,
                    "options": options,
                    "last_seen": last_seen,
                    "on_label": "An" if data_kind == "binary" else None,
                    "off_label": "Aus" if data_kind == "binary" else None,
                }
            ))
            
        return {
            "series": results,
            "range_resolved": {
                "from": resolved_from,
                "to": resolved_to
            }
        }

influx_service = InfluxService(
    host=settings.INFLUXDB_URL,
    token=settings.INFLUXDB_TOKEN,
    org=settings.INFLUXDB_ORG
)
