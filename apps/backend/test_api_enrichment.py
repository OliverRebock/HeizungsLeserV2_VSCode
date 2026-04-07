import asyncio
from app.services.influx import influx_service
from app.db.session import SessionLocal
from app.models.device import Device
import app.db.base

async def test_enrichment():
    async with SessionLocal() as session:
        from sqlalchemy import select
        result = await session.execute(select(Device).where(Device.display_name == 'HA1 Beyer'))
        device = result.scalar_one_or_none()
        
        if not device:
            print("Gerät HA1 Beyer nicht gefunden.")
            return

        print(f"Teste Entitäten-Enrichment für '{device.display_name}'...")
        entities = await influx_service.get_entities(device)
        
        # Suche nach den vom User genannten Sensoren
        targets = [
            'boiler_air_inlet_temperature_tl2',
            'boiler_aux_heater_status',
            'boiler_burner_current_power',
            'boiler_circulation_pump_speed',
            'boiler_compressor_activity'
        ]
        
        found_any = False
        for ent in entities:
            if ent.entity_id in targets:
                found_any = True
                print(f"Gefunden: {ent.entity_id}")
                print(f"  Friendly Name: {ent.friendly_name}")
                print(f"  Last Value: {ent.last_value}")
                print(f"  Last Seen: {ent.last_seen}")
                print(f"  Unit: {ent.unit_of_measurement}")
        
        if not found_any:
            print("Keine der Ziel-Entitäten in der Liste gefunden.")
            # Zeig mal die ersten 5 an
            print("\nErste 5 Entitäten in der Liste:")
            for ent in entities[:5]:
                print(f"- {ent.entity_id}: {ent.last_value}")

if __name__ == "__main__":
    asyncio.run(test_enrichment())
