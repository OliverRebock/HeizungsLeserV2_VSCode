from fastapi import APIRouter
from app.api.v1.endpoints import auth, tenants, devices, data, dashboards, analysis, users

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(tenants.router, prefix="/tenants", tags=["tenants"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(devices.router, prefix="/devices", tags=["devices"])
api_router.include_router(data.router, prefix="/data", tags=["data"])
api_router.include_router(dashboards.router, prefix="/dashboards", tags=["dashboards"])
api_router.include_router(analysis.router, prefix="/analysis", tags=["analysis"])
