from datetime import datetime

import pytest

from app.models.device import Device
from app.schemas.analysis import AnalysisRequest
from app.services.device_analysis_service import device_analysis_service
from app.services.heating_summary_service import heating_summary_service
from app.services.openai_service import openai_service


def make_device() -> Device:
    return Device(
        id=1,
        tenant_id=1,
        display_name="Test Waermepumpe",
        slug="test-waermepumpe",
        source_type="influxdb_v2",
        influx_database_name="test_bucket",
        is_active=True,
    )


def build_summary():
    return {
        "analysis_run_id": "run-1",
        "device_id": 1,
        "device_name": "Test Waermepumpe",
        "period": {
            "start": "2026-04-01T00:00:00",
            "end": "2026-04-02T00:00:00",
        },
        "entities": [
            {
                "entity_id": "sensor.vorlauf",
                "label": "Vorlauftemperatur",
                "data_kind": "numeric",
                "summary": {
                    "min": 24.5,
                    "max": 39.8,
                    "avg": 31.2,
                    "count": 18,
                },
            },
            {
                "entity_id": "sensor.betriebsstatus",
                "label": "Betriebsstatus",
                "data_kind": "state",
                "summary": {
                    "states_seen": ["Heizen", "Standby"],
                    "most_recent_state": "Heizen",
                    "most_frequent_state": "Heizen",
                    "changes": 7,
                    "count": 14,
                },
            },
        ],
        "error_candidates": [
            {
                "entity_id": "sensor.last_error",
                "label": "Letzter Fehler",
                "raw_value": "--(5140) 30.03.2026",
                "parsed_code": "5140",
                "classification": "historical",
                "confidence": "high",
                "first_seen_at": "2026-04-01T08:15:00+00:00",
                "last_seen_at": "2026-04-01T09:45:00+00:00",
                "seen_count": 3,
            }
        ],
    }


@pytest.mark.asyncio
async def test_run_analysis_falls_back_when_openai_disabled(monkeypatch):
    async def fake_summary(*args, **kwargs):
        return build_summary()

    monkeypatch.setattr(heating_summary_service, "get_device_summary", fake_summary)
    monkeypatch.setattr(openai_service, "enabled", False)

    response = await device_analysis_service.run_analysis(
        device=make_device(),
        request=AnalysisRequest(
            **{
                "from": datetime.fromisoformat("2026-04-01T00:00:00"),
                "to": datetime.fromisoformat("2026-04-02T00:00:00"),
            }
        ),
    )

    assert response.analysis_mode == "fallback"
    assert response.analysis_notice is not None
    assert response.should_trigger_error_analysis is True
    assert response.findings


@pytest.mark.asyncio
async def test_run_analysis_falls_back_when_openai_request_fails(monkeypatch):
    async def fake_summary(*args, **kwargs):
        return build_summary()

    async def failing_openai(*args, **kwargs):
        raise Exception("Fehler bei der Kommunikation mit OpenAI: 503")

    monkeypatch.setattr(heating_summary_service, "get_device_summary", fake_summary)
    monkeypatch.setattr(openai_service, "enabled", True)
    monkeypatch.setattr(openai_service, "analyze_heating_data", failing_openai)

    response = await device_analysis_service.run_analysis(
        device=make_device(),
        request=AnalysisRequest(
            **{
                "from": datetime.fromisoformat("2026-04-01T00:00:00"),
                "to": datetime.fromisoformat("2026-04-02T00:00:00"),
            }
        ),
    )

    assert response.analysis_mode == "fallback"
    assert "OpenAI" in (response.analysis_notice or "")
    assert response.detected_error_codes
    assert response.detected_error_codes[0].first_seen_at is not None
    assert response.detected_error_codes[0].last_seen_at is not None
    assert response.detected_error_codes[0].seen_count == 3


@pytest.mark.asyncio
async def test_run_analysis_returns_clear_error_for_empty_summary(monkeypatch):
    async def fake_summary(*args, **kwargs):
        return {
            "analysis_run_id": "run-empty",
            "entities": [],
            "error_candidates": [],
        }

    monkeypatch.setattr(heating_summary_service, "get_device_summary", fake_summary)
    monkeypatch.setattr(openai_service, "enabled", False)

    with pytest.raises(ValueError, match="keine auswertbaren Daten"):
        await device_analysis_service.run_analysis(
            device=make_device(),
            request=AnalysisRequest(),
        )


@pytest.mark.asyncio
async def test_run_deep_analysis_falls_back_when_openai_disabled(monkeypatch):
    async def fake_summary(*args, **kwargs):
        return build_summary()

    monkeypatch.setattr(heating_summary_service, "get_device_summary", fake_summary)
    monkeypatch.setattr(openai_service, "enabled", False)

    response = await device_analysis_service.run_deep_analysis(
        device=make_device(),
        request=AnalysisRequest(
            manufacturer="Viessmann",
            heat_pump_type="Vitocal 200-S",
        ),
    )

    assert response.analysis_mode == "fallback"
    assert response.analysis_notice is not None
    assert response.diagnostic_steps
    assert response.technical_findings
