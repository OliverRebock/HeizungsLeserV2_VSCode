from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional, List

from app.core.password_policy import validate_password_strength

class UserTenantRole(BaseModel):
    tenant_id: int
    role: str
    tenant_name: str

    class Config:
        from_attributes = True

class UserBase(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    is_active: Optional[bool] = True

class UserCreate(UserBase):
    email: EmailStr
    password: str
    tenant_id: Optional[int] = None
    role: Optional[str] = "tenant_user"

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        return validate_password_strength(value)

class UserUpdate(UserBase):
    password: Optional[str] = None
    role: Optional[str] = None
    tenant_id: Optional[int] = None

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        return validate_password_strength(value)

class UserPasswordReset(BaseModel):
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, value: str) -> str:
        return validate_password_strength(value)

class User(UserBase):
    id: int
    is_superuser: bool
    tenants: List[UserTenantRole] = []

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenPayload(BaseModel):
    sub: Optional[int] = None
