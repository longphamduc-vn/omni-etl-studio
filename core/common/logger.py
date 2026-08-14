import sys
from pathlib import Path
from loguru import logger
from config.settings import settings


def setup_logger():
    """Configures system-wide logging formatting, log levels, and sink file rotation."""
    logger.remove()  # Clear default handlers

    log_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>"
    )

    # Console Handler
    logger.add(
        sys.stdout,
        format=log_format,
        level="DEBUG" if settings.DEBUG else "INFO",
        colorize=True
    )

    # Rotating File Handler (Production Debugging)
    log_dir = settings.LOGS_DIR
    log_dir.mkdir(parents=True, exist_ok=True)
    
    logger.add(
        log_dir / "omni_etl.log",
        format=log_format,
        level="INFO",
        rotation="10 MB",
        retention="7 days",
        enqueue=True
    )

    return logger


log = setup_logger()