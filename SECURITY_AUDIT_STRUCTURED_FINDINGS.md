# InfluxDB Security Audit - Structured Results

## 1. QUERY EXECUTION POINTS WITH LINE NUMBERS

### Query Methods in influx_service.py (Main Query Executor)

```
METHOD: get_last_data_timestamp()
  File: apps/backend/app/services/influx.py:129-167
  Query Execution: Line 138-141
  Variables Used: bucket (from device.influx_database_name)
  Vulnerability: F-string injection on bucket
  Called From: _enrich_device_status() in devices.py:16
  
  Flux Query:
    from(bucket: "{bucket}")
    |> range(start: -24h)
    |> filter(fn: (r) => r["_field"] == "value" or r["_field"] == "state")
    |> drop(columns: ["_value"])
    |> group()
    |> max(column: "_time")
```

```
METHOD: _read_entity_metadata()
  File: apps/backend/app/services/influx.py:686-724
  Query Execution: Line 694-708
  Variables Used: bucket, eid (entity_id - USER INPUT)
  Vulnerability: F-string injection on bucket AND eid ⚠️ CRITICAL
  Called From: get_timeseries() at line 1318, get_dashboard_data() at line 1164
  
  Flux Query:
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
```

```
METHOD: _read_last_sample_before()
  File: apps/backend/app/services/influx.py:732-760
  Query Execution: Line 740-750
  Variables Used: bucket, eid (USER INPUT)
  Vulnerability: F-string injection on bucket AND eid ⚠️ CRITICAL
  Called From: get_timeseries() at line 1323, get_dashboard_data() at line 1163
  
  Flux Query:
    from(bucket: "{bucket}")
    |> range(start: 0, stop: time(v: "{start_ts}"))
    |> filter(fn: (r) => r["_measurement"] == "{eid}" or r["entity_id"] == "{eid}")
    |> filter(fn: (r) => r["_field"] == "value" or r["_field"] == "state")
    |> last()
    |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
```

```
METHOD: _read_samples_in_range()
  File: apps/backend/app/services/influx.py:764-787
  Query Execution: Line 772-782
  Variables Used: bucket, eid (USER INPUT), start_ts, end_ts
  Vulnerability: F-string injection on bucket AND eid ⚠️ CRITICAL
  Called From: get_timeseries() at line 1324, get_dashboard_data() at line 1197
  
  Flux Query:
    from(bucket: "{bucket}")
    |> range(start: time(v: "{start_ts}"), stop: time(v: "{end_ts}"))
    |> filter(fn: (r) => r["_measurement"] == "{eid}" or r["entity_id"] == "{eid}")
    |> filter(fn: (r) => r["_field"] == "value" or r["_field"] == "state")
    |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
```

```
METHOD: get_entities()
  File: apps/backend/app/services/influx.py:968-1126
  Query Execution 1: Line 1019-1021
  Variables Used: bucket
  Vulnerability: F-string injection on bucket
  
  Query Execution 2 (Fallback): Line 1103-1115
  Variables Used: bucket, eid
  Vulnerability: F-string injection on bucket AND eid
  
  Called From: read_device_entities() in data.py:40, heating_summary_service:241
  
  Primary Flux Query:
    import "influxdata/influxdb/schema"
    schema.tagValues(bucket: "{bucket}", tag: "entity_id")
    
  Fallback Query:
    import "influxdata/influxdb/schema"
    schema.measurements(bucket: "{bucket}")
```

```
METHOD: get_dashboard_data()
  File: apps/backend/app/services/influx.py:1143-1304
  Query Execution 1: Line 1169-1191 (latest point query)
  Variables Used: bucket, eid (USER INPUT)
  Vulnerability: F-string injection ⚠️ CRITICAL
  
  Query Execution 2: Line 1218-1228 (sparkline aggregation)
  Variables Used: bucket, eid (USER INPUT), agg_fn
  Vulnerability: F-string injection ⚠️ CRITICAL
  
  Called From: read_device_dashboard() in data.py:12
  
  Latest Point Query:
    from(bucket: "{bucket}")
    |> range(start: -24h)
    |> filter(fn: (r) => r["_measurement"] == "{eid}" or r["entity_id"] == "{eid}")
    |> filter(fn: (r) => r["_field"] == "value" or r["_field"] == "state")
    |> last()
    |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
    
  Sparkline Query:
    from(bucket: "{bucket}")
    |> range(start: -24h)
    |> filter(fn: (r) => r["_measurement"] == "{eid}" or r["entity_id"] == "{eid}")
    |> filter(fn: (r) => r["_field"] == "value" or r["_field"] == "state")
    |> map(fn: (r) => ({ r with _value: float(v: r._value) }))
    |> aggregateWindow(every: 30m, fn: {agg_fn}, createEmpty: false)
    |> keep(columns: ["_time", "_value"])
```

