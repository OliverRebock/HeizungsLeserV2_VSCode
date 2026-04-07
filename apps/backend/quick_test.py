import asyncio
from app.services.influx import influx_service

class MockDevice:
    def __init__(self, db_name):
        self.influx_database_name = db_name

async def test():
    # Suche nach der Betriebsart in verschiedenen Measurements/Tags
    from influxdb_client import InfluxDBClient
    url = "http://10.8.0.1:8086"
    token = "-hBacWyE-7_nWSH2N4-UjV2p2yXbst7B00ir3TjJagiGMR7bpqR4HYuY1R6a8mOcifKgdtIH47uK9zCoqUHG2Q=="
    org = "bf79932d3a0547c3"
    bucket = "ha_Input_beyer1V2"
    
    client = InfluxDBClient(url=url, token=token, org=org)
    query_api = client.query_api()
    
    # Wir suchen nach der Entität in den letzten 30 Tagen
    flux_query = f'''
        from(bucket: "{bucket}")
        |> range(start: -30d)
        |> filter(fn: (r) => r["entity_id"] == "select.thermostat_hc1_operating_mode" or r["_measurement"] == "select.thermostat_hc1_operating_mode")
        |> last()
    '''
    
    try:
        print("Searching for select.thermostat_hc1_operating_mode...")
        tables = query_api.query(query=flux_query)
        found = False
        for table in tables:
            for record in table.records:
                found = True
                print(f"FOUND DATA: {record.values}")
        
        if not found:
            print("Not found by exact name, searching for partial matches...")
            search_query = f'''
                import "influxdata/influxdb/schema"
                schema.tagValues(bucket: "{bucket}", tag: "entity_id")
            '''
            tag_tables = query_api.query(query=search_query)
            for table in tag_tables:
                for record in table.records:
                    if "hc1" in record.get_value().lower() and "mode" in record.get_value().lower():
                        print(f"PARTIAL MATCH FOUND: {record.get_value()}")
    except Exception as e:
        print(f"FAILED: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    asyncio.run(test())
