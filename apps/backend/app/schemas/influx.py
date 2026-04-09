from pydantic import BaseModel, ConfigDict
from typing import Optional, List, Dict, Any, Union

class EntityBase(BaseModel):
    entity_id: str
    domain: str
    friendly_name: Optional[str] = None
    data_kind: str # numeric, binary, enum, string
    value_semantics: Optional[str] = "default" # default, instant, stateful
    chartable: bool = False
    icon: Optional[str] = None
    device_class: Optional[str] = None
    unit_of_measurement: Optional[str] = None
    options: Optional[List[str]] = None

class Entity(EntityBase):
    last_seen: Optional[str] = None
    last_value: Optional[Union[float, str]] = None
    source_table: str

class DashboardDataPoint(BaseModel):
    ts: str
    value: Optional[float] = None
    state: Optional[str] = None
    is_actual: bool = True # False if it's a padding/synthetic point

class DashboardEntityData(BaseModel):
    entity_id: str
    friendly_name: str
    domain: str
    data_kind: str
    value_semantics: str = "default"
    latest_point: Optional[DashboardDataPoint] = None
    sparkline: List[DashboardDataPoint] = []
    is_stale: bool = False
    freshness_info: str = ""

class DeviceDashboardResponse(BaseModel):
    device_id: int
    entities: List[DashboardEntityData]

class DataPoint(BaseModel):
    ts: str
    value: Optional[float] = None
    state: Optional[str] = None

class TimeSeriesResponse(BaseModel):
    entity_id: str
    friendly_name: str
    domain: str
    data_kind: str
    value_semantics: str = "default"
    chartable: bool
    points: List[DataPoint]
    meta: Dict[str, Any]

class DeviceDataResponse(BaseModel):
    device_id: int
    range: Dict[str, Any]
    range_resolved: Optional[Dict[str, str]] = None
    series: List[TimeSeriesResponse]
