# ==============================================================================
# Filepath: core/common/logger.py
# Updated_at: 2026-08-16 17:25:00
# Description: Centralized logging setup.
# ==============================================================================

import logging
import sys


def init_logger(name: str = "omni_etl") -> logging.Logger:
    """Creates a standardized stream logger."""
    logger = logging.getLogger(name)

    if not logger.handlers:
        logger.setLevel(logging.INFO)
        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger


log = init_logger()