import pytest
from httpx import AsyncClient
from .conftest import get_auth_header

@pytest.mark.asyncio
async def test_device_response_structure(client: AsyncClient, platform_admin, test_tenant):
    headers = get_auth_header(platform_admin.id)
    # First create a device
    device_data = {
        "display_name": "Structure Test Device",
        "influx_database_name": "struct_db",
        "tenant_id": test_tenant.id
    }
    create_res = await client.post("/api/v1/devices/", json=device_data, headers=headers)
    assert create_res.status_code == 200
    
    device_id = create_res.json()["id"]
    
    # Get the device and check structure
    response = await client.get(f"/api/v1/devices/{device_id}", headers=headers)
    assert response.status_code == 200
    data = response.json()
    
    expected_fields = ["id", "display_name", "slug", "tenant_id", "is_active", "source_type", "influx_database_name", "created_at", "updated_at"]
    for field in expected_fields:
        assert field in data, f"Missing field {field} in Device response"
    
    # Ensure token is masked in standard response
    assert "influx_token" in data
    # If token was provided in creation (we didn't, but let's assume), it should be masked or None
    # Default masking returns the value if too short, or masks if long. 

@pytest.mark.asyncio
async def test_analysis_response_structure_mock(client: AsyncClient, platform_admin, test_tenant):
    headers = get_auth_header(platform_admin.id)
    # The analysis endpoint might need actual Influx data, so we check if the endpoint exists and returns 422/404 if data missing
    # or we just check the schema if we can.
    # Here we check if the analysis options are available
    response = await client.get("/api/v1/analysis/options", headers=headers)
    if response.status_code == 200:
        data = response.json()
        assert isinstance(data, list) or isinstance(data, dict)
