import pytest
import asyncio
from typing import AsyncGenerator, Generator
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import StaticPool

import sys
import os
# Add apps/backend to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "apps", "backend")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "apps", "backend", "app")))

from main import app
from app.db.session import get_db
from app.models.user import User, UserTenantLink
from app.models.tenant import Tenant
from app.core import security
from app.db.base import Base

# Use SQLite for testing
SQLALCHEMY_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
SessionTesting = async_sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

@pytest.fixture(scope="session")
def event_loop() -> Generator:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async with SessionTesting() as session:
        yield session
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def _get_test_db():
        yield db_session

    app.dependency_overrides[get_db] = _get_test_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()

async def create_test_user(db: AsyncSession, email: str, role: str = None, tenant_id: int = None, is_superuser: bool = False):
    hashed_password = security.get_password_hash("TestPass123!")
    user = User(
        email=email,
        hashed_password=hashed_password,
        is_active=True,
        is_superuser=is_superuser,
        full_name=f"Test {role or 'Admin'}"
    )
    db.add(user)
    await db.flush() # Use flush to get ID without commit if in transaction
    
    if role and tenant_id:
        link = UserTenantLink(user_id=user.id, tenant_id=tenant_id, role=role)
        db.add(link)
        await db.flush()
    
    await db.commit()
    await db.refresh(user)
    return user

def get_auth_header(user_id: int):
    token = security.create_access_token(user_id)
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture
async def platform_admin(db_session: AsyncSession):
    return await create_test_user(db_session, "platform@example.com", is_superuser=True)

@pytest.fixture
async def tenant_admin(db_session: AsyncSession, test_tenant: Tenant):
    return await create_test_user(db_session, "tenant_admin@example.com", role="tenant_admin", tenant_id=test_tenant.id)

@pytest.fixture
async def tenant_user(db_session: AsyncSession, test_tenant: Tenant):
    return await create_test_user(db_session, "tenant_user@example.com", role="tenant_user", tenant_id=test_tenant.id)

@pytest.fixture
async def test_tenant(db_session: AsyncSession):
    tenant = Tenant(name="Test Tenant", slug="test-tenant")
    db_session.add(tenant)
    await db_session.commit()
    await db_session.refresh(tenant)
    return tenant
