# InfluxDB Security Audit - Comprehensive Findings Report

**Date:** April 16, 2026  
**Scope:** All endpoints/services executing Flux queries, token usage, encryption needs  

---

## EXECUTIVE SUMMARY

### Critical Issues Identified:

1. **Flux Query Injection Vulnerability (CRITICAL)** - User-controlled `entity_id` values directly interpolated into Flux queries via f-strings
2. **Unencrypted Token Storage (HIGH)** - `influx_token` stored in plaintext in database
3. **No Query Sanitization/Validation (HIGH)** - Zero validation on bucket names and entity IDs before query execution
4. **Token Exposure via API (MEDIUM)** - Token endpoint returns unmasked tokens to authorized users

---

## 1. FLUX QUERY EXECUTION POINTS

### 1.1 Direct Query Injection Vulnerabilities

**File: [apps/backend/app/services/influx.py](apps/backend/app/services/influx.py)**

#### Vulnerability Pattern:
F-strings with **unvalidated `eid` (entity_id)** and **bucket** parameters directly embedded in Flux queries.

#### Injection Points (Line Numbers):

| Method | Lines | Vulnerable Parameters | Severity |
|--------|-------|----------------------|----------|
| `get_last_data_timestamp()` | [138-141](apps/backend/app/services/influx.py#L138-L141) | `bucket` | CRITICAL |
| `_read_entity_metadata()` | [694-708](apps/backend/app/services/influx.py#L694-L708) | `bucket`, `eid` | CRITICAL |
| `_read_last_sample_before()` | [740-750](apps/backend/app/services/influx.py#L740-L750) | `bucket`, `eid` | CRITICAL |
| `_read_samples_in_range()` | [772-782](apps/backend/app/services/influx.py#L772-L782) | `bucket`, `eid` | CRITICAL |
| `get_entities()` | [1019-1021](apps/backend/app/services/influx.py#L1019-L1021) | `bucket` | HIGH |
| `get_entities()` (fallback) | [1103-1115](apps/backend/app/services/influx.py#L1103-L1115) | `bucket`, `eid` | HIGH |
| `get_dashboard_data()` | [1169-1191](apps/backend/app/services/influx.py#L1169-L1191) | `bucket`, `eid` | CRITICAL |
| `get_dashboard_data()` (sparkline) | [1218-1228](apps/backend/app/services/influx.py#L1218-L1228) | `bucket`, `eid` | CRITICAL |

#### Example Vulnerable Code:

```python
# Line 694-708 (apps/backend/app/services/influx.py)
metadata_query = f'''
    from(bucket: "{bucket}")
    |> range(start: 0, stop: time(v: "{end_ts}"))
    |> filter(fn: (r) => r["_measurement"] == "{eid}" or r["entity_id"] == "{eid}")
    |> filter(fn: (r) =>
        r["_field"] == "friendly_name_str" or
        ...
    )
'''
```

**Attack Vector:** An authenticated user can inject Flux syntax through entity_id parameter:
```
entity_id: "sensor.test") |> delete()"
```

This would inject a delete operation into the query.

---

## 2. INFLUX_TOKEN USAGE & STORAGE

### 2.1 Token Storage Locations

#### Database Model:
**File: [apps/backend/app/models/device.py](apps/backend/app/models/device.py#L20)**
```python
influx_token: Mapped[str] = mapped_column(String(255), nullable=True)
```
- **Status:** Stored in **PLAINTEXT** - NOT ENCRYPTED
- **Size:** Limited to 255 characters
- **Nullable:** Yes (tokens optional)

#### Database Migration:
**File: [apps/backend/alembic/versions/e06013ff8435_add_influx_token_to_device.py](apps/backend/alembic/versions/e06013ff8435_add_influx_token_to_device.py#L23)**
- Migration adds plaintext token column

### 2.2 Token Usage Patterns

#### Token Generation (Device Provisioning):
**File: [apps/backend/app/services/device.py](apps/backend/app/services/device.py#L24-L56)**
- Line 39-43: Token created via `influx_service.create_service_token()`
- Line 55: Token stored in database without encryption
- Used only during device creation; stored for reference

#### Token Access Points:

**File: [apps/backend/app/api/v1/endpoints/devices.py](apps/backend/app/api/v1/endpoints/devices.py#L99-L111)**
```python
@router.get("/{device_id}/token", response_model=DeviceWithToken)
async def read_device_with_token(...)
```
- **Line 99-111:** `/api/v1/devices/{device_id}/token` endpoint
- **Protection:** Superuser/admin only (`check current_user.is_superuser`)
- **Returns:** Unmasked token via `DeviceWithToken` schema
- **Line 106:** Uses unmask validator to expose full token

#### Schema Token Handling:

**File: [apps/backend/app/schemas/device.py](apps/backend/app/schemas/device.py)**

1. **`Device` schema (line 24-33):** Token field NOT included - secure by default
2. **`DeviceCreate` schema (line 13):** Accepts optional token via `Union[str, SecretStr]`
3. **`DeviceUpdate` schema (line 16):** Accepts optional token updates
4. **`DeviceWithToken` schema (line 39-48):** 
   - Special variant that returns UNMASKED token
   - Has validator at line 45-48: `unmask_token()` returns plaintext
   - Response model for admin-only endpoint

### 2.3 Current Token Usage

**Status:** Generated but NOT actively used for authentication
- Admin token (from config) used for all queries: `settings.INFLUXDB_TOKEN`
- Device tokens generated but stored for reference only
- No per-device auth implementation

---

## 3. QUERY VALIDATION & SANITIZATION

### 3.1 Current Security Mechanisms

**Search Results:** Only 2 matches for "escape", "sanitize", "validate" patterns
- No dedicated query sanitization function exists
- No validation/escape utilities found

**What EXISTS:**
- Timestamp parsing with ISO-8601 validation [Line 788-805](apps/backend/app/services/influx.py#L788-L805)
- Time range resolution (named ranges like 'today', 'yesterday', 'this_week')
- Numeric value parsing from strings

**What DOES NOT EXIST:**
- No `sanitize_flux_literal()` function
- No entity_id validation (alphanumeric + dots only)
- No bucket name validation
- No quote escaping for Flux string interpolation

### 3.2 Current Input Handling

#### Entity ID Input Flow:
1. **Endpoint receives:** `/api/v1/data/{device_id}/timeseries?entity_ids=sensor.test`
2. **Processing:** [apps/backend/app/api/v1/endpoints/data.py](apps/backend/app/api/v1/endpoints/data.py#L82-L100)
   - Line 95-100: Simple string splitting by comma, no validation
   - No alphanumeric check
   - No reserved character check
3. **Passed to:** `influx_service.get_timeseries()` [apps/backend/app/services/influx.py](apps/backend/app/services/influx.py#L1307-L1360)
4. **Direct injection:** String directly embedded in f-string at line 1334

---

## 4. ENDPOINTS & SERVICES EXECUTING QUERIES

### 4.1 API Endpoints (Query Execution Points)

**File: [apps/backend/app/api/v1/endpoints/data.py](apps/backend/app/api/v1/endpoints/data.py)**

| Endpoint | Method | Line | Executes Query |
|----------|--------|------|-----------------|
| `/api/v1/data/{device_id}/entities` | GET | [40-48](apps/backend/app/api/v1/endpoints/data.py#L40-L48) | Via `get_entities()` |
| `/api/v1/data/{device_id}/dashboard` | GET | [12-36](apps/backend/app/api/v1/endpoints/data.py#L12-L36) | Via `get_dashboard_data()` |
| `/api/v1/data/{device_id}/timeseries` | GET | [82-100](apps/backend/app/api/v1/endpoints/data.py#L82-L100) | Via `get_timeseries()` |

**File: [apps/backend/app/api/v1/endpoints/analysis.py](apps/backend/app/api/v1/endpoints/analysis.py)**

| Endpoint | Method | Line | Query Chain |
|----------|--------|------|-------------|
| `/api/v1/analysis/{device_id}` | POST | [14-45](apps/backend/app/api/v1/endpoints/analysis.py#L14-L45) | `device_analysis_service.run_analysis()` → `heating_summary_service.get_device_summary()` → `influx_service.get_timeseries()` |
| `/api/v1/analysis/{device_id}/deep` | POST | [48-71](apps/backend/app/api/v1/endpoints/analysis.py#L48-L71) | `device_analysis_service.run_deep_analysis()` → `heating_summary_service.get_device_summary()` → `influx_service.get_timeseries()` |

### 4.2 Service Call Chain

```
API Endpoint
  ↓
device_analysis_service.run_analysis()
  ↓
heating_summary_service.get_device_summary()
  ↓
influx_service.get_timeseries()
  ↓
influx_service._read_entity_metadata()      [INJECTION POINT]
influx_service._read_samples_in_range()     [INJECTION POINT]
influx_service._read_last_sample_before()   [INJECTION POINT]
```

---

## 5. FILES NEEDING TOKEN ENCRYPTION

### 5.1 Models

| File | Field | Current Type | Issue |
|------|-------|--------------|-------|
| [apps/backend/app/models/device.py](apps/backend/app/models/device.py#L20) | `influx_token` | `String(255)` | **PLAINTEXT** - Needs encryption |

### 5.2 Schemas

| File | Schema | Field | Issue |
|------|--------|-------|-------|
| [apps/backend/app/schemas/device.py](apps/backend/app/schemas/device.py#L13) | `DeviceCreate` | `influx_token` | Accepts plaintext input |
| [apps/backend/app/schemas/device.py](apps/backend/app/schemas/device.py#L16) | `DeviceUpdate` | `influx_token` | Accepts plaintext input |
| [apps/backend/app/schemas/device.py](apps/backend/app/schemas/device.py#L39-L48) | `DeviceWithToken` | `influx_token` | Returns unmasked via validator |

### 5.3 Services

| File | Function | Usage |
|------|----------|-------|
| [apps/backend/app/services/device.py](apps/backend/app/services/device.py#L56) | `create_device()` | Stores token without encryption |
| [apps/backend/app/services/device.py](apps/backend/app/services/device.py#L90) | `update_device()` | Updates token without encryption |

### 5.4 Endpoints

| File | Endpoint | Returns |
|------|----------|---------|
| [apps/backend/app/api/v1/endpoints/devices.py](apps/backend/app/api/v1/endpoints/devices.py#L99-L111) | `GET /{device_id}/token` | Unencrypted token (admin-only) |

---

## 6. DATABASE TABLES & COLUMNS NEEDING ENCRYPTION

### 6.1 Device Table

```sql
CREATE TABLE device (
    id INTEGER PRIMARY KEY,
    influx_token VARCHAR(255),  -- ⚠️ PLAINTEXT - NEEDS ENCRYPTION
    ...
)
```

**Migration Location:** [apps/backend/alembic/versions/e06013ff8435_add_influx_token_to_device.py](apps/backend/alembic/versions/e06013ff8435_add_influx_token_to_device.py)

---

## 7. EXISTING SECURITY CONTROLS

### 7.1 Authentication & Authorization

✅ **RBAC Checks:**
- Endpoint: [apps/backend/app/api/v1/endpoints/analysis.py](apps/backend/app/api/v1/endpoints/analysis.py#L31)
  - `deps.check_tenant_access()` ensures user has tenant access
- Endpoint: [apps/backend/app/api/v1/endpoints/data.py](apps/backend/app/api/v1/endpoints/data.py#L26-27)
  - Same access control on all data endpoints

✅ **Admin-Only Token Access:**
- Endpoint: [apps/backend/app/api/v1/endpoints/devices.py](apps/backend/app/api/v1/endpoints/devices.py#L106)
  - `current_user.is_superuser` check required

✅ **Multi-Tenancy:**
- All devices scoped to tenants
- User-tenant relationship validated

### 7.2 Field-Level Masking

**Schema Handling:**
- Line 24-33 in [apps/backend/app/schemas/device.py](apps/backend/app/schemas/device.py)
  - Standard `Device` schema does NOT include `influx_token` field
  - Prevents accidental token exposure in list endpoints
- Line 39-48: `DeviceWithToken` schema only used by admin-protected endpoint

### 7.3 Input Processing

**Entity ID Handling:**
- Line 95-100 in [apps/backend/app/api/v1/endpoints/data.py](apps/backend/app/api/v1/endpoints/data.py)
  - Comma-separated values split and trimmed
  - ⚠️ But NO validation against allowed characters

---

## 8. ATTACK SCENARIOS

### 8.1 Flux Injection Attack

**Scenario:** Authenticated user queries timeseries with malicious entity_id

```bash
curl -X GET "http://localhost:8000/api/v1/data/1/timeseries" \
  -H "Authorization: Bearer <token>" \
  --data-urlencode 'entity_ids=sensor.test") |> delete()'
```

**Result:**
- Entity ID passed to [apps/backend/app/services/influx.py](apps/backend/app/services/influx.py#L1334)
- Injected into Flux query at line 1334:
  ```flux
  from(bucket: "test_bucket")
  |> filter(fn: (r) => r["_measurement"] == "sensor.test") |> delete()" or ...)
  ```
- InfluxDB would delete data from bucket

### 8.2 Token Exposure Attack

**Scenario:** Database breach or backup leak

- All `influx_token` values in `device` table are **plaintext**
- Attacker can use tokens to access InfluxDB directly
- No encryption-at-rest protection

### 8.3 Multi-Tenancy Bypass via Injection

**Scenario:** Tenant A queries another tenant's data via injection

- Potential but limited by bucket isolation in InfluxDB
- Each device has separate bucket (per code analysis)
- But cross-bucket queries possible if bucket name guessable

---

## 9. SUMMARY TABLE - ALL VULNERABLE FILES

| File | Issue | Line(s) | Severity |
|------|-------|---------|----------|
| [apps/backend/app/services/influx.py](apps/backend/app/services/influx.py) | Flux injection via eid in f-string | 694-708, 740-750, 772-782, 1169-1191, 1218-1228 | **CRITICAL** |
| [apps/backend/app/models/device.py](apps/backend/app/models/device.py#L20) | Plaintext token storage | 20 | **HIGH** |
| [apps/backend/app/schemas/device.py](apps/backend/app/schemas/device.py) | Token in create/update schemas without validation | 13, 16 | **HIGH** |
| [apps/backend/app/api/v1/endpoints/devices.py](apps/backend/app/api/v1/endpoints/devices.py#L99-L111) | Unencrypted token exposure | 99-111 | **MEDIUM** |
| [apps/backend/alembic/versions/e06013ff8435_add_influx_token_to_device.py](apps/backend/alembic/versions/e06013ff8435_add_influx_token_to_device.py#L23) | Plaintext migration | 23 | **HIGH** |

---

## 10. RECOMMENDATIONS (PRIORITY ORDER)

### Immediate (Security Critical):

1. **Implement Flux Query Sanitization**
   - Create `sanitize_flux_literal(value: str)` function
   - Escape quotes and special characters for Flux
   - Validate entity_ids against whitelist pattern: `^[a-z0-9._]+$`

2. **Encrypt influx_token in Database**
   - Use cryptography library or similar
   - Implement transparent encryption/decryption via SQLAlchemy hybrid property
   - Create migration to encrypt existing tokens

3. **Input Validation**
   - Add entity_id validation in endpoints
   - Add bucket name validation in services
   - Reject non-alphanumeric (except dots and underscores)

### Short-term (High Priority):

4. **Use Per-Device Authentication**
   - Implement per-device token in InfluxDB queries
   - Move from admin token to device-specific tokens
   - Implement token rotation

5. **Audit Logging**
   - Log all query execution with user/device context
   - Monitor for injection attempts

6. **Token Management**
   - Implement token expiration/rotation policy
   - Add token versioning in database

---

## 11. AFFECTED QUERY METHODS

All `_read_*` methods in [apps/backend/app/services/influx.py](apps/backend/app/services/influx.py) need sanitization:

- `get_last_data_timestamp()`
- `_read_entity_metadata()`
- `_read_last_sample_before()`
- `_read_samples_in_range()`
- `get_entities()`
- `get_dashboard_data()`
- All sparkline query builders

---

## 12. CERTIFICATION SUMMARY

✅ **Endpoints Identified:** 5 main query endpoints  
✅ **Query Execution Points:** 8 vulnerable methods  
✅ **Injection Vectors:** 2 user inputs (entity_id, bucket)  
✅ **Unencrypted Secrets:** 1 (influx_token)  
✅ **Affected Tables:** 1 (device table)  
✅ **Token Exposure Points:** 1 (admin endpoint returns plaintext)  

**Overall Risk Level:** 🔴 **CRITICAL - IMMEDIATE ACTION REQUIRED**

---

*Report Generated: April 16, 2026*