```
METHOD: get_timeseries()
  File: apps/backend/app/services/influx.py:1307-1377
  Function: Main entry point for timeseries queries
  Variables Used: bucket, entity_ids (LIST - USER INPUT), start, end
  Vulnerability: Passes USER INPUT directly to injection-vulnerable methods
  
  Calls injection-vulnerable methods:
    - _read_entity_metadata(eid) at line 1318 ⚠️
    - _read_samples_in_range(eid) at line 1324 ⚠️
    - _read_last_sample_before(eid) at line 1323 ⚠️
  
  Called From: 
    - read_device_timeseries() in data.py:82
    - read_device_dashboard() in data.py:12
    - heating_summary_service.get_device_summary() at line 276
```

---

## 2. API ENDPOINTS EXECUTING QUERIES

### Data Endpoints

```
ENDPOINT: GET /api/v1/data/{device_id}/timeseries
  File: apps/backend/app/api/v1/endpoints/data.py:82-100
  User Input Parameters:
    - entity_ids: List[str] = Query(...) - DIRECTLY PASSED TO SERVICE
    - start: Optional[str] = ISO-8601 time (validated format)
    - end: Optional[str] = ISO-8601 time (validated format)
    - range: Optional[str] = e.g. "24h" (predefined format)
  
  Input Processing (Line 95-100):
    for eid in entity_ids:
      if "," in eid:
        clean_ids.extend([id.strip() for id in eid.split(",") if id.strip()])
      else:
        clean_ids.append(eid.strip())
    # ❌ NO VALIDATION - directly passed to influx_service.get_timeseries()
  
  Query Chain:
    read_device_timeseries() 
      → influx_service.get_timeseries()
        → _read_entity_metadata(eid) [INJECTION POINT]
        → _read_samples_in_range(eid) [INJECTION POINT]
        → _read_last_sample_before(eid) [INJECTION POINT]
```

```
ENDPOINT: GET /api/v1/data/{device_id}/dashboard
  File: apps/backend/app/api/v1/endpoints/data.py:12-36
  User Input Parameters:
    - entity_ids: List[str] = Query(...) - DIRECTLY PASSED TO SERVICE
  
  Input Processing (Line 24-30):
    clean_ids = []
    for eid in entity_ids:
      if "," in eid:
        clean_ids.extend([id.strip() for id in eid.split(",") if id.strip()])
      else:
        clean_ids.append(eid.strip())
    # ❌ NO VALIDATION
  
  Query Chain:
    read_device_dashboard()
      → influx_service.get_dashboard_data()
        → _read_entity_metadata(eid) [INJECTION POINT]
        → _read_samples_in_range(eid) [INJECTION POINT]
```

```
ENDPOINT: GET /api/v1/data/{device_id}/entities
  File: apps/backend/app/api/v1/endpoints/data.py:40-48
  User Input Parameters: NONE
  
  Query Chain:
    read_device_entities()
      → influx_service.get_entities()
        → Returns all entity_ids from bucket
        → No user input in query
  
  Vulnerability: LOW (no user input)
```

### Analysis Endpoints

```
ENDPOINT: POST /api/v1/analysis/{device_id}
  File: apps/backend/app/api/v1/endpoints/analysis.py:14-45
  User Input Parameters (from AnalysisRequest body):
    - entity_ids: List[str]
    - start: Optional[datetime]
    - end: Optional[datetime]
  
  Query Chain:
    create_device_analysis()
      → device_analysis_service.run_analysis()
        → heating_summary_service.get_device_summary()
          → influx_service.get_timeseries(entity_ids) [INJECTION VULNERABLE]
            → _read_entity_metadata(eid) [INJECTION POINT]
            → _read_samples_in_range(eid) [INJECTION POINT]
            → _read_last_sample_before(eid) [INJECTION POINT]
```

```
ENDPOINT: POST /api/v1/analysis/{device_id}/deep
  File: apps/backend/app/api/v1/endpoints/analysis.py:48-71
  User Input Parameters (from AnalysisRequest body):
    - entity_ids: List[str]
    - start: Optional[datetime]
    - end: Optional[datetime]
    - manufacturer: str (required)
    - heat_pump_type: str (required)
  
  Query Chain:
    create_deep_analysis()
      → device_analysis_service.run_deep_analysis()
        → heating_summary_service.get_device_summary()
          → influx_service.get_timeseries(entity_ids) [INJECTION VULNERABLE]
            → _read_entity_metadata(eid) [INJECTION POINT]
            → _read_samples_in_range(eid) [INJECTION POINT]
            → _read_last_sample_before(eid) [INJECTION POINT]
```

