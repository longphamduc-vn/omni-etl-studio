# ==============================================================================
# Filepath: config/settings.py
# Updated_at: 2026-08-16 17:25:00
# Description: System configuration settings.
# ==============================================================================

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration settings."""

    app_env: str = "dev"
    db_path: str = "storage.duckdb"
    shared_schema: str = "shared_storage"
    api_timeout: int = 30
    max_retries: int = 3

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


app_config = Settings()