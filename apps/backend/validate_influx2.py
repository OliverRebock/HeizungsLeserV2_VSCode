import os
from influxdb_client import InfluxDBClient
from datetime import datetime, timedelta

# Config from env or hardcoded for test
URL = "http://10.8.0.1:8086"
TOKEN = "-hBacWyE-7_nWSH2N4-UjV2p2yXbst7B00ir3TjJagiGMR7bpqR4HYuY1R6a8mOcifKgdtIH47uK9zCoqUHG2Q=="
ORG = "bf79932d3a0547c3"
BUCKET = "ha_Input_beyer1V2"

def test_connection():
    print(f"Connecting to {URL}...")
    client = InfluxDBClient(url=URL, token=TOKEN, org=ORG, debug=True)
    
    try:
        # 1. Health check
        ready = client.ping()
        print(f"Ping successful: {ready}")
        
        # 2. List buckets
        buckets_api = client.buckets_api()
        bucket = buckets_api.find_bucket_by_name(BUCKET)
        if bucket:
            print(f"Bucket '{BUCKET}' found (ID: {bucket.id})")
        else:
            print(f"Bucket '{BUCKET}' NOT found!")
            return

        # 3. Query measurements
        query_api = client.query_api()
        flux = f'import "influxdata/influxdb/schema" schema.measurements(bucket: "{BUCKET}")'
        print("Querying measurements...")
        tables = query_api.query(flux)
        
        measurements = []
        for table in tables:
            for record in table.records:
                measurements.append(record.get_value())
        
        print(f"Found {len(measurements)} measurements: {measurements[:5]}...")

        # 4. Query data for one measurement (if exists)
        if measurements:
            m = measurements[0]
            print(f"Querying data for {m}...")
            data_flux = f'from(bucket: "{BUCKET}") |> range(start: -7d) |> filter(fn: (r) => r["_measurement"] == "{m}") |> last()'
            res = query_api.query(data_flux)
            if res:
                print("Data found!")
                for table in res:
                    for record in table.records:
                        print(f"Last point: {record.get_time()} - {record.get_field()}: {record.get_value()}")
            else:
                print("No data found in the last 7 days.")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    test_connection()