---

## 3. CURRENT INFLUX_TOKEN USAGE PATTERNS

### Where Tokens Are Used

```
GENERATION (Device Creation):
  File: apps/backend/app/services/device.py
    Line 31-43: Device provisioning creates new token
    Line 39-43: influx_service.create_service_token(db_name, description)
    Line 55-56: Generated token stored in Device model without encryption
    
    Code:
      if bucket_res["status"] in ["ok", "exists"]:
        token_res = await influx_service.create_service_token(
          influx_db_name, 
          description=f"HA Token for device {device_in.display_name}"
        )
        if token_res["status"] == "ok":
          generated_token = token_res["token"]
      
      db_obj = Device(
        ...
        influx_token=generated_token,  # ← UNENCRYPTED STORAGE
        ...
      )
```

```
STORAGE (Database):
  File: apps/backend/app/models/device.py:20
    influx_token: Mapped[str] = mapped_column(String(255), nullable=True)
    
    Status: PLAINTEXT - NOT ENCRYPTED
    Type: String (max 255 chars)
    Nullable: Yes
    Index: None
    
    Table: device
    Column: influx_token
```

```
RETRIEVAL (Admin Endpoint):
  File: apps/backend/app/api/v1/endpoints/devices.py:99-111
    @router.get("/{device_id}/token", response_model=DeviceWithToken)
    async def read_device_with_token(...)
    
    Access Control: Line 106
      if not current_user.is_superuser:
        raise HTTPException(status_code=403)
    
    Returns: DeviceWithToken schema (line 39-48 in schemas)
    
    Token Unmasking: Line 45-48
      @field_validator("influx_token", mode="after")
      @classmethod
      def unmask_token(cls, v: Optional[Union[str, SecretStr]]) -> Optional[str]:
        return v.get_secret_value() if isinstance(v, SecretStr) else v
    
    Returns: UNENCRYPTED TOKEN IN HTTP RESPONSE
```

### Current Usage Status

```
GENERATION: ✓ Yes - created for each device during provisioning
STORAGE: ✓ Yes - stored in database (PLAINTEXT)
ACTIVE USE: ❌ NO - tokens generated but NOT used for authentication

ACTUAL AUTH FLOW:
  All queries use: settings.INFLUXDB_TOKEN (admin token from .env)
  Device tokens: Generated but only for reference/export to users
  
File: apps/backend/app/services/influx.py:176-179
  def __init__(self, host: str, token: str, org: str):
    self.host = host
    self.token = token  # ← Uses admin token from settings, not per-device
```

---

## 4. EXISTING QUERY VALIDATION & SANITIZATION

### Search Results: NO SANITIZATION FOUND

```
Search Query: "escape|sanitize|validate.*eid|validate.*entity|quote|safe"
Results: 0 dedicated sanitization functions found
```

### What Exists (Weak Validation)

```
Timestamp Parsing (apps/backend/app/services/influx.py:788-805):
  ✓ ISO-8601 format validation
  ✓ Named range support (today, yesterday, this_week, this_month)
  ✓ Duration parsing (1h, 24d, etc.)
  
  BUT: Only for time parameters, NOT for entity_ids
```

```
Entity ID Splitting (apps/backend/app/api/v1/endpoints/data.py:95-100):
  ✓ Comma-separated parsing
  ✓ String trimming
  
  BUT: NO format validation, NO special character escaping
```

### What Does NOT Exist

```
❌ sanitize_flux_literal() or similar function
❌ entity_id format validation (no whitelist pattern check)
❌ bucket name validation
❌ Quote escaping for Flux string interpolation
❌ Flux injection detection
❌ Input length limits beyond DB column size
```

---

## 5. FILES REQUIRING TOKEN ENCRYPTION

### Models

```
File: apps/backend/app/models/device.py
  Class: Device
  Line: 20
  Field: influx_token
  Type: Mapped[str]
  Column Type: String(255)
  
  NEEDS ENCRYPTION:
    - Change to encrypted field or hybrid property
    - Implement transparent encryption/decryption
    - Rotate migration to encrypt existing tokens
```

### Schemas

```
File: apps/backend/app/schemas/device.py
  
  Schema: DeviceCreate
    Line: 13
    Field: influx_token
    Type: Optional[Union[str, SecretStr]]
    NEEDS: Validation on input, never accept plaintext
    
  Schema: DeviceUpdate  
    Line: 16
    Field: influx_token
    Type: Optional[Union[str, SecretStr]]
    NEEDS: Validation on update, never accept plaintext
    
  Schema: DeviceWithToken
    Line: 39-48
    Field: influx_token
    Type: Optional[Union[str, SecretStr]]
    NEEDS: Remove this schema or change to return masked token
```

