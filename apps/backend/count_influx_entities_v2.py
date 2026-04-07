from influxdb_client import InfluxDBClient

def count_entities():
    url = 'http://10.8.0.1:8086'
    token = '-hBacWyE-7_nWSH2N4-UjV2p2yXbst7B00ir3TjJagiGMR7bpqR4HYuY1R6a8mOcifKgdtIH47uK9zCoqUHG2Q=='
    org = 'heizungsleser'
    bucket = 'ha_Input_beyer1V2'

    client = InfluxDBClient(url=url, token=token, org=org)
    query_api = client.query_api()

    # Wir gruppieren nach dem Tag 'entity_id', um die tatsächlichen HomeAssistant-Entitäten zu zählen
    query = f'''
    from(bucket: "{bucket}")
      |> range(start: -24h)
      |> keep(columns: ["entity_id"])
      |> group(columns: ["entity_id"])
      |> distinct(column: "entity_id")
    '''
    
    try:
        tables = query_api.query(query)
        entities = []
        for table in tables:
            for record in table:
                entities.append(record.get_value())
        
        print(f"ANZAHL_ENTITAETEN: {len(entities)}")
        if entities:
            print("ENTITAETEN_LISTE:")
            for entity in sorted(entities):
                print(f"- {entity}")
        else:
            print("KEINE_ENTITAETEN_GEFUNDEN")
            
    except Exception as e:
        print(f"ERROR: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    count_entities()
