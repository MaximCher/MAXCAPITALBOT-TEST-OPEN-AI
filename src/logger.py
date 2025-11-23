"""
MAXCAPITAL Bot - Logging Configuration
Structured logging with structlog
"""

import sys
import logging
from pathlib import Path
import structlog
from structlog.stdlib import LoggerFactory

from src.config import settings


def setup_logging() -> None:
    """Configure structured logging for the application"""
    
    # Create logs directory
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    
    # Configure standard logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.log_level.upper()),
    )
    
    # Add file handler
    file_handler = logging.FileHandler(
        logs_dir / "maxcapital_bot.log",
        encoding="utf-8"
    )
    file_handler.setLevel(logging.INFO)
    logging.root.addHandler(file_handler)
    
    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer() if not settings.debug_mode
            else structlog.dev.ConsoleRenderer()
        ],
        context_class=dict,
        logger_factory=LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    logger = structlog.get_logger()
    logger.info(
        "logging_configured",
        log_level=settings.log_level,
        debug_mode=settings.debug_mode
    )


def get_logger():
    """Get configured logger instance"""
    return structlog.get_logger()


