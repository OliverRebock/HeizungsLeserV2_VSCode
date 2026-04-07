import asyncio
from app.db.session import SessionLocal
from app.models.user import User
from app.models.tenant import Tenant
from app.models.device import Device
from sqlalchemy import select, update

async def fix_devices():
    print("Checking and fixing Device entries in PostgreSQL...")
    async with SessionLocal() as db:
        result = await db.execute(select(Device))
        devices = result.scalars().all()
        for d in devices:
            print(f"Current Device ID: {d.id}, Name: {d.display_name}, Bucket: {d.influx_database_name}")
            if d.influx_database_name == "ha_Input_beyer1":
                print(f" -> Updating bucket for device {d.id} to 'ha_Input_beyer1V2'")
                await db.execute(
                    update(Device)
                    .where(Device.id == d.id)
                    .values(influx_database_name="ha_Input_beyer1V2")
                )
        await db.commit()
    print("Done.")

if __name__ == "__main__":
    asyncio.run(fix_devices())
