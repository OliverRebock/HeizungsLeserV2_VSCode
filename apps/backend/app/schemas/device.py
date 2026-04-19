from pydantic import BaseModel, ConfigDict, field_validator, SecretStr, ValidationError
from typing import Optional, Dict, Any, Union
from datetime import datetime

# Known heat pump manufacturers for validation
KNOWN_MANUFACTURERS = {
    "vaillant": "Vaillant",
    "stiebel": "Stiebel Eltron",
    "stiebel eltron": "Stiebel Eltron",
    "nibe": "Nibe",
    "bosch": "Bosch",
    "ivt": "IVT",
}

class DeviceResponseBase(BaseModel):
    display_name: str
    is_active: bool = True
    source_type: str = "influxdb_v2"
    manufacturer: Optional[str] = None
    heat_pump_type: Optional[str] = None
    influx_database_name: str
    retention_policy: Optional[str] = None
    source_config: Optional[Dict[str, Any]] = None

class DeviceCreate(DeviceResponseBase):
    tenant_id: int
    influx_token: Optional[Union[str, SecretStr]] = None

    @field_validator("manufacturer", mode="before")
    @classmethod
    def validate_manufacturer(cls, v: Optional[str]) -> Optional[str]:
        """Validate and normalize manufacturer name."""
        if v is None or v.strip() == "":
            return None
        
        normalized = v.strip().lower()
        if normalized not in KNOWN_MANUFACTURERS:
            valid_options = ", ".join(sorted(set(KNOWN_MANUFACTURERS.values())))
            raise ValueError(
                f"Unknown manufacturer '{v}'. Valid options are: {valid_options}"
            )
        
        return KNOWN_MANUFACTURERS[normalized]

class DeviceUpdate(BaseModel):
    display_name: Optional[str] = None
    is_active: Optional[bool] = None
    manufacturer: Optional[str] = None
    heat_pump_type: Optional[str] = None
    influx_database_name: Optional[str] = None
    influx_token: Optional[Union[str, SecretStr]] = None
    retention_policy: Optional[str] = None
    source_config: Optional[Dict[str, Any]] = None

    @field_validator("manufacturer", mode="before")
    @classmethod
    def validate_manufacturer(cls, v: Optional[str]) -> Optional[str]:
        """Validate and normalize manufacturer name."""
        if v is None or v.strip() == "":
            return None
        
        normalized = v.strip().lower()
        if normalized not in KNOWN_MANUFACTURERS:
            valid_options = ", ".join(sorted(set(KNOWN_MANUFACTURERS.values())))
            raise ValueError(
                f"Unknown manufacturer '{v}'. Valid options are: {valid_options}"
            )
        
        return KNOWN_MANUFACTURERS[normalized]

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
