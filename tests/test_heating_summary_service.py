from types import SimpleNamespace
from datetime import datetime, timezone, timedelta

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


@pytest.mark.asyncio
async def test_error_candidates_filtered_by_timeframe_when_requested(monkeypatch):
    """Test that errors outside the analysis timeframe are excluded when apply_timeframe_filter=True."""
    async def fake_get_entities(_device):
        return ["sensor.last_error_code"]

    async def fake_get_timeseries(_device, entity_ids, _start, _end):
        return [
            SimpleNamespace(
                entity_id="sensor.last_error_code",
                points=[
                    # Error BEFORE the analysis window (should be filtered)
                    SimpleNamespace(
                        value="--(1234) 17.04.2026",
                        state="--(1234) 17.04.2026",
                        ts="2026-04-17T10:00:00+00:00",
                    ),
                    # Error WITHIN the analysis window (should be included)
                    SimpleNamespace(
                        value="--(5678) 18.04.2026",
                        state="--(5678) 18.04.2026",
                        ts="2026-04-18T15:00:00+00:00",
                    ),
                    # Error AFTER the analysis window (should be filtered)
                    SimpleNamespace(
                        value="--(9999) 19.04.2026",
                        state="--(9999) 19.04.2026",
                        ts="2026-04-19T20:00:00+00:00",
                    ),
                ],
            ),
        ]

    monkeypatch.setattr(influx_service, "get_entities", fake_get_entities)
    monkeypatch.setattr(influx_service, "get_timeseries", fake_get_timeseries)

    # Define a narrow timeframe: 18.04 08:00 to 19.04 08:00
    start = datetime(2026, 4, 18, 8, 0, 0, tzinfo=timezone.utc)
    end = datetime(2026, 4, 19, 8, 0, 0, tzinfo=timezone.utc)

    # With apply_timeframe_filter=True, only errors within [start, end] should appear
    summary = await heating_summary_service.get_device_summary(
        device=make_device(),
        start=start,
        end=end,
        apply_timeframe_filter=True  # Enable timeframe filtering
    )

    # Should only have one error (5678) - the one within the window
    error_codes = [c.get("parsed_code") for c in summary["error_candidates"]]
    assert "5678" in error_codes
    assert "1234" not in error_codes  # Before window
    assert "9999" not in error_codes  # After window


@pytest.mark.asyncio
async def test_error_candidates_not_filtered_by_default_includes_latest_error(monkeypatch):
    """Test that the latest error is included when apply_timeframe_filter=False."""
    async def fake_get_entities(_device):
        return ["sensor.last_error_code"]

    async def fake_get_timeseries(_device, entity_ids, _start, _end):
        # Return a single latest error within the query window
        return [
            SimpleNamespace(
                entity_id="sensor.last_error_code",
                points=[
                    # Latest error point returned by InfluxDB
                    SimpleNamespace(
                        value="--(5678) 18.04.2026",
                        state="--(5678) 18.04.2026",
                        ts="2026-04-18T18:00:00+00:00",
                    ),
                ],
            ),
        ]

    monkeypatch.setattr(influx_service, "get_entities", fake_get_entities)
    monkeypatch.setattr(influx_service, "get_timeseries", fake_get_timeseries)

    # Define timeframe
    start = datetime(2026, 4, 18, 8, 0, 0, tzinfo=timezone.utc)
    end = datetime(2026, 4, 19, 8, 0, 0, tzinfo=timezone.utc)

    # With apply_timeframe_filter=False (default), errors from InfluxDB are shown unfiltered
    summary = await heating_summary_service.get_device_summary(
        device=make_device(),
        start=start,
        end=end,
        apply_timeframe_filter=False
    )

    # Should have the latest error
    error_codes = [c.get("parsed_code") for c in summary["error_candidates"]]
    assert "5678" in error_codes


@pytest.mark.asyncio
async def test_summary_builds_dynamic_operating_context_for_peaks(monkeypatch):
    async def fake_get_entities(_device):
        return [
            {
                "entity_id": "sensor.custom_compressor_mode",
                "friendly_name": "Verdichtermodus",
                "domain": "sensor",
                "data_kind": "state",
            },
            {
                "entity_id": "binary_sensor.custom_ww_status",
                "friendly_name": "Warmwasser aktiv",
                "domain": "binary_sensor",
                "data_kind": "binary",
            },
            {
                "entity_id": "sensor.custom_flow_temperature",
                "friendly_name": "Vorlauf",
                "domain": "sensor",
                "data_kind": "numeric",
                "unit_of_measurement": "°C",
            },
            {
                "entity_id": "sensor.custom_ww_priority",
                "friendly_name": "WW Vorrang",
                "domain": "binary_sensor",
                "data_kind": "binary",
            },
        ]

    async def fake_get_timeseries(_device, _entity_ids, _start, _end):
        return [
            SimpleNamespace(
                entity_id="sensor.custom_compressor_mode",
                points=[
                    SimpleNamespace(value=0, state="aus", ts="2026-04-30T10:00:00+00:00"),
                    SimpleNamespace(value=0, state="heizen", ts="2026-04-30T10:10:00+00:00"),
                    SimpleNamespace(value=0, state="heizen", ts="2026-04-30T10:40:00+00:00"),
                    SimpleNamespace(value=0, state="aus", ts="2026-04-30T10:45:00+00:00"),
                ],
            ),
            SimpleNamespace(
                entity_id="binary_sensor.custom_ww_status",
                points=[
                    SimpleNamespace(value=0, state="0", ts="2026-04-30T10:00:00+00:00"),
                    SimpleNamespace(value=1, state="1", ts="2026-04-30T10:20:00+00:00"),
                    SimpleNamespace(value=0, state="0", ts="2026-04-30T10:42:00+00:00"),
                ],
            ),
            SimpleNamespace(
                entity_id="sensor.custom_flow_temperature",
                points=[
                    SimpleNamespace(value=30.0, state=None, ts="2026-04-30T10:05:00+00:00"),
                    SimpleNamespace(value=66.4, state=None, ts="2026-04-30T10:21:00+00:00"),
                    SimpleNamespace(value=35.0, state=None, ts="2026-04-30T10:50:00+00:00"),
                ],
            ),
            SimpleNamespace(
                entity_id="sensor.custom_ww_priority",
                points=[
                    SimpleNamespace(value=1, state="1", ts="2026-04-30T10:00:00+00:00"),
                    SimpleNamespace(value=1, state="1", ts="2026-04-30T10:30:00+00:00"),
                ],
            ),
        ]

    monkeypatch.setattr(influx_service, "get_entities", fake_get_entities)
    monkeypatch.setattr(influx_service, "get_timeseries", fake_get_timeseries)

    summary = await heating_summary_service.get_device_summary(device=make_device())

    operating_context = summary.get("operating_context") or {}
    status_windows = operating_context.get("status_windows") or []
    peak_contexts = operating_context.get("temperature_peak_contexts") or []

    assert any(item.get("category") == "compressor" for item in status_windows)
    assert any(item.get("category") == "hot_water" for item in status_windows)
    assert not any(item.get("entity_id") == "sensor.custom_ww_priority" for item in status_windows)
    assert any(
        item.get("entity_id") == "sensor.custom_flow_temperature"
        and item.get("active_modes")
        for item in peak_contexts
    )
