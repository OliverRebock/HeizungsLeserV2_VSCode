from influxdb_client import InfluxDBClient

def count_entities():
    url = 'http://10.8.0.1:8086'
    token = '-hBacWyE-7_nWSH2N4-UjV2p2yXbst7B00ir3TjJagiGMR7bpqR4HYuY1R6a8mOcifKgdtIH47uK9zCoqUHG2Q=='
    org = 'heizungsleser'
    bucket = 'ha_Input_beyer1V2'

    client = InfluxDBClient(url=url, token=token, org=org)
    query_api = client.query_api()

    # Wir gruppieren nach _field, um alle verschiedenen Entitäten (Sensoren) zu finden
    query = f'''
    from(bucket: "{bucket}")
      |> range(start: -24h)
      |> keep(columns: ["_field"])
      |> group(columns: ["_field"])
      |> distinct(column: "_field")
    '''
    
    try:
        tables = query_api.query(query)
        fields = []
        for table in tables:
            for record in table:
                fields.append(record.get_value())
        
        print(f"ANZAHL_ENTITAETEN: {len(fields)}")
        if fields:
            print("ENTITAETEN_LISTE:")
            for field in sorted(fields):
                print(f"- {field}")
        else:
            print("KEINE_ENTITAETEN_GEFUNDEN")
            
    except Exception as e:
        print(f"ERROR: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    count_entities()
