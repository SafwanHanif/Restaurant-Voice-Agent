import sys
from pathlib import Path

from loguru import logger

from app.config import settings


def setup_logging():
    """Configure structured logging for the application."""
    log_level = settings.LOG_LEVEL.upper()

    # Remove default handler
    logger.remove()

    # Console handler
    logger.add(
        sys.stderr,
        level=log_level,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        colorize=True,
    )

    # File handler
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    logger.add(
        log_dir / "voice_agent.log",
        level=log_level,
        rotation="10 MB",
        retention="7 days",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    )

    logger.info(f"Logging initialized at level {log_level}")
    return logger
