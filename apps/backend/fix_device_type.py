import asyncio
from app.db.session import SessionLocal
from app.models.device import Device
from app.models.tenant import Tenant # Import Tenant to avoid mapper error
from sqlalchemy import select, update

async def fix_device_type():
    async with SessionLocal() as session:
        # Check current status
        result = await session.execute(select(Device).where(Device.display_name == 'HA1 Beyer'))
        device = result.scalar_one_or_none()
        
        if device:
            print(f"Aktueller Typ von '{device.display_name}': {device.source_type}")
            
            if device.source_type != "influxdb_v2":
                print(f"Korrigiere Typ auf 'influxdb_v2'...")
                await session.execute(
                    update(Device)
                    .where(Device.id == device.id)
                    .values(source_type="influxdb_v2")
                )
                await session.commit()
                print("Korrektur erfolgreich durchgeführt.")
            else:
                print("Typ ist bereits korrekt auf 'influxdb_v2' gesetzt.")
        else:
            print("Gerät 'HA1 Beyer' nicht gefunden.")

if __name__ == "__main__":
    asyncio.run(fix_device_type())
