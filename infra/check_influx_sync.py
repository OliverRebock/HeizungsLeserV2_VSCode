from influxdb_client import InfluxDBClient

def check_value():
    url = 'http://10.8.0.1:8086'
    token = '-hBacWyE-7_nWSH2N4-UjV2p2yXbst7B00ir3TjJagiGMR7bpqR4HYuY1R6a8mOcifKgdtIH47uK9zCoqUHG2Q=='
    org = 'heizungsleser'
    bucket = 'ha_Input_beyer1V2'
    
    print(f"Connecting to {url} (Bucket: {bucket})...")
    with InfluxDBClient(url=url, token=token, org=org, timeout=10000) as client:
        query = f'''
        from(bucket: "{bucket}")
        |> range(start: -48h)
        |> filter(fn: (r) => r["entity_id"] == "boiler_compressor_current_power")
        |> last()
        '''
        try:
            tables = client.query_api().query(query)
            if not tables:
                print("Keine Daten fÃ¼r 'boiler_compressor_current_power' gefunden.")
                return
                
            for table in tables:
                for record in table.records:
                    print(f"Zeitpunkt: {record.get_time()}")
                    print(f"Wert: {record.get_value()}")
                    print(f"Feld: {record.get_field()}")
                    print(f"Entity: {record.values.get('entity_id')}")
        except Exception as e:
            print(f"Fehler bei der Abfrage: {e}")

if __name__ == '__main__':
    check_value()
