"""
Audit Log Model

Tracks audit events for compliance and security investigation.
"""

from datetime import datetime, timezone
from typing import Any
from sqlalchemy import String, Integer, DateTime, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base_class import Base


class AuditLogEntry(Base):
    """
    Audit log entry for tracking sensitive operations.
    
    Stores WHO did WHAT to WHOM/WHAT WHEN and WHY/HOW.
    """
    
    __tablename__ = "audit_log_entry"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    
    # When the event occurred
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )
    
    # Type of event (e.g., "user_created", "password_reset", "login_failed")
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    
    # Who performed the action (None for system events or failed login attempts)
    actor_user_id: Mapped[int] = mapped_column(Integer, nullable=True, index=True)
    
    # What was affected
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False)  # "user", "tenant", "device", etc.
    resource_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    
    # Multi-tenant context
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=True, index=True)
    
    # Additional context as JSON
    # Example: {"old_value": "user", "new_value": "admin", "ip_address": "192.168.1.1"}
    details: Mapped[Any] = mapped_column(JSON, nullable=True)
    
    # Human-readable description
    description: Mapped[str] = mapped_column(Text, nullable=True)
    
    def __repr__(self) -> str:
        return (
            f"<AuditLogEntry(timestamp={self.timestamp}, event_type={self.event_type}, "
            f"actor_user_id={self.actor_user_id}, resource={self.resource_type}:{self.resource_id})>"
        )
