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
