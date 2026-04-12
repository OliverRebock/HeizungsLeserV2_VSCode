import asyncio
import os
import sys

# Pfad zum App-Verzeichnis hinzufügen
sys.path.append("/app")

from app.services.influx import influx_service
# Dummy class instead of real model to avoid SQLAlchemy issues
class Device:
    def __init__(self, id, name, influx_database_name):
        self.id = id
        self.name = name
        self.influx_database_name = influx_database_name

async def check():
    buckets = ["ha_Input_rebock"]
    
    entity_ids = ["boiler_compressor_current_power"]
    
    for bucket in buckets:
        print(f"\n========================================")
        print(f"ULTIMATIVER CHECK BUCKET: {bucket}")
        print(f"========================================")
        
        query_api = influx_service.client.query_api()
        
        # 1. Was sind die absolut neuesten Daten im ganzen Bucket?
        query_latest = f'''
            from(bucket: "{bucket}")
            |> range(start: -7d)
            |> last()
            |> limit(n: 10)
        '''
        try:
            tables = query_api.query(query=query_latest)
            print("Letzte Punkte im Bucket (letzte 7 Tage):")
            for table in tables:
                for record in table.records:
                    print(f"  T: {record.get_time()} | M: {record.get_measurement()} | F: {record.get_field()} | V: {record.get_value()}")
        except Exception as e:
            print(f"Fehler bei Latest-Query: {e}")

        # 2. Suche nach 'boiler_compressor_current_power' als Tag oder Measurement
        query_tag = f'''
            from(bucket: "{bucket}")
            |> range(start: -7d)
            |> filter(fn: (r) => r["entity_id"] == "boiler_compressor_current_power" or r["_measurement"] == "boiler_compressor_current_power")
            |> last()
        '''
        try:
            tables = query_api.query(query=query_tag)
            print("\nSuche nach 'boiler_compressor_current_power' (Tag/Measurement):")
            found = False
            for table in tables:
                for record in table.records:
                    found = True
                    print(f"  T: {record.get_time()} | M: {record.get_measurement()} | V: {record.get_value()}")
            if not found:
                print("Nicht gefunden.")
        except Exception as e:
            print(f"Fehler bei Tag-Query: {e}")

if __name__ == "__main__":
    asyncio.run(check())
