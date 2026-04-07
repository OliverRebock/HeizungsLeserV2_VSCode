from influxdb_client import InfluxDBClient

def check_all_historical():
    url = 'http://10.8.0.1:8086'
    token = '-hBacWyE-7_nWSH2N4-UjV2p2yXbst7B00ir3TjJagiGMR7bpqR4HYuY1R6a8mOcifKgdtIH47uK9zCoqUHG2Q=='
    org = 'heizungsleser'
    bucket = 'ha_Input_beyer1V2'
    entity_id = 'ebusd_cpu_usage'

    client = InfluxDBClient(url=url, token=token, org=org)
    query_api = client.query_api()

    # Wir prüfen seit Anbeginn der Zeit (1970)
    query = f'''
    from(bucket: "{bucket}")
      |> range(start: 0)
      |> filter(fn: (r) => r["entity_id"] == "{entity_id}")
      |> last()
    '''
    
    try:
        print(f"Prüfe Daten für '{entity_id}' seit Anbeginn der Zeit...")
        tables = query_api.query(query)
        if tables:
            for table in tables:
                for record in table.records:
                    print(f"Letzter historischer Datenpunkt gefunden:")
                    print(f"- Zeit: {record.get_time()}")
                    print(f"- Wert: {record.get_value()}")
        else:
            print(f"Absolut KEINE Daten für '{entity_id}' im Bucket gefunden.")
            
    except Exception as e:
        print(f"Fehler bei der Abfrage: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    check_all_historical()
