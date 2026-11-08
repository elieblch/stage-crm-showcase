from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # App
    app_name: str = "Stage CRM"
    app_env: str = "development"
    secret_key: str = "change-this-in-production"
    frontend_url: str = "http://localhost:3000"

    # Database
    database_url: str = "postgresql+asyncpg://stage_user:stage_password@db:5432/stage_crm"

    # Redis
    redis_url: str = "redis://redis:6379/0"

    # Anthropic (Claude)
    anthropic_api_key: str = ""
    claude_model: str = "claude-sonnet-4-6"

    # Gmail
    gmail_client_id: str = ""
    gmail_client_secret: str = ""
    gmail_redirect_uri: str = "http://localhost:8000/auth/gmail/callback"

    # JobTeaser
    jobteaser_base_url: str = ""
    jobteaser_email: str = ""
    jobteaser_password: str = ""
    jobteaser_session_cookie: str = ""

    # Scraping
    scraping_interval_hours: int = 24
    max_offers_per_scan: int = 100

    # SMTP newsletter
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    newsletter_recipient: str = ""
    newsletter_from_name: str = "Stage CRM"

    class Config:
        env_file = ".env"
        extra = "allow"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
