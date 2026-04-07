from influxdb_client import InfluxDBClient

def check_entities():
    url = 'http://10.8.0.1:8086'
    token = '-hBacWyE-7_nWSH2N4-UjV2p2yXbst7B00ir3TjJagiGMR7bpqR4HYuY1R6a8mOcifKgdtIH47uK9zCoqUHG2Q=='
    org = 'heizungsleser'
    bucket = 'ha_Input_beyer1V2'

    client = InfluxDBClient(url=url, token=token, org=org)
    query_api = client.query_api()

    # Strategie 1: Tag Values (entity_id) - Ohne Zeitbeschränkung
    query1 = f'''
        import "influxdata/influxdb/schema"
        schema.tagValues(bucket: "{bucket}", tag: "entity_id")
    '''
    
    # Strategie 2: Letzte 24h (Live Daten)
    query2 = f'''
        from(bucket: "{bucket}")
          |> range(start: -24h)
          |> keep(columns: ["entity_id"])
          |> group(columns: ["entity_id"])
          |> distinct(column: "entity_id")
    '''
    
    try:
        print("--- Strategie 1: Alle historischen entity_id Tags ---")
        tables1 = query_api.query(query1)
        tags_all = []
        for table in tables1:
            for record in table.records:
                tags_all.append(record.get_value())
        print(f"Gefundene historische Entitäten: {len(tags_all)}")
        
        print("\n--- Strategie 2: Entitäten mit Daten in den letzten 24h ---")
        tables2 = query_api.query(query2)
        tags_live = []
        for table in tables2:
            for record in table:
                tags_live.append(record.get_value())
        print(f"Gefundene Live-Entitäten (24h): {len(tags_live)}")
        
        diff = set(tags_all) - set(tags_live)
        if diff:
            print(f"\nEntitäten, die historisch existieren, aber in den letzten 24h KEINE Daten gesendet haben ({len(diff)}):")
            for item in sorted(list(diff)):
                print(f"- {item}")
        else:
            print("\nAlle historischen Entitäten haben auch in den letzten 24h Daten gesendet.")
            
    except Exception as e:
        print(f"Fehler: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    check_entities()
