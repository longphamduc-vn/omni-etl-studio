from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """System-wide configuration settings loaded from environment variables or .env file."""

    # Project Information
    PROJECT_NAME: str = Field(default="omni-etl-studio", validation_alias="PROJECT_NAME")
    APP_ENV: str = Field(default="development", validation_alias="APP_ENV")
    DEBUG: bool = Field(default=True, validation_alias="DEBUG")

    # DuckDB Storage Settings
    DUCKDB_PATH: str = Field(default=":memory:", validation_alias="DUCKDB_PATH")

    # HTTP & Driver Timeouts
    DEFAULT_HTTP_TIMEOUT: int = Field(default=30, validation_alias="DEFAULT_HTTP_TIMEOUT")
    MAX_RETRIES: int = Field(default=3, validation_alias="MAX_RETRIES")

    # Directories
    WORKFLOWS_DIR: Path = BASE_DIR / "workflows"
    LOGS_DIR: Path = BASE_DIR / "logs"

    # Pydantic V2 Configuration for .env file
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()