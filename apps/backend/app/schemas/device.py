from pydantic import BaseModel, ConfigDict, field_validator, SecretStr
from typing import Optional, Dict, Any, Union
from datetime import datetime

class DeviceResponseBase(BaseModel):
    display_name: str
    is_active: bool = True
    source_type: str = "influxdb_v2"
    influx_database_name: str
    retention_policy: Optional[str] = None
    source_config: Optional[Dict[str, Any]] = None

class DeviceCreate(DeviceResponseBase):
    tenant_id: int
    influx_token: Optional[Union[str, SecretStr]] = None

class DeviceUpdate(BaseModel):
    display_name: Optional[str] = None
    is_active: Optional[bool] = None
    influx_database_name: Optional[str] = None
    influx_token: Optional[Union[str, SecretStr]] = None
    retention_policy: Optional[str] = None
    source_config: Optional[Dict[str, Any]] = None

class Device(DeviceResponseBase):
    id: int
    tenant_id: int
    slug: str
    created_at: datetime
    updated_at: datetime
    is_online: bool = False
    last_seen: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class DeviceWithToken(DeviceResponseBase):
    """Spezielle Schema-Variante, die den Token NICHT maskiert."""
    influx_token: Optional[Union[str, SecretStr]] = None
    id: int
    tenant_id: int
    slug: str
    created_at: datetime
    updated_at: datetime
    is_online: bool = False
    last_seen: Optional[datetime] = None
    
    @field_validator("influx_token", mode="after")
    @classmethod
    def unmask_token(cls, v: Optional[Union[str, SecretStr]], info: Any) -> Optional[str]:
        """Gibt den unmaskierten Token zurück (nur für diese Schema-Variante)."""
        return v.get_secret_value() if isinstance(v, SecretStr) else v
    
    model_config = ConfigDict(from_attributes=True)
