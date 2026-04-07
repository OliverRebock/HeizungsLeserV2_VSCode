import asyncio
from app.db.session import SessionLocal
from app.models.device import Device
from sqlalchemy import select

async def check_device():
    async with SessionLocal() as session:
        result = await session.execute(select(Device).where(Device.display_name == 'HA1 Beyer'))
        device = result.scalar_one_or_none()
        if device:
            print(f"DEVICE_ID: {device.id}")
            print(f"DISPLAY_NAME: {device.display_name}")
            print(f"SOURCE_TYPE: {device.source_type}")
            print(f"BUCKET: {device.influx_database_name}")
        else:
            print("Gerät 'HA1 Beyer' nicht gefunden.")

if __name__ == "__main__":
    asyncio.run(check_device())
