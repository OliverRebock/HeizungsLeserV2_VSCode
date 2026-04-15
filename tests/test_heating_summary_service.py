from types import SimpleNamespace

import pytest

from app.models.device import Device
from app.services.heating_summary_service import heating_summary_service
from app.services.influx import influx_service


def make_device() -> Device:
    return Device(
        id=99,
        tenant_id=1,
        display_name="Testanlage",
        slug="testanlage",
        source_type="influxdb_v2",
        influx_database_name="test-bucket",
        is_active=True,
    )


@pytest.mark.asyncio
async def test_summary_handles_string_entity_lists(monkeypatch):
    async def fake_get_entities(_device):
        # Reproduces the runtime issue where entity metadata can arrive as plain strings.
        return ["sensor.vorlauf_temp", "sensor.last_error_code"]

    async def fake_get_timeseries(_device, entity_ids, _start, _end):
        assert "sensor.vorlauf_temp" in entity_ids
        assert "sensor.last_error_code" in entity_ids
        return [
            SimpleNamespace(
                entity_id="sensor.vorlauf_temp",
                points=[
                    SimpleNamespace(value="28.2", state=None),
                    SimpleNamespace(value="34.9", state=None),
                ],
            ),
            SimpleNamespace(
                entity_id="sensor.last_error_code",
                points=[
                    SimpleNamespace(
                        value="--(5140) 30.03.2026",
                        state="--(5140) 30.03.2026",
                        ts="2026-03-30T15:55:00+00:00",
                    ),
                ],
            ),
        ]

    monkeypatch.setattr(influx_service, "get_entities", fake_get_entities)
    monkeypatch.setattr(influx_service, "get_timeseries", fake_get_timeseries)

    summary = await heating_summary_service.get_device_summary(device=make_device())

    assert summary["entities"]
    error_candidate = next(candidate for candidate in summary["error_candidates"] if candidate.get("parsed_code") == "5140")
    assert error_candidate["first_seen_at"] == "2026-03-30T15:55:00+00:00"
    assert error_candidate["last_seen_at"] == "2026-03-30T15:55:00+00:00"
    assert error_candidate["seen_count"] == 1
