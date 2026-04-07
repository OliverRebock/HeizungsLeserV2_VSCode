from influxdb_client import InfluxDBClient

def check_live_data_structure():
    url = 'http://10.8.0.1:8086'
    token = '-hBacWyE-7_nWSH2N4-UjV2p2yXbst7B00ir3TjJagiGMR7bpqR4HYuY1R6a8mOcifKgdtIH47uK9zCoqUHG2Q=='
    org = 'heizungsleser'
    bucket = 'ha_Input_beyer1V2'

    client = InfluxDBClient(url=url, token=token, org=org)
    query_api = client.query_api()

    # Wir schauen uns mal ein paar echte Datensätze an, um die Struktur zu verstehen
    query = f'''
    from(bucket: "{bucket}")
      |> range(start: -1h)
      |> filter(fn: (r) => r["entity_id"] == "boiler_air_inlet_temperature_tl2")
      |> last()
    '''
    
    try:
        print(f"Abfrage für 'boiler_air_inlet_temperature_tl2' im Bucket '{bucket}':")
        tables = query_api.query(query)
        if not tables:
            print("KEINE Daten in der letzten Stunde gefunden.")
            return

        for table in tables:
            for record in table.records:
                print(f"Record gefunden:")
                print(f"  Field: {record.get_field()}")
                print(f"  Value: {record.get_value()}")
                print(f"  Time:  {record.get_time()}")
                print(f"  Alle Tags/Felder: {record.values}")
                
    except Exception as e:
        print(f"Fehler: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    check_live_data_structure()
