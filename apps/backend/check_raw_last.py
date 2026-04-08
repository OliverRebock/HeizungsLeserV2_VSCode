from influxdb_client import InfluxDBClient

def check_raw_last():
    url = 'http://10.8.0.1:8086'
    token = '-hBacWyE-7_nWSH2N4-UjV2p2yXbst7B00ir3TjJagiGMR7bpqR4HYuY1R6a8mOcifKgdtIH47uK9zCoqUHG2Q=='
    org = 'heizungsleser'
    bucket = 'ha_Input_rebock'
    
    print(f"Connecting to {url} (Bucket: {bucket})...")
    with InfluxDBClient(url=url, token=token, org=org, timeout=10000) as client:
        entities = ["boiler_compressor_current_power", "boiler_compressor_power_output"]
        for entity in entities:
            print(f"\nEntity: {entity}")
            query = f'''
            from(bucket: "{bucket}")
            |> range(start: 0)
            |> filter(fn: (r) => r["entity_id"] == "{entity}")
            |> filter(fn: (r) => r["_field"] == "value")
            |> last()
            '''
            tables = client.query_api().query(query)
            for table in tables:
                for record in table.records:
                    print(f"  Time: {record.get_time()} -> Value: {record.get_value()}")

if __name__ == '__main__':
    check_raw_last()
