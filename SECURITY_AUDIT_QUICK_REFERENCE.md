# InfluxDB Security Audit - Quick Reference

## 🔴 CRITICAL: Flux Query Injection Points

### Location: `apps/backend/app/services/influx.py`

```
Line 138-141    | get_last_data_timestamp()         | f-string injection: bucket
Line 694-708    | _read_entity_metadata()           | f-string injection: bucket, eid ⚠️⚠️
Line 740-750    | _read_last_sample_before()        | f-string injection: bucket, eid ⚠️⚠️
Line 772-782    | _read_samples_in_range()          | f-string injection: bucket, eid ⚠️⚠️
Line 1019-1021  | get_entities()                    | f-string injection: bucket
Line 1103-1115  | get_entities() fallback           | f-string injection: bucket, eid
Line 1169-1191  | get_dashboard_data()              | f-string injection: bucket, eid ⚠️⚠️
Line 1218-1228  | get_dashboard_data() sparkline    | f-string injection: bucket, eid ⚠️⚠️
```

**⚠️⚠️ = Most dangerous - accessed from user-provided entity_ids**

---

## 🔴 HIGH: Plaintext Token Storage

### Model Definition
```
File: apps/backend/app/models/device.py:20
Field: influx_token
Type: String(255) 
Status: PLAINTEXT - NOT ENCRYPTED
```

### Schema Definitions
```
File: apps/backend/app/schemas/device.py
  Line 13: DeviceCreate - accepts influx_token
  Line 16: DeviceUpdate - accepts influx_token  
  Line 39-48: DeviceWithToken - UNMASKS token for admin response
```

### Service Storage
```
File: apps/backend/app/services/device.py
  Line 56: create_device() stores token unencrypted
  Line 90: update_device() stores token unencrypted
```

### Database Migration
```
File: apps/backend/alembic/versions/e06013ff8435_add_influx_token_to_device.py:23
Event: Initial addition of plaintext token column
```

---

## 🔵 MEDIUM: Token Exposure via API

### Admin Token Endpoint
```
File: apps/backend/app/api/v1/endpoints/devices.py
  Line 99-111: GET /api/v1/devices/{device_id}/token
  Returns: DeviceWithToken schema with UNMASKED token
  Auth: Admin only (is_superuser check required)
  Danger: Unencrypted token in HTTP response
```

---

## 🟡 Query Entry Points (User Input)

### Data Endpoint
```
File: apps/backend/app/api/v1/endpoints/data.py
  Line 12-36: GET /api/v1/data/{device_id}/dashboard
    Param: entity_ids (List[str]) → passed to get_dashboard_data()
    
  Line 40-48: GET /api/v1/data/{device_id}/entities  
    No params → called without entity_ids
    
  Line 82-100: GET /api/v1/data/{device_id}/timeseries
    Param: entity_ids (List[str]) → passed to get_timeseries()
    Param: start, end, range (time params, validated)
    
    Processing: Lines 95-100
      - Splits comma-separated entity_ids
      - NO validation on entity_id format
      - Directly passed to influx_service
```

### Analysis Endpoints
```
File: apps/backend/app/api/v1/endpoints/analysis.py
  Line 14-45: POST /api/v1/analysis/{device_id}
    Body param: entity_ids (from AnalysisRequest)
    Flow: device_analysis_service → heating_summary_service → influx_service
    
  Line 48-71: POST /api/v1/analysis/{device_id}/deep
    Body param: entity_ids (from AnalysisRequest)
    Flow: device_analysis_service → heating_summary_service → influx_service
```

---

## 🟢 Security Controls Present

### Access Control
```
✅ apps/backend/app/api/v1/endpoints/data.py
   - Line 26-27: check_tenant_access() validates user can access device tenant
   
✅ apps/backend/app/api/v1/endpoints/analysis.py
   - Line 31, 68: check_tenant_access() validates user can access device tenant
   
✅ apps/backend/app/api/v1/endpoints/devices.py
   - Line 99-111: is_superuser check for token endpoint
```

### Field-Level Masking
```
✅ apps/backend/app/schemas/device.py
   - Line 24-33: Device schema does NOT include influx_token
   - Prevents accidental exposure in list responses
```

### Multi-Tenancy
```
✅ All queries scoped to device.influx_database_name (tenant-specific bucket)
✅ User-tenant relationship validated before query execution
```

---

## 📊 Input Validation Gap Analysis

### Current Validation: ❌ NONE

