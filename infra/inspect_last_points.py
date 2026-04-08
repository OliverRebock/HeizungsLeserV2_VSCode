from influxdb_client import InfluxDBClient
from datetime import datetime, timezone

def inspect_last_points():
    url = 'http://10.8.0.1:8086'
    token = '-hBacWyE-7_nWSH2N4-UjV2p2yXbst7B00ir3TjJagiGMR7bpqR4HYuY1R6a8mOcifKgdtIH47uK9zCoqUHG2Q=='
    org = 'heizungsleser'
    bucket = 'ha_Input_rebock'
    
    entities = [
        "boiler_compressor_current_power", 
        "boiler_compressor_power_output"
    ]
    
    now_utc = datetime.now(timezone.utc)
    print(f"DEBUG: Current UTC: {now_utc.isoformat()}")
    
    with InfluxDBClient(url=url, token=token, org=org) as client:
        for entity in entities:
            print(f"\n--- Entity: {entity} ---")
            # Wir suchen nach dem allerletzten Punkt ÜBERHAUPT
            query = f'''
            from(bucket: "{bucket}")
            |> range(start: -48h)
            |> filter(fn: (r) => r["entity_id"] == "{entity}")
            |> filter(fn: (r) => r["_field"] == "value")
            |> last()
            '''
            tables = client.query_api().query(query)
            if not tables:
                print("  No data found in last 48h.")
                continue
                
            for table in tables:
                for record in table.records:
                    ts = record.get_time()
                    val = record.get_value()
                    unit = record.values.get("unit_of_measurement_str", "N/A")
                    
                    diff = (now_utc - ts).total_seconds()
                    print(f"  Technical ID: {entity}")
                    print(f"  Last Real Point Time: {ts.isoformat()}")
                    print(f"  Last Real Value: {val} {unit}")
                    print(f"  Age: {int(diff/60)} minutes")
                    
                    if diff > 900:
                        print(f"  RESULT: Should be 0.0 at the end of the chart (Timeout active).")
                    else:
                        print(f"  RESULT: Should hold value {val} until now.")

if __name__ == '__main__':
    inspect_last_points()