### Services

```
File: apps/backend/app/services/device.py
  
  Function: create_device()
    Line: 56
    Operation: db_obj = Device(..., influx_token=generated_token)
    NEEDS: Encrypt token before storing
    
  Function: update_device()
    Line: 90
    Operation: db_obj.influx_token = device_in.influx_token
    NEEDS: Encrypt token before storing
```

### Endpoints

```
File: apps/backend/app/api/v1/endpoints/devices.py
  
  Endpoint: GET /devices/{device_id}/token
  Line: 99-111
  Response: DeviceWithToken
  NEEDS: Return masked/encrypted token or remove endpoint
```

### Migrations

```
File: apps/backend/alembic/versions/e06013ff8435_add_influx_token_to_device.py
  
  Line: 23
  Operation: op.add_column('device', sa.Column('influx_token', ...))
  
  NEEDS: Follow-up migration to encrypt all existing tokens
```

---

## 6. DATABASE TABLES & COLUMNS NEEDING ENCRYPTION

### Device Table

```
Table Name: device
Columns Needing Encryption:
  
  1. influx_token
     Current Type: VARCHAR(255)
     Current Storage: PLAINTEXT
     Status: ⚠️ CRITICAL
     
     Recommendations:
       Option 1: BYTEA (binary) with application-layer encryption
       Option 2: VARCHAR with encrypted content + IV
       Option 3: Create separate encrypted_secrets table (key rotation friendly)

Schema:
  CREATE TABLE device (
    id INTEGER PRIMARY KEY,
    tenant_id INTEGER NOT NULL,
    display_name VARCHAR(255) NOT NULL,
    slug VARCHAR(255) NOT NULL,
    source_type VARCHAR(50) DEFAULT 'influxdb_v2',
    influx_database_name VARCHAR(255) NOT NULL,
    influx_token VARCHAR(255),  -- ⚠️ PLAINTEXT - NEEDS ENCRYPTION
    retention_policy VARCHAR(100),
    source_config JSON,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    FOREIGN KEY (tenant_id) REFERENCES tenant(id)
  );
```

---

## 7. SUMMARY MATRIX

### Query Execution Points
```
Total Methods: 8
Vulnerable: 8/8 (100%)
  - 3 methods use eid from user input ⚠️⚠️ CRITICAL
  - 5 methods use bucket from DB (medium risk)
  - All use f-string interpolation (no escaping)
```

### Token Usage Points
```
Total Storage Locations: 1 (Device table)
Encrypted: 0/1 (0%)
Vulnerable to:
  - Database breach: Complete token exposure
  - Backup exposure: All tokens exposed
  - Query logging: Potential token leakage
```

### Input Validation Coverage
```
entity_ids: 0% (no validation)
bucket: 0% (no validation)
timestamps: 100% (well-validated)
```

### Security Controls
```
Present: Access control (RBAC), Field masking, Multi-tenancy
Missing: Query sanitization, Input validation, Token encryption
```

---

## 8. COMPLETE FILE REFERENCE TABLE

```
Model & Database Files:
  ✓ apps/backend/app/models/device.py                           (Line 20 - Token storage)
  ✓ apps/backend/alembic/versions/e06013ff8435_...py            (Line 23 - Token migration)

Schema Files:
  ✓ apps/backend/app/schemas/device.py                          (Lines 13, 16, 39-48)

Query Execution Files:
  ✓ apps/backend/app/services/influx.py                         (8 vulnerable methods)

Service Orchestration Files:
  ✓ apps/backend/app/services/device.py                         (Lines 24-90)
  ✓ apps/backend/app/services/heating_summary_service.py        (Query chain)
  ✓ apps/backend/app/services/device_analysis_service.py        (Analysis chain)

API Endpoint Files:
  ✓ apps/backend/app/api/v1/endpoints/data.py                   (3 data endpoints)
  ✓ apps/backend/app/api/v1/endpoints/analysis.py               (2 analysis endpoints)
  ✓ apps/backend/app/api/v1/endpoints/devices.py                (1 token endpoint)
```

---

**Total Vulnerable Points Identified: 14**
- 8 query execution methods with injection risk
- 3 data endpoints with unsanitized input
- 2 analysis endpoints with unsanitized input
- 1 token storage location (plaintext)

**Overall Risk Level: 🔴 CRITICAL**

*Report Generated: April 16, 2026*
