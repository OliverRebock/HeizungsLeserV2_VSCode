from pydantic import BaseModel, ConfigDict, field_validator
from typing import Optional, Dict, Any
from datetime import datetime

class DeviceBase(BaseModel):
    display_name: str
    is_active: bool = True
    source_type: str = "influxdb_v2"
    influx_database_name: str
    influx_token: Optional[str] = None
    retention_policy: Optional[str] = None
    source_config: Optional[Dict[str, Any]] = None

class DeviceCreate(DeviceBase):
    tenant_id: int

class DeviceUpdate(BaseModel):
    display_name: Optional[str] = None
    is_active: Optional[bool] = None
    influx_database_name: Optional[str] = None
    influx_token: Optional[str] = None
    retention_policy: Optional[str] = None
    source_config: Optional[Dict[str, Any]] = None

class Device(DeviceBase):
    id: int
    tenant_id: int
    slug: str
    created_at: datetime
    updated_at: datetime
    is_online: bool = False
    last_seen: Optional[datetime] = None

    @field_validator("influx_token", mode="after")
    @classmethod
    def mask_token(cls, v: Optional[str], info: Any) -> Optional[str]:
        """Maskiert den Influx-Token für die Standard-API-Antwort."""
        # Wir maskieren nur in der regulären Device-Antwort
        if v and len(v) > 8:
            return f"{v[:4]}...{v[-4:]}"
        return v

    model_config = ConfigDict(from_attributes=True)

class DeviceWithToken(DeviceBase):
    """Spezielle Schema-Variante, die den Token NICHT maskiert."""
    id: int
    tenant_id: int
    slug: str
    created_at: datetime
    updated_at: datetime
    is_online: bool = False
    last_seen: Optional[datetime] = None
    
    # Hier KEIN mask_token Validator!
    
    model_config = ConfigDict(from_attributes=True)
