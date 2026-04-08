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
from typing import List, Dict, Any, Optional
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

    def _get_data_kind(self, domain: str, eid: str) -> str:
        """
        Derives data kind from domain and entity id.
        Now covers a wide range of state-based sensors.
        """
        lower_eid = eid.lower()
        
        # Binary triggers
        binary_domains = ["binary_sensor", "switch", "lock", "input_boolean"]
        binary_keywords = ["active", "status_pc1", "status_pc2", "heating_active", "pump_status"]
        
        if domain in binary_domains or any(kw in lower_eid for kw in binary_keywords):
            return "binary"
            
        # Enum/Text detection for selects and status sensors
        enum_triggers = [
            "select", "status", "mode", "phase", "art", 
            "state", "condition", "type", "step", "level",
            "error", "fault", "warning", "alarm", "code"
        ]
        
        if domain in ["select", "input_select", "device_tracker", "person", "update"]:
            return "enum"
            
        if any(trigger in lower_eid for trigger in enum_triggers):
            return "enum"
            
        return "numeric"

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
                        entities.append(Entity(
                            entity_id=eid,
                            domain=domain,
                            friendly_name=eid.split('.')[-1].replace('_', ' ').title(),
                            data_kind=self._get_data_kind(domain, eid),
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
                        
                        # Domain Update
                        if m.get("domain"):
                            ent.domain = m.get("domain")
                            ent.data_kind = self._get_data_kind(ent.domain, ent.entity_id)

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
                        entities.append(Entity(
                            entity_id=eid,
                            domain=domain,
                            friendly_name=eid.split('.')[-1].replace('_', ' ').title(),
                            data_kind="binary" if domain == "binary_sensor" else "numeric",
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
        - the very last REAL point (no carry forward, no padding)
        - a small sparkline (last 24h, no artificial start/end points)
        - freshness check
        """
        import pytz
        from datetime import datetime, timedelta
        
        bucket = device.influx_database_name or settings.INFLUXDB_BUCKET
        query_api = self.client.query_api()
        tz_berlin = pytz.timezone("Europe/Berlin")
        now_berlin = datetime.now(tz_berlin)
        
        results = []
        
        for eid in entity_ids:
            # 1. Get the last 10 points for sparkline + latest info
            # We query last 24h by default for the sparkline
            query = f'''
                from(bucket: "{bucket}")
                |> range(start: -24h)
                |> filter(fn: (r) => r["_measurement"] == "{eid}" or r["entity_id"] == "{eid}")
                |> filter(fn: (r) => r["_field"] == "value" or r["_field"] == "state" or r["_field"] == "friendly_name_str")
                |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
                |> sort(columns: ["_time"], desc: false)
                |> keep(columns: ["_time", "value", "state", "friendly_name_str"])
            '''
            
            try:
                tables = query_api.query(query=query)
                all_points = []
                friendly_name = eid
                
                for table in tables:
                    for record in table.records:
                        ts = record.get_time().isoformat()
                        val = record.values.get("value")
                        if val is None: val = record.values.get("state")
                        
                        if record.values.get("friendly_name_str"):
                            friendly_name = self._clean_friendly_name(record.values.get("friendly_name_str"))
                            
                        num_val = 0.0
                        state = str(val) if val is not None else ""
                        if isinstance(val, (int, float)):
                            num_val = float(val)
                        elif isinstance(val, bool):
                            num_val = 1.0 if val else 0.0
                            state = "on" if val else "off"
                        elif isinstance(val, str):
                            state = val
                            low_val = val.lower()
                            if low_val in ['on', 'true', 'active', 'heating', 'an']: num_val = 1.0
                            elif low_val in ['off', 'false', 'idle', 'inactive', 'aus']: num_val = 0.0
                        
                        all_points.append(DashboardDataPoint(
                            ts=ts, 
                            value=num_val, 
                            state=state, 
                            is_actual=True
                        ))
                
                # If no data in 24h, try to get at least the absolute last point ever
                latest_point = None
                if all_points:
                    latest_point = all_points[-1]
                else:
                    last_query = f'''
                        from(bucket: "{bucket}")
                        |> range(start: 0)
                        |> filter(fn: (r) => r["_measurement"] == "{eid}" or r["entity_id"] == "{eid}")
                        |> filter(fn: (r) => r["_field"] == "value" or r["_field"] == "state")
                        |> last()
                        |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
                    '''
                    last_tables = query_api.query(query=last_query)
                    for table in last_tables:
                        for record in table.records:
                            ts = record.get_time().isoformat()
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
                            
                            latest_point = DashboardDataPoint(ts=ts, value=num_val, state=state, is_actual=True)

                # Freshness check
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

                data_kind = self._get_data_kind(eid.split('.')[0] if '.' in eid else "sensor", eid)
                
                results.append(DashboardEntityData(
                    entity_id=eid,
                    friendly_name=friendly_name,
                    domain=eid.split('.')[0] if '.' in eid else "sensor",
                    data_kind=data_kind,
                    latest_point=latest_point,
                    sparkline=all_points[-20:] if len(all_points) > 20 else all_points,
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
    ) -> List[TimeSeriesResponse]:
        """
        Fetch timeseries data from InfluxDB 2 using Flux.
        Optimized to find data by either Measurement OR entity_id Tag.
        """
        bucket = device.influx_database_name or settings.INFLUXDB_BUCKET
        query_api = self.client.query_api()
        results = []

        def format_time(t, default_val="-24h"):
            import pytz
            from datetime import datetime, timedelta
            logger.debug(f"INFLUX_SERVICE: Formatting time input: '{t}' (type={type(t)})")
            if not t: return default_val
            if isinstance(t, str):
                if t == "now()": return "now()"
                
                # Check for keywords first to avoid matching them in the relative check (e.g. 'today' contains 'd')
                if t == "today": 
                    now_val = datetime.now(pytz.timezone("Europe/Berlin"))
                    today_start = now_val.replace(hour=0, minute=0, second=0, microsecond=0)
                    iso_start = today_start.isoformat()
                    logger.debug(f"INFLUX_SERVICE: 'today' resolved to (Berlin): {iso_start}")
                    return iso_start
                    
                if t == "yesterday":
                    now_val = datetime.now(pytz.timezone("Europe/Berlin"))
                    yesterday_start = (now_val - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
                    yesterday_end = yesterday_start.replace(hour=23, minute=59, second=59, microsecond=999999)
                    iso_start = yesterday_start.isoformat()
                    iso_end = yesterday_end.isoformat()
                    logger.debug(f"INFLUX_SERVICE: 'yesterday' resolved to (Berlin): {iso_start} to {iso_end}")
                    return f"{iso_start}|{iso_end}"
                
                if t == "this_week":
                    now_val = datetime.now(pytz.timezone("Europe/Berlin"))
                    monday_start = (now_val - timedelta(days=now_val.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
                    iso_start = monday_start.isoformat()
                    logger.debug(f"INFLUX_SERVICE: 'this_week' resolved to (Berlin): {iso_start}")
                    return iso_start

                if t == "this_month":
                    now_val = datetime.now(pytz.timezone("Europe/Berlin"))
                    month_start = now_val.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                    iso_start = month_start.isoformat()
                    logger.debug(f"INFLUX_SERVICE: 'this_month' resolved to (Berlin): {iso_start}")
                    return iso_start

                # If it's a simple relative duration like 24h, 12h etc
                if any(unit in t for unit in ['h', 'd', 'm', 's']) and "T" not in t:
                    if t.startswith('-'):
                        return t
                    return f"-{t}"
                
                # Check for ISO format
                if "T" in t:
                    if not t.endswith('Z') and '+' not in t:
                        return t + 'Z'
                    return t
            return default_val

        flux_start = format_time(start, "-24h")
        flux_end = format_time(end, "now()")
        
        # Handle the special "yesterday" pipe return
        if "|" in flux_start:
            flux_start, flux_end = flux_start.split("|")

        logger.debug(f"INFLUX_SERVICE: Final flux range before fixing: {flux_start} to {flux_end}")

        # Fix for absolute timestamps: they must not have a leading minus
        if flux_start and "T" in str(flux_start) and str(flux_start).startswith("-"):
            flux_start = str(flux_start)[1:]
            
        # Falls end ein relativer String ohne Vorzeichen ist (z.B. "12h"), machen wir ihn negativ, falls es nicht "now()" ist
        if flux_end and flux_end != "now()" and not str(flux_end).startswith("-") and any(u in str(flux_end) for u in ['h','d','m','s']) and "T" not in str(flux_end):
            flux_end = f"-{flux_end}"
        
        # Absolute Endzeitpunkte ebenfalls vom Minus befreien
        if flux_end and "T" in str(flux_end) and str(flux_end).startswith("-"):
            flux_end = str(flux_end)[1:]

        logger.debug(f"INFLUX_SERVICE: Final flux range: {flux_start} to {flux_end}")

        for eid in entity_ids:
            # WICHTIG: Wir holen value ODER state (für Select-Entitäten).
            # Die time() Funktion in Flux erwartet RFC3339 Format. 
            # Python's isoformat() liefert manchmal Mikrosekunden, die Flux nicht mag, wenn kein Z am Ende steht.
            # Wir stellen sicher, dass es als korrektes RFC3339 (mit Z) gesendet wird.
            def to_rfc3339(ts_str):
                if "T" in ts_str:
                    if not ts_str.endswith('Z') and '+' not in ts_str:
                        return ts_str + 'Z'
                return ts_str

            start_rfc = to_rfc3339(str(flux_start))
            end_rfc = to_rfc3339(str(flux_end))
            
            start_val = f'time(v: "{start_rfc}")' if "T" in start_rfc else start_rfc
            end_val = f'time(v: "{end_rfc}")' if "T" in end_rfc else end_rfc
            
            range_start = start_val
            range_stop = end_val
            
            # --- NEU: Vorherigen Wert abfragen (Last known value before start) ---
            # Wir suchen den letzten Punkt VOR dem gewählten Startzeitpunkt
            last_query = f'''
                from(bucket: "{bucket}")
                |> range(start: 0, stop: {range_start})
                |> filter(fn: (r) => r["_measurement"] == "{eid}" or r["entity_id"] == "{eid}")
                |> filter(fn: (r) => r["_field"] == "value" or r["_field"] == "state")
                |> last()
                |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
            '''
            
            points = []
            friendly_name = eid.replace('_', ' ').replace('.', ' ').title()
            domain = eid.split('.')[0] if '.' in eid else "sensor"
            unit_of_measurement = None

            # 1. Letzten bekannten Wert vor dem Zeitraum holen
            try:
                last_tables = query_api.query(query=last_query)
                for table in last_tables:
                    for record in table.records:
                        # Wir setzen diesen Punkt auf GENAU den Startzeitpunkt
                        # falls wir den Startzeitpunkt als ISO-String haben
                        fake_ts = start_rfc if "T" in start_rfc else datetime.now().isoformat()
                        
                        val = record.values.get("value")
                        if val is None: val = record.values.get("state")
                        
                        if val is not None:
                            num_val = float(val) if isinstance(val, (int, float, bool)) else 0.0
                            state = str(val)
                            points.append(DataPoint(ts=fake_ts, value=num_val, state=state))
                            logger.debug(f"INFLUX_SERVICE: Found last value BEFORE start for {eid}: {val}")
            except Exception as e:
                logger.debug(f"INFLUX_SERVICE: Error during last_query for {eid}: {e}")

            # 2. Hauptabfrage für den Zeitraum
            flux_query = f'''
                from(bucket: "{bucket}")
                |> range(start: {range_start}, stop: {range_stop})
                |> filter(fn: (r) => r["_measurement"] == "{eid}" or r["entity_id"] == "{eid}")
                |> filter(fn: (r) => r["_field"] == "value" or r["_field"] == "state" or r["_field"] == "friendly_name_str" or r["_field"] == "unit_of_measurement_str")
                |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
                |> keep(columns: ["_time", "value", "state", "_measurement", "entity_id", "friendly_name_str", "domain", "unit_of_measurement_str"])
            '''
            
            logger.debug(f"INFLUX_SERVICE: EXECUTING FLUX QUERY for {eid}:\n{flux_query}")
            
            try:
                tables = query_api.query(query=flux_query)
                for table in tables:
                    for record in table.records:
                        ts = record.get_time().isoformat()
                        
                        val = record.values.get("value")
                        if val is None: val = record.values.get("state")
                        
                        if record.values.get("friendly_name_str"):
                            friendly_name = self._clean_friendly_name(record.values.get("friendly_name_str"))
                        if record.values.get("domain"):
                            domain = record.values.get("domain")
                        if record.values.get("unit_of_measurement_str"):
                            unit_of_measurement = str(record.values.get("unit_of_measurement_str"))
                        elif not unit_of_measurement and record.values.get("_measurement"):
                            m = str(record.values.get("_measurement"))
                            if len(m) <= 5 or any(c in m for c in ['°', '%']):
                                unit_of_measurement = m
                            
                        num_val = 0.0
                        state = str(val) if val is not None else ""
                        
                        if isinstance(val, (int, float)):
                            num_val = float(val)
                        elif isinstance(val, bool):
                            num_val = 1.0 if val else 0.0
                            state = "on" if val else "off"
                        elif isinstance(val, str):
                            state = val
                            # Mapping for binary-like strings to numeric values for charts
                            low_val = val.lower()
                            if low_val in ['on', 'true', 'online', 'active', 'heating', 'an']:
                                num_val = 1.0
                            elif low_val in ['off', 'false', 'offline', 'idle', 'inactive', 'aus']:
                                num_val = 0.0
                            else:
                                num_val = 0.0
                        
                        points.append(DataPoint(ts=ts, value=num_val, state=state))
            except Exception as e:
                logger.warning(f"INFLUX_SERVICE: Query error for {eid}: {e}")
                
            # 3. Carry Forward zum Endzeitpunkt (Last point to end of range)
            if points:
                # Sortieren um sicherzustellen, dass wir den wirklich letzten haben
                points.sort(key=lambda p: p.ts)
                last_p = points[-1]
                
                # Wir bestimmen den absoluten Endzeitpunkt für das Carry-Forward
                # Wenn end_rfc ein absoluter Timestamp ist, nehmen wir diesen.
                # Wenn nicht (z.B. "now()"), nehmen wir die aktuelle Zeit in Berlin
                import pytz
                from datetime import datetime as dt_final
                tz_berlin = pytz.timezone("Europe/Berlin")
                
                final_end_ts = end_rfc
                if "T" not in str(final_end_ts):
                    final_end_ts = dt_final.now(tz_berlin).isoformat()
                
                # Nur wenn der letzte Punkt zeitlich vor dem Ende liegt (ISO string compare)
                if last_p.ts < final_end_ts:
                    points.append(DataPoint(ts=final_end_ts, value=last_p.value, state=last_p.state))
                    logger.debug(f"INFLUX_SERVICE: Carrying forward last value for {eid} to absolute end: {final_end_ts}")

            # --- NEU: Double Padding am Anfang für Step-Lines (HA-Style) ---
            # Um schräge Linien vom Start zum ersten echten Punkt zu vermeiden, 
            # fügen wir einen Punkt kurz vor dem ersten echten Punkt ein (mit dem alten Wert)
            if len(points) >= 2:
                points.sort(key=lambda p: p.ts)
                # Wenn der erste Punkt ein künstlicher Startpunkt ist (ts == start_rfc)
                # und der zweite Punkt ein echter Messwert ist, brauchen wir dazwischen 
                # einen Punkt (ts = zweiter_ts - 1ms, val = erster_val)
                first_p = points[0]
                second_p = points[1]
                
                if first_p.ts == start_rfc and second_p.ts > first_p.ts:
                    try:
                        # Wir parsen den zweiten Zeitstempel, ziehen 1ms ab
                        # isoformat von record.get_time() hat oft Z oder +00:00
                        ts_to_parse = second_p.ts.replace('Z', '+00:00')
                        dt_second = datetime.fromisoformat(ts_to_parse)
                        dt_padding = dt_second - timedelta(milliseconds=1)
                        # Wir behalten das Format des Originals bei für den ISO-Vergleich
                        padding_ts = dt_padding.isoformat()
                        if 'Z' in second_p.ts:
                            padding_ts = padding_ts.replace('+00:00', 'Z')
                        
                        # Einfügen zwischen 0 und 1
                        points.insert(1, DataPoint(ts=padding_ts, value=first_p.value, state=first_p.state))
                        logger.debug(f"INFLUX_SERVICE: Added step-padding for {eid} at {padding_ts}")
                    except Exception as e:
                        logger.debug(f"INFLUX_SERVICE: Could not add step-padding for {eid}: {e}")

            logger.debug(f"INFLUX_SERVICE: Found {len(points)} points for {eid} (incl. padding)")
            
            data_kind = self._get_data_kind(domain, eid)
            results.append(TimeSeriesResponse(
                entity_id=eid,
                friendly_name=friendly_name,
                domain=domain,
                data_kind=data_kind,
                chartable=True,
                points=sorted(points, key=lambda p: p.ts),
                meta={
                    "unit_of_measurement": unit_of_measurement,
                    "on_label": "An" if data_kind == "binary" else None,
                    "off_label": "Aus" if data_kind == "binary" else None
                }
            ))
            
        return results

influx_service = InfluxService(
    host=settings.INFLUXDB_URL,
    token=settings.INFLUXDB_TOKEN,
    org=settings.INFLUXDB_ORG
)
