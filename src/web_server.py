"""
MAXCAPITAL Bot - Web Server Entry Point
Runs FastAPI admin panel
"""

import asyncio
import uvicorn
from src.database import init_db, close_db
from src.config import settings
from src.web.api import app
import structlog

logger = structlog.get_logger()


@app.on_event("startup")
async def startup_event():
    """Initialize database on startup"""
    logger.info("web_server_starting")
    await init_db()
    logger.info("web_server_started")


@app.on_event("shutdown")
async def shutdown_event():
    """Close database on shutdown"""
    logger.info("web_server_shutting_down")
    await close_db()
    logger.info("web_server_stopped")


if __name__ == "__main__":
    uvicorn.run(
        "src.web_server:app",
        host=settings.web_host,
        port=settings.web_port,
        reload=False,
        log_level="info"
    )

