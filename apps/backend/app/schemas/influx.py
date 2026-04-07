from pydantic import BaseModel, ConfigDict
from typing import Optional, List, Dict, Any, Union

class EntityBase(BaseModel):
    entity_id: str
    domain: str
    friendly_name: Optional[str] = None
    data_kind: str # numeric, binary, enum, string
    chartable: bool = False
    icon: Optional[str] = None
    device_class: Optional[str] = None
    unit_of_measurement: Optional[str] = None
    options: Optional[List[str]] = None

class Entity(EntityBase):
    last_seen: Optional[str] = None
    last_value: Optional[Union[float, str]] = None # Neu hinzugefügt
    source_table: str

class DataPoint(BaseModel):
    ts: str
    value: Optional[float] = None
    state: Optional[str] = None

class TimeSeriesResponse(BaseModel):
    entity_id: str
    friendly_name: str
    domain: str
    data_kind: str
    chartable: bool
    points: List[DataPoint]
    meta: Dict[str, Any]

class DeviceDataResponse(BaseModel):
    device_id: int
    range: Dict[str, Any]
    series: List[TimeSeriesResponse]
