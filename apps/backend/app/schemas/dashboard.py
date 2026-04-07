from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime

class DashboardBase(BaseModel):
    name: str = "Standard"
    config: List[Dict[str, Any]] = []

class DashboardCreate(DashboardBase):
    device_id: int

class DashboardUpdate(DashboardBase):
    pass

class Dashboard(DashboardBase):
    id: int
    user_id: int
    device_id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
