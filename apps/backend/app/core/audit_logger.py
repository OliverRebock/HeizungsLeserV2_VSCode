"""
Audit Logging Module

Logs all sensitive mutations (user create/update/delete, password reset, tenant changes, etc.)
for compliance, debugging, and security investigation.
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from enum import Enum
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import Column, Integer, String, DateTime, JSON, Text
from sqlalchemy.orm import declarative_base

logger = logging.getLogger(__name__)

# Will be set by app initialization
Base = None


class AuditEventType(str, Enum):
    """Types of auditable events."""
    
    # User operations
    USER_CREATED = "user_created"
    USER_UPDATED = "user_updated"
    USER_DELETED = "user_deleted"
    USER_PASSWORD_RESET = "user_password_reset"
    USER_PASSWORD_CHANGED = "user_password_changed"
    
    # Tenant operations
    TENANT_CREATED = "tenant_created"
    TENANT_UPDATED = "tenant_updated"
    TENANT_DELETED = "tenant_deleted"
    TENANT_MEMBER_ADDED = "tenant_member_added"
    TENANT_MEMBER_REMOVED = "tenant_member_removed"
    TENANT_MEMBER_ROLE_CHANGED = "tenant_member_role_changed"
    
    # Device operations
    DEVICE_CREATED = "device_created"
    DEVICE_UPDATED = "device_updated"
    DEVICE_DELETED = "device_deleted"
    DEVICE_TOKEN_RESET = "device_token_reset"
    
    # Authentication
    LOGIN_FAILED = "login_failed"
    LOGIN_FAILED_RATE_LIMITED = "login_failed_rate_limited"
    
    # API Access
    API_ACCESS_DENIED = "api_access_denied"


class AuditLog:
    """
    Audit log entry model.
    
    Tracks WHO (actor_user_id) did WHAT (event_type) to WHOM/WHAT (resource_id)
    WHEN (timestamp) and WHY/HOW (details as JSON).
    """
    
    __tablename__ = "audit_log"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Timestamp of the event (UTC)
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
    
    # Type of event (enum stored as string)
    event_type = Column(String(50), nullable=False, index=True)
    
    # Actor: user ID who performed the action (can be None for system actions)
    actor_user_id = Column(Integer, nullable=True, index=True)
    
    # Resource: what was affected (user_id, tenant_id, device_id, etc.)
    resource_type = Column(String(50), nullable=False)  # e.g., "user", "tenant", "device"
    resource_id = Column(String(255), nullable=False, index=True)
    
    # Tenant context (for multi-tenant auditing)
    tenant_id = Column(Integer, nullable=True, index=True)
    
    # Details: JSON object with additional context
    # Example: {"old_role": "user", "new_role": "admin", "ip_address": "192.168.1.1"}
    details = Column(JSON, nullable=True)
    
    # Free-form description
    description = Column(Text, nullable=True)


class AuditLogger:
    """
    Logs audit events to the database.
    
    Usage:
        await AuditLogger.log(
            db=session,
            event_type=AuditEventType.USER_PASSWORD_RESET,
            actor_user_id=current_user.id,
            resource_type="user",
            resource_id=str(target_user.id),
            tenant_id=target_user.primary_tenant_id,
            details={"reset_by_admin": True, "ip_address": "10.0.0.1"},
            description=f"Admin reset password for user {target_user.email}"
        )
    """
    
    @staticmethod
    async def log(
        db: AsyncSession,
        event_type: AuditEventType,
        actor_user_id: Optional[int] = None,
        resource_type: str = "unknown",
        resource_id: str = "unknown",
        tenant_id: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
        description: Optional[str] = None,
    ) -> None:
        """
        Logs an audit event asynchronously.
        
        Args:
            db: AsyncSession for database access
            event_type: Type of event (from AuditEventType enum)
            actor_user_id: ID of user who performed the action
            resource_type: Type of resource affected (user, tenant, device, etc.)
            resource_id: ID of resource affected
            tenant_id: Tenant context (for multi-tenant queries)
            details: JSON-serializable dict with additional context
            description: Human-readable description of the event
        """
        try:
            # Import here to avoid circular dependency
            from app.models.audit import AuditLogEntry
            
            now = datetime.now(timezone.utc)
            
            entry = AuditLogEntry(
                timestamp=now,
                event_type=event_type.value if isinstance(event_type, AuditEventType) else event_type,
                actor_user_id=actor_user_id,
                resource_type=resource_type,
                resource_id=resource_id,
                tenant_id=tenant_id,
                details=details or {},
                description=description,
            )
            
            db.add(entry)
            await db.flush()
            
            logger.info(
                f"AUDIT: {event_type.value if isinstance(event_type, AuditEventType) else event_type} | "
                f"Actor: {actor_user_id} | Resource: {resource_type}:{resource_id} | "
                f"Tenant: {tenant_id} | {description or ''}"
            )
            
        except Exception as exc:
            # Log audit failures but don't crash the application
            logger.error(f"Failed to write audit log: {exc}", exc_info=True)
    
    @staticmethod
    async def log_user_created(
        db: AsyncSession,
        actor_user_id: Optional[int],
        new_user_id: int,
        new_user_email: str,
        tenant_id: Optional[int] = None,
        ip_address: Optional[str] = None,
    ) -> None:
        """Logs user creation."""
        await AuditLogger.log(
            db=db,
            event_type=AuditEventType.USER_CREATED,
            actor_user_id=actor_user_id,
            resource_type="user",
            resource_id=str(new_user_id),
            tenant_id=tenant_id,
            details={"email": new_user_email, "ip_address": ip_address},
            description=f"Created user: {new_user_email}",
        )
    
    @staticmethod
    async def log_user_deleted(
        db: AsyncSession,
        actor_user_id: Optional[int],
        deleted_user_id: int,
        deleted_user_email: str,
        tenant_id: Optional[int] = None,
        ip_address: Optional[str] = None,
    ) -> None:
        """Logs user deletion."""
        await AuditLogger.log(
            db=db,
            event_type=AuditEventType.USER_DELETED,
            actor_user_id=actor_user_id,
            resource_type="user",
            resource_id=str(deleted_user_id),
            tenant_id=tenant_id,
            details={"email": deleted_user_email, "ip_address": ip_address},
            description=f"Deleted user: {deleted_user_email}",
        )
    
    @staticmethod
    async def log_password_reset(
        db: AsyncSession,
        actor_user_id: Optional[int],
        target_user_id: int,
        target_user_email: str,
        reset_type: str = "admin",
        tenant_id: Optional[int] = None,
        ip_address: Optional[str] = None,
    ) -> None:
        """Logs password reset."""
        await AuditLogger.log(
            db=db,
            event_type=AuditEventType.USER_PASSWORD_RESET,
            actor_user_id=actor_user_id,
            resource_type="user",
            resource_id=str(target_user_id),
            tenant_id=tenant_id,
            details={
                "email": target_user_email,
                "reset_type": reset_type,  # "admin" or "self"
                "ip_address": ip_address,
            },
            description=f"{reset_type.capitalize()} reset password for {target_user_email}",
        )
    
    @staticmethod
    async def log_tenant_member_added(
        db: AsyncSession,
        actor_user_id: Optional[int],
        tenant_id: int,
        member_user_id: int,
        member_email: str,
        role: str = "user",
        ip_address: Optional[str] = None,
    ) -> None:
        """Logs tenant member addition."""
        await AuditLogger.log(
            db=db,
            event_type=AuditEventType.TENANT_MEMBER_ADDED,
            actor_user_id=actor_user_id,
            resource_type="tenant_member",
            resource_id=str(tenant_id),
            tenant_id=tenant_id,
            details={
                "member_user_id": member_user_id,
                "member_email": member_email,
                "role": role,
                "ip_address": ip_address,
            },
            description=f"Added {member_email} to tenant as {role}",
        )
    
    @staticmethod
    async def log_login_failed(
        db: AsyncSession,
        email: str,
        reason: str = "invalid_credentials",
        ip_address: Optional[str] = None,
    ) -> None:
        """Logs failed login attempt."""
        await AuditLogger.log(
            db=db,
            event_type=AuditEventType.LOGIN_FAILED,
            actor_user_id=None,
            resource_type="login",
            resource_id=email,
            details={"reason": reason, "ip_address": ip_address},
            description=f"Failed login attempt for {email}: {reason}",
        )
    
    @staticmethod
    async def log_login_rate_limited(
        db: AsyncSession,
        email: str,
        ip_address: Optional[str] = None,
        lockout_seconds: int = 900,
    ) -> None:
        """Logs rate-limited login attempt."""
        await AuditLogger.log(
            db=db,
            event_type=AuditEventType.LOGIN_FAILED_RATE_LIMITED,
            actor_user_id=None,
            resource_type="login",
            resource_id=email,
            details={
                "reason": "rate_limited",
                "ip_address": ip_address,
                "lockout_seconds": lockout_seconds,
            },
            description=f"Rate-limited login attempt for {email} from {ip_address}",
        )


# Convenience functions
async def audit_user_created(
    db: AsyncSession,
    actor_user_id: Optional[int],
    new_user_id: int,
    new_user_email: str,
    ip_address: Optional[str] = None,
) -> None:
    """Convenience wrapper."""
    await AuditLogger.log_user_created(
        db=db,
        actor_user_id=actor_user_id,
        new_user_id=new_user_id,
        new_user_email=new_user_email,
        ip_address=ip_address,
    )


async def audit_password_reset(
    db: AsyncSession,
    actor_user_id: Optional[int],
    target_user_id: int,
    target_user_email: str,
    ip_address: Optional[str] = None,
) -> None:
    """Convenience wrapper."""
    await AuditLogger.log_password_reset(
        db=db,
        actor_user_id=actor_user_id,
        target_user_id=target_user_id,
        target_user_email=target_user_email,
        ip_address=ip_address,
    )
