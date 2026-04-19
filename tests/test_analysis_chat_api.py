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


@pytest.mark.asyncio
async def test_chat_endpoint_fault_timepoint_question_returns_fault_window_values(
    client: AsyncClient, platform_admin, test_tenant, monkeypatch
):
    headers = get_auth_header(platform_admin.id)

    monkeypatch.setattr(heatpump_chat_service, "openai_enabled", False)

    async def fake_get_entities(_device):
        return [
            make_entity("boiler_last_error_code", "Boiler Letzter Fehler"),
            make_entity("boiler_current_flow_temperature", "Boiler Vorlauf"),
            make_entity("boiler_return_temperature", "Boiler Ruecklauf"),
            make_entity("mixer_hc2_setpoint_flow_temperature", "HK2 Soll Vorlauf"),
        ]

    async def fake_get_timeseries(_device, entity_ids, _start, _end):
        mapping = {
            "boiler_last_error_code": TimeSeriesResponse(
                entity_id="boiler_last_error_code",
                friendly_name="Boiler Letzter Fehler",
                domain="sensor",
                data_kind="enum",
                chartable=True,
                points=[DataPoint(ts="2026-04-03T09:51:54.981364Z", state="--(6256) 03.04.2026 11:50 - now")],
                meta={},
            ),
            "boiler_current_flow_temperature": TimeSeriesResponse(
                entity_id="boiler_current_flow_temperature",
                friendly_name="Boiler Vorlauf",
                domain="sensor",
                data_kind="numeric",
                chartable=True,
                points=[DataPoint(ts="2026-04-03T09:51:54.981715Z", value=52.1)],
                meta={},
            ),
            "boiler_return_temperature": TimeSeriesResponse(
                entity_id="boiler_return_temperature",
                friendly_name="Boiler Ruecklauf",
                domain="sensor",
                data_kind="numeric",
                chartable=True,
                points=[DataPoint(ts="2026-04-03T09:51:54.981526Z", value=45.2)],
                meta={},
            ),
            "mixer_hc2_setpoint_flow_temperature": TimeSeriesResponse(
                entity_id="mixer_hc2_setpoint_flow_temperature",
                friendly_name="HK2 Soll Vorlauf",
                domain="sensor",
                data_kind="numeric",
                chartable=True,
                points=[DataPoint(ts="2026-04-03T09:51:45.191748Z", value=29.0)],
                meta={},
            ),
        }
        return {"series": [mapping[eid] for eid in entity_ids if eid in mapping]}

    monkeypatch.setattr("app.services.heatpump_chat_service.influx_service.get_entities", fake_get_entities)
    monkeypatch.setattr("app.services.heatpump_chat_service.influx_service.get_timeseries", fake_get_timeseries)

    device_data = {
        "display_name": "Chat API Device Fault Window",
        "influx_database_name": "db_chat_api_fault_window",
        "tenant_id": test_tenant.id,
        "is_active": True,
        "source_type": "influxdb_v2",
    }
    create_res = await client.post("/api/v1/devices/", json=device_data, headers=headers)
    assert create_res.status_code == 200
    device_id = create_res.json()["id"]

    chat_res = await client.post(
        f"/api/v1/analysis/{device_id}/chat",
        json={"question": "lies die werte zum zeitpunkt des fehlers aus", "language": "de"},
        headers=headers,
    )
    assert chat_res.status_code == 200

    body = chat_res.json()
    assert body["intent"] == "anomaly"
    assert any("Fehlerzeitpunkt erkannt" in fact for fact in body["evidence"])
    assert any("Boiler Vorlauf (boiler_current_flow_temperature) beim Fehlerzeitpunkt: 52.1" in fact for fact in body["evidence"])
    assert any("Boiler Ruecklauf (boiler_return_temperature) beim Fehlerzeitpunkt: 45.2" in fact for fact in body["evidence"])


