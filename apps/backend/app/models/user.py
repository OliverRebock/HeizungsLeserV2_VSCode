from typing import TYPE_CHECKING, List
from sqlalchemy import String, ForeignKey, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base_class import Base, TimestampMixin

if TYPE_CHECKING:
    from .tenant import Tenant

class UserTenantLink(Base):
    __tablename__ = "user_tenant_roles"
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenant.id"), primary_key=True)
    role: Mapped[str] = mapped_column(String, nullable=False) # platform_admin, tenant_admin, tenant_user

    user: Mapped["User"] = relationship(back_populates="tenant_links")
    tenant: Mapped["Tenant"] = relationship()

class User(Base, TimestampMixin):
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False)

    tenant_links: Mapped[List["UserTenantLink"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", lazy="selectin"
    )

    @property
    def tenants(self):
        return [
            {
                "tenant_id": link.tenant_id,
                "role": link.role,
                "tenant_name": link.tenant.name
            }
            for link in self.tenant_links
        ]
