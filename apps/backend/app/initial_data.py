import asyncio
from app.db.base import Base # Ensure all models are loaded
from app.db.session import SessionLocal
from app.core.security import get_password_hash
from app.core.config import settings
from app.models.user import User
from sqlalchemy import select

async def seed_db():
    async with SessionLocal() as db:
        # Create superuser if not exists
        result = await db.execute(select(User).where(User.email == settings.FIRST_SUPERUSER))
        user = result.scalar_one_or_none()
        if not user:
            user = User(
                email=settings.FIRST_SUPERUSER,
                hashed_password=get_password_hash(settings.FIRST_SUPERUSER_PASSWORD),
                is_superuser=True,
                full_name="Initial Admin"
            )
            db.add(user)
            await db.commit()
            print(f"Superuser {settings.FIRST_SUPERUSER} created.")
        else:
            print(f"Superuser {settings.FIRST_SUPERUSER} already exists.")

if __name__ == "__main__":
    asyncio.run(seed_db())
