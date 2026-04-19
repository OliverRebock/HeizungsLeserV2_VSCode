from typing import TYPE_CHECKING
from sqlalchemy import String, ForeignKey, Boolean, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base_class import Base, TimestampMixin

if TYPE_CHECKING:
    from .tenant import Tenant

class Device(Base, TimestampMixin):
    __tablename__ = "device"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenant.id", ondelete="CASCADE"), index=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    
    # Abstraction for data source
    source_type: Mapped[str] = mapped_column(String(50), default="influxdb_v2")
    manufacturer: Mapped[str] = mapped_column(String(120), nullable=True)
    heat_pump_type: Mapped[str] = mapped_column(String(120), nullable=True)
    influx_database_name: Mapped[str] = mapped_column(String(255), nullable=False)
    influx_token: Mapped[str] = mapped_column(String(255), nullable=True)
    retention_policy: Mapped[str] = mapped_column(String(100), nullable=True)
    
    # Store additional config if needed
    source_config: Mapped[dict] = mapped_column(JSON, nullable=True)
    
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    tenant: Mapped["Tenant"] = relationship(back_populates="devices")
