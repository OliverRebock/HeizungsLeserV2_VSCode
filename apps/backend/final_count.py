import asyncio
from influxdb_client import InfluxDBClient
import os

async def count_entities():
    url = "http://10.8.0.1:8086"
    token = "-hBacWyE-7_nWSH2N4-UjV2p2yXbst7B00ir3TjJagiGMR7bpqR4HYuY1R6a8mOcifKgdtIH47uK9zCoqUHG2Q=="
    org = "bf79932d3a0547c3"
    bucket = "ha_Input_beyer1V2"
    
    client = InfluxDBClient(url=url, token=token, org=org)
    query_api = client.query_api()
    
    # Abfrage für alle eindeutigen entity_id Tags ÜBERHAUPT (unabhängig vom Zeitfenster)
    flux_query = f'''
        import "influxdata/influxdb/schema"
        schema.tagValues(bucket: "{bucket}", tag: "entity_id")
    '''
    
    try:
        tables = query_api.query(query=flux_query)
        entities = set()
        for table in tables:
            for record in table.records:
                entities.add(record.get_value())
        
        print(f"TOTAL_UNIQUE_ENTITY_IDS_IN_INFLUXDB: {len(entities)}")
        
        # Zum Vergleich: Abfrage für Entitäten mit Daten in den letzten 7 Tagen
        flux_query_7d = f'''
            from(bucket: "{bucket}")
            |> range(start: -7d)
            |> filter(fn: (r) => r["_field"] == "value")
            |> group(columns: ["entity_id"])
            |> distinct(column: "entity_id")
            |> keep(columns: ["entity_id"])
        '''
        tables_7d = query_api.query(query=flux_query_7d)
        entities_7d = set()
        for table in tables_7d:
            for record in table.records:
                entities_7d.add(record.values.get("entity_id"))
        
        print(f"ENTITIES_WITH_DATA_LAST_7D: {len(entities_7d)}")
        
    except Exception as e:
        print(f"FAILED: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    asyncio.run(count_entities())
