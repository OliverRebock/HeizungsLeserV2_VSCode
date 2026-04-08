from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api import deps
from app.db.session import get_db
from app.models.user import User as UserModel, UserTenantLink
from app.schemas.user import User, UserCreate, UserUpdate, UserPasswordReset
from app.services import user as user_service

router = APIRouter()

@router.get("/", response_model=List[User])
async def read_users(
    db: AsyncSession = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: UserModel = Depends(deps.get_current_user),
    tenant_id: Optional[int] = None,
):
    """
    Retrieve users.
    - Platform admin: Can see all users, or filter by tenant.
    - Tenant admin: Can see only users of their own tenant.
    """
    if current_user.is_superuser:
        if tenant_id:
            return await user_service.get_users_by_tenant(db, tenant_id=tenant_id, skip=skip, limit=limit)
        return await user_service.get_users(db, skip=skip, limit=limit)
    
    # Check if user is tenant_admin for any tenant or specific tenant
    # For now, let's assume they might be tenant_admin in multiple, but usually one.
    # If tenant_id is provided, check if they are admin there.
    if tenant_id:
        role = await deps.check_tenant_access(tenant_id, current_user, db, required_roles=["tenant_admin"])
        return await user_service.get_users_by_tenant(db, tenant_id=tenant_id, skip=skip, limit=limit)
    
    # If no tenant_id provided, find all tenants where current_user is tenant_admin
    stmt = select(UserTenantLink.tenant_id).where(
        UserTenantLink.user_id == current_user.id,
        UserTenantLink.role == "tenant_admin"
    )
    res = await db.execute(stmt)
    admin_tenants = [r.tenant_id for r in res.all()]
    
    if not admin_tenants:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    # Return users from the first admin tenant for simplicity or combine?
    # Requirement says: tenant_admin sees users of their own tenant.
    return await user_service.get_users_by_tenant(db, tenant_id=admin_tenants[0], skip=skip, limit=limit)

@router.post("/", response_model=User)
async def create_user(
    *,
    db: AsyncSession = Depends(get_db),
    user_in: UserCreate,
    current_user: UserModel = Depends(deps.get_current_user),
):
    """
    Create new user.
    - Platform admin: Can create user for any tenant and any role.
    - Tenant admin: Can only create tenant_user for their own tenant.
    """
    if not current_user.is_superuser:
        if not user_in.tenant_id:
            raise HTTPException(status_code=400, detail="tenant_id is required for tenant admins")
        
        await deps.check_tenant_access(user_in.tenant_id, current_user, db, required_roles=["tenant_admin"])
        
        if user_in.role != "tenant_user":
             raise HTTPException(status_code=403, detail="Tenant admins can only create tenant_users")
    
    user = await user_service.get_user_by_email(db, email=user_in.email)
    if user:
        raise HTTPException(
            status_code=400,
            detail="The user with this email already exists in the system.",
        )
    return await user_service.create_user(db, user_in=user_in)

@router.get("/{user_id}", response_model=User)
async def read_user_by_id(
    user_id: int,
    current_user: UserModel = Depends(deps.get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get a specific user by id.
    """
    user = await user_service.get_user(db, user_id=user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if current_user.is_superuser:
        return user
    
    # Check if they share a tenant and current_user is admin there
    # AND the target user is NOT a platform_admin (though they shouldn't be in a tenant as such usually, but safety first)
    # AND the target user is a tenant_user or the same user (self-read is always okay)
    if user.id == current_user.id:
        return user

    for t in user.tenants:
        # t is a dict from User.tenants property
        tenant_id = t.get("tenant_id")
        role = await user_service.get_user_role_in_tenant(db, current_user.id, tenant_id)
        if role == "tenant_admin":
            # Tenant admin can see other users in their tenant.
            return user
            
    raise HTTPException(status_code=403, detail="Not enough permissions")

@router.put("/{user_id}", response_model=User)
async def update_user(
    *,
    db: AsyncSession = Depends(get_db),
    user_id: int,
    user_in: UserUpdate,
    current_user: UserModel = Depends(deps.get_current_user),
):
    """
    Update a user.
    """
    user = await user_service.get_user(db, user_id=user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if not current_user.is_superuser:
        if user.is_superuser:
            raise HTTPException(status_code=403, detail="Cannot update platform admin")
            
        # Check if current_user is admin in user's tenant
        is_allowed = False
        target_role_in_shared_tenant = None
        for t in user.tenants:
            tenant_id = t.get("tenant_id")
            role = await user_service.get_user_role_in_tenant(db, current_user.id, tenant_id)
            if role == "tenant_admin":
                target_role_in_shared_tenant = t.get("role")
                # Rule: tenant_admin can only edit tenant_user
                if target_role_in_shared_tenant == "tenant_user":
                    is_allowed = True
                    break
        
        if not is_allowed:
            raise HTTPException(status_code=403, detail="Not enough permissions. Tenant admins can only update tenant_users in their tenant.")
        
        # Tenant admin cannot change role to anything other than tenant_user
        if user_in.role and user_in.role != "tenant_user":
            raise HTTPException(status_code=403, detail="Tenant admins can only assign tenant_user role")

    return await user_service.update_user(db, db_obj=user, user_in=user_in)

@router.delete("/{user_id}", response_model=bool)
async def delete_user(
    *,
    db: AsyncSession = Depends(get_db),
    user_id: int,
    current_user: UserModel = Depends(deps.get_current_user),
):
    """
    Delete a user.
    """
    user = await user_service.get_user(db, user_id=user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if not current_user.is_superuser:
        if user.is_superuser:
             raise HTTPException(status_code=403, detail="Cannot delete platform admin")
             
        is_allowed = False
        for t in user.tenants:
            tenant_id = t.get("tenant_id")
            role = await user_service.get_user_role_in_tenant(db, current_user.id, tenant_id)
            if role == "tenant_admin":
                # Only allow deleting tenant_users
                if t.get("role") == "tenant_user":
                    is_allowed = True
                    break
        if not is_allowed:
            raise HTTPException(status_code=403, detail="Not enough permissions. Tenant admins can only delete tenant_users.")

    return await user_service.delete_user(db, user_id=user_id)

@router.post("/{user_id}/reset-password", response_model=bool)
async def reset_user_password(
    *,
    db: AsyncSession = Depends(get_db),
    user_id: int,
    password_in: UserPasswordReset,
    current_user: UserModel = Depends(deps.get_current_user),
):
    """
    Reset user password.
    """
    user = await user_service.get_user(db, user_id=user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    if not current_user.is_superuser:
        if user.is_superuser:
             raise HTTPException(status_code=403, detail="Cannot reset password for platform admin")

        is_allowed = False
        for t in user.tenants:
            tenant_id = t.get("tenant_id")
            role = await user_service.get_user_role_in_tenant(db, current_user.id, tenant_id)
            if role == "tenant_admin":
                # Tenant admin can reset password for users in their tenant.
                # Requirement 2 says: "Passwörter von Benutzern des eigenen Mandanten zurücksetzen"
                # Usually this refers to tenant_users.
                if t.get("role") == "tenant_user":
                    is_allowed = True
                    break
        if not is_allowed:
            raise HTTPException(status_code=403, detail="Not enough permissions. Tenant admins can only reset passwords for tenant_users.")

    return await user_service.reset_password(db, user_id=user_id, new_password=password_in.new_password)
