from influxdb_client import InfluxDBClient

def list_measurements():
    url = 'http://10.8.0.1:8086'
    token = '-hBacWyE-7_nWSH2N4-UjV2p2yXbst7B00ir3TjJagiGMR7bpqR4HYuY1R6a8mOcifKgdtIH47uK9zCoqUHG2Q=='
    org = 'heizungsleser'
    bucket = 'ha_Input_beyer1V2'
    
    print(f"Connecting to {url} (Bucket: {bucket})...")
    with InfluxDBClient(url=url, token=token, org=org, timeout=10000) as client:
        # Abfrage aller verfÃ¼gbaren Measurements in den letzten 2 Stunden
        query = f'''
        import "influxdata/influxdb/schema"
        schema.measurements(bucket: "{bucket}")
        '''
        try:
            tables = client.query_api().query(query)
            print("VerfÃ¼gbare Measurements:")
            for table in tables:
                for record in table.records:
                    print(f"- {record.get_value()}")
                    
            # Auch nach Tags suchen (entity_id)
            query_tags = f'''
            import "influxdata/influxdb/schema"
            schema.tagValues(bucket: "{bucket}", tag: "entity_id")
            '''
            tables_tags = client.query_api().query(query_tags)
            print("\nVerfÃ¼gbare entity_id Tags:")
            for table in tables_tags:
                for record in table.records:
                    print(f"- {record.get_value()}")
                    
        except Exception as e:
            print(f"Fehler bei der Abfrage: {e}")

if __name__ == '__main__':
    list_measurements()
