from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime

class TenantBase(BaseModel):
    name: str
    is_active: bool = True
    influx_bucket: Optional[str] = None

class TenantCreate(TenantBase):
    influx_token: Optional[str] = None

class TenantUpdate(BaseModel):
    name: Optional[str] = None
    is_active: Optional[bool] = None

class Tenant(TenantBase):
    id: int
    slug: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TenantWithToken(Tenant):
    influx_token: Optional[str] = None
