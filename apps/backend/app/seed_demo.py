import asyncio
from app.db.session import SessionLocal
from app.models.tenant import Tenant
from app.models.device import Device
from app.models.user import UserTenantLink # Wichtig für SQLAlchemy-Beziehungen
from sqlalchemy import select

async def seed_demo_data():
    async with SessionLocal() as db:
        # Create Beyer Tenant
        result = await db.execute(select(Tenant).where(Tenant.slug == "beyer"))
        tenant_beyer = result.scalar_one_or_none()
        if not tenant_beyer:
            tenant_beyer = Tenant(name="Heizungsbau Beyer", slug="beyer")
            db.add(tenant_beyer)
            await db.flush()
            print("Tenant Beyer created.")
            
            # Add Device for Beyer
            device_ha1 = Device(
                tenant_id=tenant_beyer.id,
                display_name="HA1 Beyer",
                slug="ha-beyer-1",
                influx_database_name="ha_Input_beyer1"
            )
            db.add(device_ha1)
            print("Device HA1 Beyer created.")

        # Create Rebock Tenant
        result = await db.execute(select(Tenant).where(Tenant.slug == "rebock"))
        tenant_rebock = result.scalar_one_or_none()
        if not tenant_rebock:
            tenant_rebock = Tenant(name="Heizungstechnik Rebock", slug="rebock")
            db.add(tenant_rebock)
            await db.flush()
            print("Tenant Rebock created.")
            
            # Add Devices for Rebock
            device_ha1_r = Device(
                tenant_id=tenant_rebock.id,
                display_name="HA1 Rebock",
                slug="ha-rebock-1",
                influx_database_name="ha_Input_rebock1"
            )
            device_ha2_r = Device(
                tenant_id=tenant_rebock.id,
                display_name="HA2 Rebock",
                slug="ha-rebock-2",
                influx_database_name="ha_Input_rebock2"
            )
            db.add(device_ha1_r)
            db.add(device_ha2_r)
            print("Devices HA1 & HA2 Rebock created.")

        await db.commit()
        print("Demo data seeding completed.")

if __name__ == "__main__":
    asyncio.run(seed_demo_data())
