from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


BACKEND_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_ROOT.parent.parent if BACKEND_ROOT.parent.name == "apps" else BACKEND_ROOT
ENV_FILES = tuple(str(path) for path in dict.fromkeys((BACKEND_ROOT / ".env", REPO_ROOT / ".env")))

class Settings(BaseSettings):
    PROJECT_NAME: str = "Heizungsleser V2"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = "DEV_SECRET_KEY_DO_NOT_USE_IN_PROD"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8  # 8 days
    LOGIN_RATE_LIMIT_MAX_ATTEMPTS: int = 5
    LOGIN_RATE_LIMIT_WINDOW_SECONDS: int = 300
    LOGIN_LOCKOUT_SECONDS: int = 900
    PASSWORD_MIN_LENGTH: int = 12

    # Postgres
    POSTGRES_USER: str = "heitleser_user"
    POSTGRES_PASSWORD: str = "heitleser_pass"
    POSTGRES_DB: str = "heitleser_db"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432

    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    # InfluxDB 2 (Neues Ziel-System)
    INFLUXDB_URL: str = "http://localhost:8086"
    INFLUXDB_TOKEN: str = ""
    INFLUXDB_ORG: str = "default"
    INFLUXDB_BUCKET: str = "ha_Input_beyer1V2"
    INFLUXDB_ADMIN_TOKEN: Optional[str] = None

    # InfluxDB 3 (Legacy/Übergang - falls noch für Migration benötigt)
    INFLUXDB_V3_HOST: Optional[str] = None
    INFLUXDB_V3_TOKEN: Optional[str] = None
    INFLUXDB_V3_ORG: Optional[str] = None
    INFLUXDB_V3_DATABASE: Optional[str] = None
    INFLUXDB_V3_ADMIN_TOKEN: Optional[str] = None

    # First Superuser
    FIRST_SUPERUSER: str = "admin@example.com"
    FIRST_SUPERUSER_PASSWORD: str = "adminpass"

    # OpenAI
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL_PRIMARY: str = "gpt-5.3"
    OPENAI_TIMEOUT_SECONDS: int = 60
    OPENAI_ANALYSIS_ENABLED: bool = False

    model_config = SettingsConfigDict(
        env_file=ENV_FILES,
        case_sensitive=True,
        extra="ignore"
    )

settings = Settings()
