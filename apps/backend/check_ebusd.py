from influxdb_client import InfluxDBClient

def check_ebusd_cpu():
    url = 'http://10.8.0.1:8086'
    token = '-hBacWyE-7_nWSH2N4-UjV2p2yXbst7B00ir3TjJagiGMR7bpqR4HYuY1R6a8mOcifKgdtIH47uK9zCoqUHG2Q=='
    org = 'heizungsleser'
    bucket = 'ha_Input_beyer1V2'
    entity_id = 'ebusd_cpu_usage'

    client = InfluxDBClient(url=url, token=token, org=org)
    query_api = client.query_api()

    # Wir prüfen die letzten 30 Tage auf Daten für diese spezifische Entität
    query = f'''
    from(bucket: "{bucket}")
      |> range(start: -30d)
      |> filter(fn: (r) => r["entity_id"] == "{entity_id}")
      |> last()
    '''
    
    try:
        print(f"Prüfe Daten für '{entity_id}' in den letzten 30 Tagen...")
        tables = query_api.query(query)
        if tables:
            for table in tables:
                for record in table.records:
                    print(f"Letzter Datenpunkt gefunden:")
                    print(f"- Zeit: {record.get_time()}")
                    print(f"- Wert: {record.get_value()}")
                    print(f"- Feld: {record.get_field()}")
        else:
            print(f"KEINE Daten für '{entity_id}' in den letzten 30 Tagen gefunden.")
            
    except Exception as e:
        print(f"Fehler bei der Abfrage: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    check_ebusd_cpu()