| Input | Endpoint | Validation |
|-------|----------|-----------|
| entity_ids | /data/timeseries | ❌ Split by comma, no format check |
| entity_ids | /data/dashboard | ❌ Split by comma, no format check |
| entity_ids | /analysis | ❌ Passed through heating_summary → no check |
| bucket | internal method | ❌ From device.influx_database_name - trusts DB value |

### What SHOULD Be Validated:
```
entity_ids: Must match /^[a-z0-9._]+$/i (alphanumeric, dots, underscores only)
bucket: Must match /^[a-z0-9_-]+$/i (alphanumeric, underscores, hyphens only)
```

---

## 🔍 Data Flow: User Input → Query Execution

### Scenario: GET /api/v1/data/1/timeseries?entity_ids=sensor.test

```
1. Endpoint receives entity_ids parameter (user-controlled)
   File: apps/backend/app/api/v1/endpoints/data.py:92

2. Tenant access check ✓ SECURE
   File: apps/backend/app/api/v1/endpoints/data.py:89

3. Split by comma, trim whitespace ⚠️ NO VALIDATION
   File: apps/backend/app/api/v1/endpoints/data.py:95-100

4. Pass to influx_service.get_timeseries()
   File: apps/backend/app/services/influx.py:1307

5. For each eid in entity_ids:
   a) Call _read_entity_metadata(eid) 
      Line 1318 → uses eid at Line 697-698 in f-string ⚠️⚠️ INJECTION
      
   b) Call _read_samples_in_range(eid)
      Line 1324 → uses eid at Line 775 in f-string ⚠️⚠️ INJECTION
      
   c) Embed results in Flux query

6. Execute query against InfluxDB
   ❌ VULNERABLE TO INJECTION
```

---

## 🎯 Vulnerability Severity Matrix

```
┌─────────────────────────┬──────────┬─────────────────┐
│ Vulnerability           │ Severity │ Affected Scope  │
├─────────────────────────┼──────────┼─────────────────┤
│ Flux Query Injection    │ CRITICAL │ All authenticated│
│ (via entity_ids)        │          │ users querying  │
│                         │          │ timeseries/     │
│                         │          │ dashboard/      │
│                         │          │ analysis        │
│─────────────────────────┼──────────┼─────────────────┤
│ Plaintext Token Storage │ HIGH     │ Database breach │
│                         │          │ scenario only   │
│─────────────────────────┼──────────┼─────────────────┤
│ Unmasked Token via API  │ MEDIUM   │ Admin users     │
│                         │          │ (limited exposure│
│                         │          │ via HTTP)       │
│─────────────────────────┼──────────┼─────────────────┤
│ No Input Validation     │ HIGH     │ Enables all     │
│                         │          │ injection attacks│
└─────────────────────────┴──────────┴─────────────────┘
```

---

## 📋 Complete File Inventory

### Model & Schema Files
```
✓ apps/backend/app/models/device.py           - Token storage model
✓ apps/backend/app/schemas/device.py          - Token schemas  
✓ apps/backend/alembic/versions/...           - Token migration
```

### Service Files  
```
✓ apps/backend/app/services/influx.py         - Query execution (8 injection points)
✓ apps/backend/app/services/device.py         - Token storage service
✓ apps/backend/app/services/heating_summary_service.py - Query orchestration
✓ apps/backend/app/services/device_analysis_service.py - Analysis service
```

### Endpoint Files
```
✓ apps/backend/app/api/v1/endpoints/data.py       - Data query endpoints
✓ apps/backend/app/api/v1/endpoints/analysis.py   - Analysis endpoints
✓ apps/backend/app/api/v1/endpoints/devices.py    - Device management (token endpoint)
```

---

## 🚀 Quickstart: What to Audit First

1. **MOST CRITICAL:** [apps/backend/app/services/influx.py](apps/backend/app/services/influx.py)
   - Lines 694-708, 740-750, 772-782 (3 methods with heaviest user input)

2. **SECOND:** [apps/backend/app/models/device.py](apps/backend/app/models/device.py)
   - Line 20: Token encryption implementation

3. **THIRD:** [apps/backend/app/api/v1/endpoints/data.py](apps/backend/app/api/v1/endpoints/data.py)
   - Lines 95-100: Add entity_id validation

---

## 📞 References

- Main Service: [apps/backend/app/services/influx.py](apps/backend/app/services/influx.py)
- Device Model: [apps/backend/app/models/device.py](apps/backend/app/models/device.py)
- Full Audit Report: [SECURITY_AUDIT_INFLUXDB.md](SECURITY_AUDIT_INFLUXDB.md)

---

*Last Updated: April 16, 2026*
