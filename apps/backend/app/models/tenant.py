from typing import TYPE_CHECKING, List
from sqlalchemy import String, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base_class import Base, TimestampMixin

if TYPE_CHECKING:
    from .user import User, UserTenantLink
    from .device import Device

class Tenant(Base, TimestampMixin):
    __tablename__ = "tenant"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # InfluxDB Integration
    influx_bucket: Mapped[str] = mapped_column(String(255), nullable=True)
    influx_token: Mapped[str] = mapped_column(String(255), nullable=True)

    users: Mapped[List["User"]] = relationship(
        secondary="user_tenant_roles", viewonly=True
    )
    devices: Mapped[List["Device"]] = relationship(back_populates="tenant")
