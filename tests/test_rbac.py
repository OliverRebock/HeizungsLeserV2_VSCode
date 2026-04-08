import pytest
from httpx import AsyncClient
from .conftest import get_auth_header

@pytest.mark.asyncio
async def test_platform_admin_can_create_device(client: AsyncClient, platform_admin, test_tenant):
    headers = get_auth_header(platform_admin.id)
    device_data = {
        "display_name": "Test Device",
        "influx_database_name": "test_db",
        "tenant_id": test_tenant.id,
        "is_active": True,
        "source_type": "influxdb_v2"
    }
    response = await client.post("/api/v1/devices/", json=device_data, headers=headers)
    assert response.status_code == 200
    assert response.json()["display_name"] == "Test Device"

@pytest.mark.asyncio
async def test_tenant_admin_cannot_create_device(client: AsyncClient, tenant_admin, test_tenant):
    headers = get_auth_header(tenant_admin.id)
    device_data = {
        "display_name": "Illegal Device",
        "influx_database_name": "illegal_db",
        "tenant_id": test_tenant.id
    }
    response = await client.post("/api/v1/devices/", json=device_data, headers=headers)
    assert response.status_code == 403

@pytest.mark.asyncio
async def test_tenant_admin_can_manage_own_tenant_user(client: AsyncClient, tenant_admin, test_tenant, db_session):
    headers = get_auth_header(tenant_admin.id)
    # Create a user in the same tenant
    user_data = {
        "email": "new_user@example.com",
        "password": "password123",
        "full_name": "New User",
        "tenant_id": test_tenant.id,
        "role": "tenant_user"
    }
    response = await client.post("/api/v1/users/", json=user_data, headers=headers)
    assert response.status_code == 200
    
    user_id = response.json()["id"]
    # Can also reset password
    response = await client.post(f"/api/v1/users/{user_id}/reset-password", json={"new_password": "newpassword"}, headers=headers)
    assert response.status_code == 200

@pytest.mark.asyncio
async def test_tenant_admin_cannot_manage_other_tenant_user(client: AsyncClient, tenant_admin, db_session):
    from app.models.tenant import Tenant
    from .conftest import create_test_user
    
    other_tenant = Tenant(name="Other", slug="other")
    db_session.add(other_tenant)
    await db_session.commit()
    await db_session.refresh(other_tenant)
    
    other_user = await create_test_user(db_session, "other@example.com", role="tenant_user", tenant_id=other_tenant.id)
    
    headers = get_auth_header(tenant_admin.id)
    response = await client.get(f"/api/v1/users/{other_user.id}", headers=headers)
    assert response.status_code == 403

@pytest.mark.asyncio
async def test_tenant_user_cannot_manage_users(client: AsyncClient, tenant_user):
    headers = get_auth_header(tenant_user.id)
    response = await client.get("/api/v1/users/", headers=headers)
    assert response.status_code == 403
