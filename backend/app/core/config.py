from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # App
    app_name: str = "Stage CRM"
    app_env: str = "development"
    frontend_url: str = "http://localhost:3000"

    # Database
    database_url: str = "postgresql+asyncpg://stage_user:stage_password@db:5432/stage_crm"

    # Uploads (PDF CV / LM)
    upload_dir: str = "/app/uploads"
    max_upload_bytes: int = 10 * 1024 * 1024  # 10 Mo

    # Utilisateur unique (mode mono-utilisateur, pas d'auth pour l'instant)
    single_user_id: int = 1

    class Config:
        env_file = ".env"
        extra = "allow"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
