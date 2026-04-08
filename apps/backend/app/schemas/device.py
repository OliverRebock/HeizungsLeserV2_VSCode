from pydantic import BaseModel, ConfigDict, field_validator, SecretStr
from typing import Optional, Dict, Any, Union
from datetime import datetime

class DeviceBase(BaseModel):
    display_name: str
    is_active: bool = True
    source_type: str = "influxdb_v2"
    influx_database_name: str
    influx_token: Optional[Union[str, SecretStr]] = None
    retention_policy: Optional[str] = None
    source_config: Optional[Dict[str, Any]] = None

class DeviceCreate(DeviceBase):
    tenant_id: int

class DeviceUpdate(BaseModel):
    display_name: Optional[str] = None
    is_active: Optional[bool] = None
    influx_database_name: Optional[str] = None
    influx_token: Optional[Union[str, SecretStr]] = None
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
    def mask_token(cls, v: Optional[Union[str, SecretStr]], info: Any) -> Optional[str]:
        """Maskiert den Influx-Token für die Standard-API-Antwort."""
        actual_value = v.get_secret_value() if isinstance(v, SecretStr) else v
        if actual_value and len(actual_value) > 8:
            return f"{actual_value[:4]}...{actual_value[-4:]}"
        return actual_value

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
    
    @field_validator("influx_token", mode="after")
    @classmethod
    def unmask_token(cls, v: Optional[Union[str, SecretStr]], info: Any) -> Optional[str]:
        """Gibt den unmaskierten Token zurück (nur für diese Schema-Variante)."""
        return v.get_secret_value() if isinstance(v, SecretStr) else v
    
    model_config = ConfigDict(from_attributes=True)