@pytest.mark.asyncio
async def test_chat_endpoint_followup_mach_2_uses_history_recommendation_context(
    client: AsyncClient, platform_admin, test_tenant, monkeypatch
):
    headers = get_auth_header(platform_admin.id)

    monkeypatch.setattr(heatpump_chat_service, "openai_enabled", False)

    async def fake_get_entities(_device):
        return [
            make_entity("boiler_last_error_code", "Boiler Letzter Fehler"),
            make_entity("thermostat_last_error_code", "Thermostat Letzter Fehler"),
            make_entity("boiler_current_flow_temperature", "Boiler Vorlauf"),
            make_entity("boiler_return_temperature", "Boiler Ruecklauf"),
            make_entity("mixer_hc2_setpoint_flow_temperature", "HK2 Soll Vorlauf"),
        ]

    async def fake_get_timeseries(_device, entity_ids, _start, _end):
        mapping = {
            "boiler_last_error_code": TimeSeriesResponse(
                entity_id="boiler_last_error_code",
                friendly_name="Boiler Letzter Fehler",
                domain="sensor",
                data_kind="enum",
                chartable=True,
                points=[DataPoint(ts="2026-04-03T09:51:54.981364Z", state="--(6256) 03.04.2026 11:50 - now")],
                meta={},
            ),
            "thermostat_last_error_code": TimeSeriesResponse(
                entity_id="thermostat_last_error_code",
                friendly_name="Thermostat Letzter Fehler",
                domain="sensor",
                data_kind="enum",
                chartable=True,
                points=[DataPoint(ts="2026-04-03T09:54:35.181516Z", state="--(6256) 03.04.2026 11:51-03.04.2026 11:51")],
                meta={},
            ),
            "boiler_current_flow_temperature": TimeSeriesResponse(
                entity_id="boiler_current_flow_temperature",
                friendly_name="Boiler Vorlauf",
                domain="sensor",
                data_kind="numeric",
                chartable=True,
                points=[DataPoint(ts="2026-04-03T09:51:54.981715Z", value=52.1)],
                meta={},
            ),
            "boiler_return_temperature": TimeSeriesResponse(
                entity_id="boiler_return_temperature",
                friendly_name="Boiler Ruecklauf",
                domain="sensor",
                data_kind="numeric",
                chartable=True,
                points=[DataPoint(ts="2026-04-03T09:51:54.981526Z", value=45.2)],
                meta={},
            ),
            "mixer_hc2_setpoint_flow_temperature": TimeSeriesResponse(
                entity_id="mixer_hc2_setpoint_flow_temperature",
                friendly_name="HK2 Soll Vorlauf",
                domain="sensor",
                data_kind="numeric",
                chartable=True,
                points=[DataPoint(ts="2026-04-03T09:51:45.191748Z", value=29.0)],
                meta={},
            ),
        }
        return {"series": [mapping[eid] for eid in entity_ids if eid in mapping]}

    monkeypatch.setattr("app.services.heatpump_chat_service.influx_service.get_entities", fake_get_entities)
    monkeypatch.setattr("app.services.heatpump_chat_service.influx_service.get_timeseries", fake_get_timeseries)

    device_data = {
        "display_name": "Chat API Device Followup",
        "influx_database_name": "db_chat_api_followup",
        "tenant_id": test_tenant.id,
        "is_active": True,
        "source_type": "influxdb_v2",
    }
    create_res = await client.post("/api/v1/devices/", json=device_data, headers=headers)
    assert create_res.status_code == 200
    device_id = create_res.json()["id"]

    chat_res = await client.post(
        f"/api/v1/analysis/{device_id}/chat",
        json={
            "question": "mach 2",
            "language": "de",
            "history": [
                {
                    "role": "assistant",
                    "content": "Konkrete Empfehlungen:\n1. **Fehlercode 6256 nachschlagen**\n2. **Ereignisprotokoll um den 03.04.2026 11:45-11:55 Uhr pruefen**\n3. **Trenddaten weiter beobachten**",
                }
            ],
        },
        headers=headers,
    )
    assert chat_res.status_code == 200

    body = chat_res.json()
    assert body["intent"] == "anomaly"
    assert any("Fehlerzeitpunkt erkannt" in fact for fact in body["evidence"])
    assert any("Boiler Vorlauf (boiler_current_flow_temperature) beim Fehlerzeitpunkt: 52.1" in fact for fact in body["evidence"])
