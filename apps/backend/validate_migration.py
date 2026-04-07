import asyncio
import os
import sys
from typing import List

# Den app Pfad zum PYTHONPATH hinzufügen
sys.path.append(os.path.join(os.getcwd(), "apps", "backend"))

from app.services.influx import influx_service
from app.schemas.influx import Entity

from dataclasses import dataclass

@dataclass
class MockDevice:
    id: int
    name: str
    influx_database_name: str

from app.core.config import settings

async def validate_migration():
    print("Validating InfluxDB 2 Migration...")
    
    # Sicherstellen dass settings korrekt geladen sind (vielleicht localhost problem im Backend Container?)
    print(f"Using InfluxDB URL: {settings.INFLUXDB_URL}")
    if "localhost" in settings.INFLUXDB_URL:
        # Im Docker Container sollte es die IP oder der Service-Name sein
        influx_service.host = "http://10.8.0.1:8086"
        # Token explizit setzen falls settings.INFLUXDB_TOKEN falsch geladen wurde
        influx_service.token = "-hBacWyE-7_nWSH2N4-UjV2p2yXbst7B00ir3TjJagiGMR7bpR4HYuY1R6a8mOcifKgdtIH47uK9zCoqUHG2Q=="
        influx_service.org = "bf79932d3a0547c3"
        # Client zurücksetzen damit er mit neuen Attributen neu erstellt wird
        influx_service._client = None
        print(f"Overriding InfluxDB URL to: {influx_service.host}")
    
    # Mock Device Objekt erstellen
    test_device = MockDevice(
        id=1,
        name="Test Device",
        influx_database_name="ha_Input_beyer1V2"
    )
    
    print("\n1. Testing get_entities...")
    try:
        entities = await influx_service.get_entities(test_device)
        print(f"Found {len(entities)} entities.")
        if entities:
            for i, ent in enumerate(entities[:5]):
                print(f" - {i+1}. {ent.entity_id} ({ent.domain}) - Source: {ent.source_table}")
        else:
            print("ERROR: No entities found!")
            return
    except Exception as e:
        print(f"ERROR in get_entities: {e}")
        return

    print("\n2. Testing get_timeseries for 'sensor.boiler_temperature'...")
    try:
        # Wir nehmen an, dass diese Entity existiert (war in der Analyse vorhanden)
        target_eid = "sensor.boiler_temperature"
        # Falls nicht in den Top 5, suchen wir sie
        if not any(e.entity_id == target_eid for e in entities):
            if entities:
                target_eid = entities[0].entity_id
                print(f"Using {target_eid} for timeseries test instead.")
        
        timeseries = await influx_service.get_timeseries(
            test_device, 
            [target_eid], 
            start="-24h", 
            end="now()"
        )
        
        if timeseries and timeseries[0].points:
            print(f"Found {len(timeseries[0].points)} data points for {target_eid}.")
            p = timeseries[0].points[-1]
            print(f"Latest point: {p.ts} | Value: {p.value} | State: {p.state}")
        else:
            print(f"No data points found for {target_eid} in the last 24h.")
            # Letzter Versuch mit längerem Zeitraum
            print("Trying with -30d...")
            timeseries = await influx_service.get_timeseries(
                test_device, 
                [target_eid], 
                start="-30d", 
                end="now()"
            )
            if timeseries and timeseries[0].points:
                 print(f"Found {len(timeseries[0].points)} data points in the last 30d.")
            else:
                 print("Still no data points found.")

    except Exception as e:
        print(f"ERROR in get_timeseries: {e}")

if __name__ == "__main__":
    asyncio.run(validate_migration())
