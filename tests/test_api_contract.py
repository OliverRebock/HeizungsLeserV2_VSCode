import pytest
from httpx import AsyncClient
from .conftest import get_auth_header

@pytest.mark.asyncio
async def test_devices_list_and_detail_contract(client: AsyncClient, platform_admin, test_tenant):
    headers = get_auth_header(platform_admin.id)
    # Create two devices
    for name in ["Contract A", "Contract B"]:
        device_data = {
            "display_name": name,
            "influx_database_name": f"db_{name.lower().replace(' ', '_')}",
            "tenant_id": test_tenant.id,
            "is_active": True,
            "source_type": "influxdb_v2"
        }
        res = await client.post("/api/v1/devices/", json=device_data, headers=headers)
        assert res.status_code == 200

    # List endpoint
    list_res = await client.get("/api/v1/devices/", headers=headers)
    assert list_res.status_code == 200
    devices = list_res.json()
    assert isinstance(devices, list)
    assert any(d.get("display_name") == "Contract A" for d in devices)

    # Detail endpoint
    dev_id = devices[0]["id"]
    detail_res = await client.get(f"/api/v1/devices/{dev_id}", headers=headers)
    assert detail_res.status_code == 200
    dev = detail_res.json()
    expected_fields = [
        "id", "display_name", "slug", "tenant_id", "is_active", "source_type",
        "influx_database_name", "created_at", "updated_at", "last_seen", "is_online"
    ]
    for field in expected_fields:
        assert field in dev, f"Missing field {field} in Device response"
    assert "influx_token" in dev

@pytest.mark.asyncio
async def test_users_list_contract_and_permissions(client: AsyncClient, platform_admin):
    headers = get_auth_header(platform_admin.id)
    res = await client.get("/api/v1/users/", headers=headers)
    assert res.status_code in (200, 204)  # allow empty list or no content
    if res.status_code == 200:
        users = res.json()
        assert isinstance(users, list)
        if users:
            u = users[0]
            assert "id" in u and "email" in u and "is_active" in u
