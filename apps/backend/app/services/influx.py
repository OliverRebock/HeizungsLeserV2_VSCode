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

    def _get_value_semantics(self, eid: str, unit: Optional[str] = None) -> str:
        """
        Derives the semantic meaning of a value based on its ID, unit, or friendly name.
        Classifies numeric values into:
        - stateful: Values that naturally hold their state until a change occurs (e.g. Temperature, Pressure)
        - instant: Instantaneous/Output-based values that represent activity/power (e.g. W, kW, Power)
        - default: Standard fallback
        """
        lower_eid = eid.lower()
        lower_unit = unit.lower() if unit else ""
        
        # Instant/Output keywords (typically power, power output, watt, etc.)
        # Wir erweitern die Keywords massiv, um "für alle" sinnvollen (nicht-Temperatur) Entitäten 
        # eine 0-Referenz zu ermöglichen.
        instant_keywords = [
            "power", "leistung", "current_flow", "verbrauch", "output", "active_power", 
            "apparent_power", "current", "speed", "drehzahl", "flow_pc", "energy", 
            "consumption", "voltage", "spann", "current", "strom", "frequency", 
            "frequenz", "flow", "durchfluss", "percent", "prozent", "coefficient", 
            "cop", "duty", "modulation"
        ]
        instant_units = [
            "w", "kw", "va", "var", "hz", "a", "%", "rpm", "l/h", "m3/h", "v", 
            "wh", "kwh", "cop", "eer"
        ]
        
        # Stateful keywords (typically temperatures, pressure, setpoints, battery levels)
        stateful_keywords = ["temp", "grad", "grad_c", "druck", "pressure", "battery", "soc", "level", "setpoint", "target", "humidity", "feuchtigkeit"]
        stateful_units = ["°c", "c", "bar", "psi"]
        
        if any(kw in lower_eid for kw in instant_keywords) or lower_unit in instant_units:
            return "instant"
            
        if any(kw in lower_eid for kw in stateful_keywords) or lower_unit in stateful_units:
            return "stateful"
            
        # Domain-based fallback
        domain = eid.split('.')[0] if '.' in eid else "sensor"
        if domain in ["binary_sensor", "switch", "lock", "input_boolean"]:
            return "stateful" # Binary states are stateful
            
        return "default"

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
            "state", "condition", "type", "step",
            "error", "fault", "warning", "alarm", "code"
        ]
        
        # Counter/Numeric triggers (Force these to be numeric even if they match enum triggers)
        numeric_triggers = ["starts", "total", "count", "counter", "duration", "runtime", "level", "zähler", "zaehler"]
        
        if domain in ["select", "input_select", "device_tracker", "person", "update"]:
            return "enum"
            
        if any(nt in lower_eid for nt in numeric_triggers):
            return "numeric"
            
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
                        data_kind = self._get_data_kind(domain, eid)
                        entities.append(Entity(
                            entity_id=eid,
                            domain=domain,
                            friendly_name=eid.split('.')[-1].replace('_', ' ').title(),
                            data_kind=data_kind,
                            value_semantics=self._get_value_semantics(eid),
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
                        
                        ent.value_semantics = self._get_value_semantics(ent.entity_id, ent.unit_of_measurement)

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
                        data_kind = "binary" if domain == "binary_sensor" else "numeric"
                        entities.append(Entity(
                            entity_id=eid,
                            domain=domain,
                            friendly_name=eid.split('.')[-1].replace('_', ' ').title(),
                            data_kind=data_kind,
                            value_semantics=self._get_value_semantics(eid),
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
        - a clean, aggregated sparkline (last 24h, 48 points)
        - freshness check
        """
        import pytz
        from datetime import datetime, timedelta
        
        bucket = device.influx_database_name or settings.INFLUXDB_BUCKET
        query_api = self.client.query_api()
        tz_berlin = pytz.timezone("Europe/Berlin")
        
        results = []
        
        for eid in entity_ids:
            try:
                # 0. Determine data kind and aggregation strategy
                domain = eid.split('.')[0] if '.' in eid else "sensor"
                data_kind = self._get_data_kind(domain, eid)
                # Use mean for numeric, but last/max for others to avoid InfluxDB errors with strings
                agg_fn = "mean" if data_kind == "numeric" else "last"

                # 1. Get the last point EVER for this entity (latest point)
                last_query = f'''
                    from(bucket: "{bucket}")
                    |> range(start: 0)
                    |> filter(fn: (r) => r["_measurement"] == "{eid}" or r["entity_id"] == "{eid}")
                    |> filter(fn: (r) => r["_field"] == "value" or r["_field"] == "state")
                    |> last()
                    |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
                '''
                
                latest_point = None
                friendly_name = eid
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

                # 2. Get aggregated sparkline (last 24h, 48 points/buckets)
                # We use 30m windows for 24h = 48 points
                # For sparkline we only care about numeric value
                sparkline_points = []
                try:
                    # To avoid schema collision (float vs string), we process fields separately or cast
                    # For sparklines, we prefer the "value" field.
                    sparkline_query = f'''
                        from(bucket: "{bucket}")
                        |> range(start: -24h)
                        |> filter(fn: (r) => r["_measurement"] == "{eid}" or r["entity_id"] == "{eid}")
                        |> filter(fn: (r) => r["_field"] == "value" or r["_field"] == "state")
                        |> map(fn: (r) => ({{ r with _value: float(v: r._value) }}))
                        |> aggregateWindow(every: 30m, fn: {agg_fn}, createEmpty: false)
                        |> keep(columns: ["_time", "_value"])
                    '''
                    
                    spark_tables = query_api.query(query=sparkline_query)
                    for table in spark_tables:
                        for record in table.records:
                            rec_val = record.get_value()
                            num_rec_val = 0.0
                            if isinstance(rec_val, (int, float)):
                                num_rec_val = float(rec_val)
                            elif isinstance(rec_val, bool):
                                num_rec_val = 1.0 if rec_val else 0.0
                            elif isinstance(rec_val, str):
                                low_rec = rec_val.lower()
                                if low_rec in ['on', 'true', 'active', 'heating', 'an']: num_rec_val = 1.0
                                elif low_rec in ['off', 'false', 'idle', 'inactive', 'aus']: num_rec_val = 0.0
                                
                            sparkline_points.append(DashboardDataPoint(
                                ts=record.get_time().isoformat(),
                                value=num_rec_val,
                                state="",
                                is_actual=False
                            ))
                except Exception as spark_err:
                    logger.warning(f"Could not fetch sparkline for {eid}: {spark_err}")
                    # Keep empty list, but don't fail the whole entity

                # 3. Get friendly name if possible
                fn_query = f'''
                    from(bucket: "{bucket}")
                    |> range(start: -7d)
                    |> filter(fn: (r) => r["_measurement"] == "{eid}" or r["entity_id"] == "{eid}")
                    |> filter(fn: (r) => r["_field"] == "friendly_name_str")
                    |> last()
                '''
                fn_tables = query_api.query(query=fn_query)
                for table in fn_tables:
                    for record in table.records:
                        if record.get_value():
                            friendly_name = self._clean_friendly_name(record.get_value())

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
                value_semantics = self._get_value_semantics(eid)
                
                results.append(DashboardEntityData(
                    entity_id=eid,
                    friendly_name=friendly_name,
                    domain=eid.split('.')[0] if '.' in eid else "sensor",
                    data_kind=data_kind,
                    value_semantics=value_semantics,
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

        import pytz
        from datetime import datetime, timedelta, timezone as dt_timezone
        tz_berlin = pytz.timezone("Europe/Berlin")

        def format_time(t, default_val="-24h"):
            logger.debug(f"INFLUX_SERVICE: Formatting time input: '{t}' (type={type(t)})")
            if not t: return default_val
            if isinstance(t, str):
                if t == "now()": return "now()"
                
                # Check for keywords first to avoid matching them in the relative check (e.g. 'today' contains 'd')
                if t == "today": 
                    now_val = datetime.now(tz_berlin)
                    today_start = now_val.replace(hour=0, minute=0, second=0, microsecond=0)
                    iso_start = today_start.isoformat()
                    logger.debug(f"INFLUX_SERVICE: 'today' resolved to (Berlin): {iso_start}")
                    return iso_start
                    
                if t == "yesterday":
                    now_val = datetime.now(tz_berlin)
                    yesterday_start = (now_val - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
                    yesterday_end = yesterday_start.replace(hour=23, minute=59, second=59, microsecond=999999)
                    iso_start = yesterday_start.isoformat()
                    iso_end = yesterday_end.isoformat()
                    logger.debug(f"INFLUX_SERVICE: 'yesterday' resolved to (Berlin): {iso_start} to {iso_end}")
                    return f"{iso_start}|{iso_end}"
                
                if t == "this_week":
                    now_val = datetime.now(tz_berlin)
                    monday_start = (now_val - timedelta(days=now_val.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
                    iso_start = monday_start.isoformat()
                    logger.debug(f"INFLUX_SERVICE: 'this_week' resolved to (Berlin): {iso_start}")
                    return iso_start

                if t == "this_month":
                    now_val = datetime.now(tz_berlin)
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

        # Resolve relative times to absolute for the frontend
        now_utc = datetime.now(dt_timezone.utc)
        resolved_from = flux_start
        resolved_to = flux_end if flux_end != "now()" else now_utc.isoformat()

        if isinstance(flux_start, str) and flux_start.startswith("-") and "T" not in flux_start:
            # Relative duration
            try:
                val = int(flux_start[1:-1])
                unit = flux_start[-1]
                if unit == 'h': resolved_from = (now_utc - timedelta(hours=val)).isoformat()
                elif unit == 'd': resolved_from = (now_utc - timedelta(days=val)).isoformat()
                elif unit == 'm': resolved_from = (now_utc - timedelta(minutes=val)).isoformat()
                elif unit == 's': resolved_from = (now_utc - timedelta(seconds=val)).isoformat()
            except: pass

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
            # WICHTIG: Für NUMERISCHE Entitäten setzen wir den künstlichen Startpunkt NICHT 
            # auf den exakten Range-Beginn, um Artefakte/Ausschläge zu vermeiden, wenn der 
            # Punkt zeitlich weit weg liegt. Stattdessen fügen wir ihn nur ein, wenn wir 
            # wirklich wissen, dass der Wert bis zum Start konstant blieb.
            # EXZEPTION: Für Counter/Zähler (starts, total, count) übernehmen wir den letzten 
            # bekannten Wert als Startpunkt am linken Rand, um eine HA-nahe Step-Line zu ermöglichen.
            data_kind = self._get_data_kind(domain, eid)
            is_counter = any(kw in eid.lower() for kw in ["starts", "total", "count", "counter"])
            
            try:
                last_tables = query_api.query(query=last_query)
                for table in last_tables:
                    for record in table.records:
                        val = record.values.get("value")
                        if val is None: val = record.values.get("state")
                        
                        if val is not None:
                            num_val = float(val) if isinstance(val, (int, float, bool)) else 0.0
                            state = str(val)
                            
                            # Logik-Entscheidung:
                            if data_kind in ("binary", "enum", "string") or is_counter:
                                # Für State-History (Binär/Enum) UND COUNTER ist der Startpunkt ESSENZIELL
                                fake_ts = start_rfc if "T" in start_rfc else datetime.now().isoformat()
                                points.append(DataPoint(ts=fake_ts, value=num_val, state=state))
                                logger.debug(f"INFLUX_SERVICE: Added START-PADDING for {data_kind} (counter={is_counter}) entity {eid}: {val}")
                            else:
                                # Für normale NUMERISCHE Werte (Temperaturen etc.): 
                                # AUF BENUTZERWUNSCH: Wir fügen KEINEN Punkt vor dem Range-Start mehr ein,
                                # um zu verhindern, dass die X-Achse nach links gedehnt wird.
                                # Der Punkt wird nur geloggt, aber NICHT in die Serie aufgenommen.
                                logger.debug(f"INFLUX_SERVICE: Skipping pre-range point for numeric entity {eid} to keep X-axis clean: {val}")
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
                        
                        # --- NEU: Gap-Erkennung (Lücken im Messverlauf) ---
                        # Wenn wir numerische Daten haben und die Lücke zum vorherigen Punkt > 30 Min ist,
                        # fügen wir einen Null-Punkt (Gap) ein, damit ECharts keine falsche Linie zieht.
                        if data_kind == "numeric" and points:
                            try:
                                last_ts_str = points[-1].ts.replace('Z', '+00:00')
                                current_ts_str = ts.replace('Z', '+00:00')
                                dt_prev = datetime.fromisoformat(last_ts_str)
                                dt_curr = datetime.fromisoformat(current_ts_str)
                                
                                # --- NEU: Padding für Counter-Werte für HA-Style Treppen (Step-Lines) ---
                                # Für Counter (starts, total, count) fügen wir vor JEDEM neuen Punkt einen
                                # Zwischenschritt ein (alter Wert bis 1ms vor neuem Zeitstempel),
                                # damit ECharts IMMER eine saubere Treppe statt einer schrägen Linie zeichnet.
                                if is_counter and points[-1].value is not None:
                                    dt_step = dt_curr - timedelta(milliseconds=1)
                                    step_ts = dt_step.isoformat().replace('+00:00', 'Z')
                                    points.append(DataPoint(ts=step_ts, value=points[-1].value, state=points[-1].state))
                                    logger.debug(f"INFLUX_SERVICE: Added Step-Padding for Counter {eid} at {step_ts}")
                                else:
                                    dt_step = dt_prev

                                if (dt_curr - dt_prev).total_seconds() > 1800: # > 30 Min
                                    # Wir fügen den Gap-Punkt 1ms nach dem letzten Punkt ein (oder nach dem Step-Padding)
                                    dt_gap = dt_step + timedelta(milliseconds=1)
                                    gap_ts = dt_gap.isoformat().replace('+00:00', 'Z')
                                    # Nur wenn wir nicht schon einen Gap haben
                                    if points[-1].value is not None:
                                        points.append(DataPoint(ts=gap_ts, value=None, state="gap"))
                                        logger.debug(f"INFLUX_SERVICE: Inserted GAP between points for {eid}")
                            except Exception as e:
                                logger.error(f"INFLUX_SERVICE: Gap detection error for {eid}: {e}")

                        points.append(DataPoint(ts=ts, value=num_val, state=state))
            except Exception as e:
                logger.warning(f"INFLUX_SERVICE: Query error for {eid}: {e}")
                
            # 3. Carry Forward zum Endzeitpunkt (Last point to end of range)
            # Auf Benutzerwunsch: Zeilinie IMMER bis zum rechten Rand (Uhrzeit jetzt) weiterziehen.
            # Fachregel: Leistungswerte (instant) fallen auf 0, wenn der letzte Punkt > 15 Min alt ist.
            value_semantics = self._get_value_semantics(eid, unit_of_measurement)
            # DEBUG
            if "power" in eid.lower() or "leistung" in eid.lower():
                logger.info(f"INFLUX_DEBUG: {eid} has semantics: {value_semantics}")

            if points:
                # Sortieren um sicherzustellen, dass wir den wirklich letzten haben
                points.sort(key=lambda p: p.ts)
                last_p = points[-1]
                
                # Wir bestimmen den absoluten Endzeitpunkt für das Carry-Forward
                import pytz
                from datetime import datetime as dt_final, timezone as dt_timezone
                
                # Wir nutzen UTC für den robusten Zeitvergleich
                now_utc = dt_final.now(dt_timezone.utc)
                
                final_end_ts = end_rfc
                if "T" not in str(final_end_ts):
                    final_end_ts = now_utc.isoformat()
                
                # Wir prüfen, ob das Ende des Zeitraums in der Nähe von "jetzt" liegt (innerhalb von 5 Min)
                # Falls ja, wenden wir die Timeout-Logik (15 Min auf 0) an.
                # Falls nein (z.B. Ansicht "Gestern"), ziehen wir den Wert einfach bis zum Ende des Zeitraums durch.
                is_near_now = False
                try:
                    ts_end_to_parse = final_end_ts.replace('Z', '+00:00')
                    dt_end = datetime.fromisoformat(ts_end_to_parse)
                    if dt_end.tzinfo is None:
                        dt_end = dt_end.replace(tzinfo=dt_timezone.utc)
                    
                    # Wenn das Ende des Graphen weniger als 5 Min von JETZT entfernt ist
                    if abs((now_utc - dt_end).total_seconds()) < 300:
                        is_near_now = True
                except:
                    # Fallback auf True für relative Zeitangaben wie "now()"
                    if "now" in str(end_rfc).lower():
                        is_near_now = True

                # Nur wenn der letzte Punkt zeitlich vor dem Ende liegt (ISO string compare)
                if last_p.ts < final_end_ts:
                    carry_value = last_p.value
                    carry_state = last_p.state
                    
                    # Logik für momentane Werte (Leistung etc.)
                    if value_semantics == "instant":
                        try:
                            # Prüfen wie alt der letzte Punkt ist (Influx liefert UTC)
                            ts_to_parse = last_p.ts.replace('Z', '+00:00')
                            dt_last = datetime.fromisoformat(ts_to_parse)
                            # Sicherstellen dass dt_last auch timezone-aware in UTC ist
                            if dt_last.tzinfo is None:
                                dt_last = dt_last.replace(tzinfo=dt_timezone.utc)
                            
                            # Wenn wir uns am aktuellen Rand befinden (HEUTE / JETZT):
                            # Wenn der letzte Punkt älter als 15 Minuten ist, fallen wir am Rand auf None (Gap)
                            if is_near_now:
                                # Wir prüfen gegen den absoluten JETZT Zeitpunkt, nicht gegen das Graph-Ende,
                                # um Geisterlinien am aktuellen Rand zu vermeiden.
                                diff_seconds = (now_utc - dt_last).total_seconds()
                                if diff_seconds > 900: # 15 * 60
                                    # NEU: Wir fügen einen Punkt direkt beim letzten echten Wert + 1ms ein,
                                    # gefolgt von einem Gap (None) am rechten Rand.
                                    # Das sorgt dafür, dass die blaue Linie am letzten echten Messwert abbricht.
                                    dt_drop = dt_last + timedelta(milliseconds=1)
                                    drop_ts = dt_drop.isoformat().replace('+00:00', 'Z')
                                    points.append(DataPoint(ts=drop_ts, value=last_p.value, state=last_p.state))
                                    
                                    # Wir setzen den Wert auf None (Gap), statt auf 0.0
                                    # Die visuelle Null-Referenz kommt nun exklusiv aus dem Frontend (markLine)
                                    carry_value = None
                                    carry_state = f"Keine Daten (Timeout: {int(diff_seconds/60)}m alt)"
                                    logger.info(f"INFLUX_SERVICE: Instant value {eid} timed out ({int(diff_seconds/60)}m), adding gap (None) at end.")
                            else:
                                # Wir sind in einer historischen Ansicht (z.B. GESTERN).
                                # Auch hier: Wenn zwischen dem letzten Punkt und dem Zeitraum-Ende > 15 Min liegen,
                                # lassen wir den Wert auf None (Gap) fallen.
                                diff_to_end = (dt_end - dt_last).total_seconds()
                                if diff_to_end > 900:
                                    dt_drop = dt_last + timedelta(milliseconds=1)
                                    drop_ts = dt_drop.isoformat().replace('+00:00', 'Z')
                                    points.append(DataPoint(ts=drop_ts, value=last_p.value, state=last_p.state))
                                    
                                    carry_value = None
                                    carry_state = "Keine Daten (Historisches Timeout)"
                                    logger.debug(f"INFLUX_SERVICE: Historical timeout for {eid} at {final_end_ts} -> Gap")
                                    
                        except Exception as e:
                            logger.error(f"INFLUX_SERVICE: Error calculating timeout for {eid}: {e}")

                    points.append(DataPoint(ts=final_end_ts, value=carry_value, state=carry_state))
                    logger.debug(f"INFLUX_SERVICE: Carrying forward {eid} to absolute end: {final_end_ts} (Value: {carry_value})")

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
                value_semantics=value_semantics,
                chartable=True,
                points=sorted(points, key=lambda p: p.ts),
                meta={
                    "unit_of_measurement": unit_of_measurement,
                    "on_label": "An" if data_kind == "binary" else None,
                    "off_label": "Aus" if data_kind == "binary" else None
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
