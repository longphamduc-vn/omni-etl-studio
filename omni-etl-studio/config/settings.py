from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    """System-wide configuration settings loaded from environment variables or defaults."""

    PROJECT_NAME: str = "omni-etl-studio"
    APP_ENV: str = Field(default="development")
    DEBUG: bool = Field(default=True)

    # Storage Settings
    DUCKDB_PATH: str = Field(default=":memory:")

    # Network & Protocol Timeouts
    DEFAULT_HTTP_TIMEOUT: int = Field(default=30)
    MAX_RETRIES: int = Field(default=3)

    # Directory Paths
    WORKFLOWS_DIR: Path = BASE_DIR / "workflows"
    LOGS_DIR: Path = BASE_DIR / "logs"

    # Pydantic V2 Configuration
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()