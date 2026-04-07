from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.api import api_router
from app.core.config import settings

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Backend für Multi-Mandanten Heizungsdaten-Visualisierung",
    version="0.1.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# CORS Konfiguration - Im lokalen Dev-Modus offen, in Produktion restriktiv.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000", 
        "http://localhost:3001",
        "http://localhost:5173"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/")
async def root():
    return {"message": "Heizungsleser V2 Backend is running"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}
