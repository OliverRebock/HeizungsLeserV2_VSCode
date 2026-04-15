from datetime import datetime, timezone

from app.services.influx import InfluxService


def test_metadata_driven_enum_characteristics_are_consistent():
    service = InfluxService(host="http://localhost:8086", token="test-token", org="test-org")
    samples = [
        service._build_sample_point(
            datetime(2026, 4, 12, 10, 0, tzinfo=timezone.utc),
            "heating",
        )
    ]

    data_kind, value_semantics, render_mode = service._derive_series_characteristics(
        domain="sensor",
        options=["idle", "heating"],
        samples=samples,
    )

    assert data_kind == "enum"
    assert value_semantics == "stateful"
    assert render_mode == "state_timeline"
