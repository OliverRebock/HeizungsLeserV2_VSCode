from pydantic import BaseModel, EmailStr
from typing import Optional, List

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

class UserUpdate(UserBase):
    password: Optional[str] = None
    role: Optional[str] = None
    tenant_id: Optional[int] = None

class UserPasswordReset(BaseModel):
    new_password: str

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
