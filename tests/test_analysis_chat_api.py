import pytest
from httpx import AsyncClient

from app.schemas.influx import DataPoint, Entity, TimeSeriesResponse
from app.services.heatpump_chat_service import heatpump_chat_service

from .conftest import get_auth_header


def make_entity(entity_id: str, friendly_name: str = "") -> Entity:
    return Entity(
        entity_id=entity_id,
        friendly_name=friendly_name,
        domain="sensor",
        data_kind="numeric",
        render_mode="history_line",
        chartable=True,
        source_table="state",
    )


def make_series(entity_id: str, friendly_name: str, value: float | None = None, state: str | None = None) -> TimeSeriesResponse:
    return TimeSeriesResponse(
        entity_id=entity_id,
        friendly_name=friendly_name,
        domain="sensor",
        data_kind="numeric",
        chartable=True,
        points=[DataPoint(ts="2026-04-19T06:00:00Z", value=value, state=state)],
        meta={},
    )


@pytest.mark.asyncio
async def test_chat_endpoint_fault_question_returns_anomaly_with_error_entities(
    client: AsyncClient, platform_admin, test_tenant, monkeypatch
):
    headers = get_auth_header(platform_admin.id)

    # Ensure test stays local and deterministic.
    monkeypatch.setattr(heatpump_chat_service, "openai_enabled", False)

    async def fake_get_entities(_device):
        return [
            make_entity("boiler_last_error_code", "Boiler Letzter Fehler"),
            make_entity("thermostat_alarm_status", "Thermostat Alarmstatus"),
            make_entity("boiler_current_flow_temperature", "Boiler Vorlauf"),
            make_entity("boiler_return_temperature", "Boiler Ruecklauf"),
        ]

    async def fake_get_timeseries(_device, entity_ids, _start, _end):
        mapping = {
            "boiler_last_error_code": make_series(
                "boiler_last_error_code",
                "Boiler Letzter Fehler",
                state="--(6256) 03.04.2026 11:50 - 03.04.2026 11:50",
            ),
            "thermostat_alarm_status": make_series(
                "thermostat_alarm_status",
                "Thermostat Alarmstatus",
                state="0",
            ),
            "boiler_current_flow_temperature": make_series(
                "boiler_current_flow_temperature",
                "Boiler Vorlauf",
                value=28.7,
            ),
            "boiler_return_temperature": make_series(
                "boiler_return_temperature",
                "Boiler Ruecklauf",
                value=25.1,
            ),
        }
        return {"series": [mapping[eid] for eid in entity_ids if eid in mapping]}

    monkeypatch.setattr("app.services.heatpump_chat_service.influx_service.get_entities", fake_get_entities)
    monkeypatch.setattr("app.services.heatpump_chat_service.influx_service.get_timeseries", fake_get_timeseries)

    device_data = {
        "display_name": "Chat API Device",
        "influx_database_name": "db_chat_api",
        "tenant_id": test_tenant.id,
        "is_active": True,
        "source_type": "influxdb_v2",
    }
    create_res = await client.post("/api/v1/devices/", json=device_data, headers=headers)
    assert create_res.status_code == 200
    device_id = create_res.json()["id"]

    chat_res = await client.post(
        f"/api/v1/analysis/{device_id}/chat",
        json={"question": "hat die heizung Fehler?", "language": "de"},
        headers=headers,
    )
    assert chat_res.status_code == 200

    body = chat_res.json()
    assert body["intent"] == "anomaly"
    assert "boiler_last_error_code" in body["used_entity_ids"]
    assert "thermostat_alarm_status" in body["used_entity_ids"]


@pytest.mark.asyncio
async def test_chat_endpoint_general_question_keeps_error_context_available(
    client: AsyncClient, platform_admin, test_tenant, monkeypatch
):
    headers = get_auth_header(platform_admin.id)

    monkeypatch.setattr(heatpump_chat_service, "openai_enabled", False)

    async def fake_get_entities(_device):
        return [
            make_entity("boiler_current_flow_temperature", "Boiler Vorlauf"),
            make_entity("boiler_last_error_code", "Boiler Letzter Fehler"),
            make_entity("boiler_return_temperature", "Boiler Ruecklauf"),
        ]

    async def fake_get_timeseries(_device, entity_ids, _start, _end):
        mapping = {
            "boiler_current_flow_temperature": make_series(
                "boiler_current_flow_temperature",
                "Boiler Vorlauf",
                value=29.4,
            ),
            "boiler_last_error_code": make_series(
                "boiler_last_error_code",
                "Boiler Letzter Fehler",
                state="--(6256)",
            ),
            "boiler_return_temperature": make_series(
                "boiler_return_temperature",
                "Boiler Ruecklauf",
                value=24.8,
            ),
        }
        return {"series": [mapping[eid] for eid in entity_ids if eid in mapping]}

    monkeypatch.setattr("app.services.heatpump_chat_service.influx_service.get_entities", fake_get_entities)
    monkeypatch.setattr("app.services.heatpump_chat_service.influx_service.get_timeseries", fake_get_timeseries)

    device_data = {
        "display_name": "Chat API Device General",
        "influx_database_name": "db_chat_api_general",
        "tenant_id": test_tenant.id,
        "is_active": True,
        "source_type": "influxdb_v2",
    }
    create_res = await client.post("/api/v1/devices/", json=device_data, headers=headers)
    assert create_res.status_code == 200
    device_id = create_res.json()["id"]

    chat_res = await client.post(
        f"/api/v1/analysis/{device_id}/chat",
        json={"question": "wie laeuft die heizung aktuell?", "language": "de"},
        headers=headers,
    )
    assert chat_res.status_code == 200

    body = chat_res.json()
    assert body["intent"] == "general"
    assert "boiler_last_error_code" in body["used_entity_ids"]
