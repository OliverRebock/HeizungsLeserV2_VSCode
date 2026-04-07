from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.config import settings
from app.core.security import ALGORITHM
from app.db.session import get_db
from app.models.user import User, UserTenantLink
from app.schemas.user import TokenPayload

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/login"
)

async def get_current_user(
    db: AsyncSession = Depends(get_db), token: str = Depends(oauth2_scheme)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[ALGORITHM]
        )
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        token_data = TokenPayload(sub=int(user_id))
    except (JWTError, ValueError):
        raise credentials_exception
    
    result = await db.execute(select(User).where(User.id == token_data.sub))
    user = result.scalar_one_or_none()
    
    if user is None:
        raise credentials_exception
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return user

def get_current_active_superuser(
    current_user: User = Depends(get_current_user),
) -> User:
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=403, detail="The user doesn't have enough privileges"
        )
    return current_user

# Role-based check helper (Tenant scoped)
async def check_tenant_access(
    tenant_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    required_roles: list[str] = None
):
    if current_user.is_superuser:
        return True
    
    # Check if user has membership in tenant
    stmt = select(UserTenantLink).where(
        UserTenantLink.user_id == current_user.id,
        UserTenantLink.tenant_id == tenant_id
    )
    result = await db.execute(stmt)
    membership = result.scalar_one_or_none()
    
    if not membership:
        raise HTTPException(status_code=403, detail="Not a member of this tenant")
    
    if required_roles and membership.role not in required_roles:
        raise HTTPException(status_code=403, detail="Insufficient permissions within tenant")
    
    return membership.role
