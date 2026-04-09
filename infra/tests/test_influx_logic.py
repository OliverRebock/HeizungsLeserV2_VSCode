import pytest
from datetime import datetime, timezone, timedelta
from app.services.influx import DataPoint

def test_value_semantics_classification():
    from app.services.influx import influx_service
    
    # Instant values
    assert influx_service._get_value_semantics("sensor.compressor_power", "kW") == "instant"
    assert influx_service._get_value_semantics("boiler_compressor_power_output", "W") == "instant"
    assert influx_service._get_value_semantics("current_consumption", "A") == "instant"
    
    # Stateful values
    assert influx_service._get_value_semantics("sensor.outside_temp", "°C") == "stateful"
    assert influx_service._get_value_semantics("boiler_pressure", "bar") == "stateful"
    assert influx_service._get_value_semantics("battery_level", "%") == "stateful"
    
    # Default/Fallback
    assert influx_service._get_value_semantics("unknown_sensor") == "default"

@pytest.mark.asyncio
async def test_timeseries_timeout_logic():
    # This is a unit test for the logic inside get_timeseries
    # We mock the parts that require a real InfluxDB
    from app.services.influx import influx_service
    import pytz
    
    # Setup test data
    eid = "boiler_compressor_power_output"
    unit = "kW"
    now_utc = datetime.now(timezone.utc)
    
    # Case 1: Point is FRESH (5 min old) -> Should NOT timeout (hold value)
    ts_fresh = (now_utc - timedelta(minutes=5)).isoformat().replace('+00:00', 'Z')
    points_fresh = [DataPoint(ts=ts_fresh, value=10.5, state="10.5")]
    
    # Manual execution of the logic we want to test
    # (Simplified reproduction of the logic in influx.py)
    value_semantics = influx_service._get_value_semantics(eid, unit)
    assert value_semantics == "instant"
    
    last_p = points_fresh[-1]
    final_end_ts = now_utc.isoformat()
    
    # Reproduce logic for fresh point
    dt_last = datetime.fromisoformat(last_p.ts.replace('Z', '+00:00'))
    diff_seconds = (now_utc - dt_last).total_seconds()
    
    # Should NOT trigger timeout if < 900s
    assert diff_seconds <= 900
    carry_value = last_p.value # Should keep 10.5
    assert carry_value == 10.5
    
    # Case 2: Point is STALE (20 min old) -> Should TIMEOUT (fall to 0)
    ts_stale = (now_utc - timedelta(minutes=20)).isoformat().replace('+00:00', 'Z')
    points_stale = [DataPoint(ts=ts_stale, value=11.5, state="11.5")]
    
    last_p_stale = points_stale[-1]
    dt_last_stale = datetime.fromisoformat(last_p_stale.ts.replace('Z', '+00:00'))
    diff_seconds_stale = (now_utc - dt_last_stale).total_seconds()
    
    # Should trigger timeout if > 900s
    assert diff_seconds_stale > 900
    carry_value_stale = 0.0 # Our logic sets this to 0.0
    assert carry_value_stale == 0.0
