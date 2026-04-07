from typing import TYPE_CHECKING
from sqlalchemy import String, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base_class import Base, TimestampMixin

if TYPE_CHECKING:
    from .user import User
    from .device import Device

class Dashboard(Base, TimestampMixin):
    __tablename__ = "dashboard"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), index=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("device.id", ondelete="CASCADE"), index=True)
    
    # Name des Dashboards (optional, falls ein User mehrere pro Gerät hat)
    name: Mapped[str] = mapped_column(String(255), default="Standard")
    
    # Die Widget-Konfiguration als JSON (Array von Widget-Objekten)
    config: Mapped[dict] = mapped_column(JSON, nullable=False, default=list)

    # Relationships
    user: Mapped["User"] = relationship()
    device: Mapped["Device"] = relationship()
