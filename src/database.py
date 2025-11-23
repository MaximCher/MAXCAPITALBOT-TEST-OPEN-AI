"""
MAXCAPITAL Bot - Database Module
Async database connection and session management
"""

import asyncio
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker,
    AsyncEngine
)
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import NullPool
import structlog

from src.config import settings

logger = structlog.get_logger()

# Base class for all models
Base = declarative_base()

# Global engine instance
_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


async def init_db() -> None:
    """Initialize database engine and create tables"""
    global _engine, _session_factory
    
    try:
        _engine = create_async_engine(
            settings.database_url,
            echo=settings.debug_mode,
            poolclass=NullPool,
            pool_pre_ping=True,
        )
        
        _session_factory = async_sessionmaker(
            _engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        
        # Create all tables
        async with _engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        logger.info("database_initialized", url=settings.postgres_host)
        
    except Exception as e:
        logger.error("database_init_failed", error=str(e))
        raise


async def close_db() -> None:
    """Close database connections"""
    global _engine
    
    if _engine:
        await _engine.dispose()
        logger.info("database_closed")


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Get database session (dependency injection for handlers)"""
    if not _session_factory:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    
    async with _session_factory() as session:
        try:
            yield session
        except Exception as e:
            await session.rollback()
            logger.error("session_error", error=str(e))
            raise
        finally:
            await session.close()


async def execute_raw_sql(sql: str) -> None:
    """Execute raw SQL (for migrations or special operations)"""
    if not _engine:
        raise RuntimeError("Database not initialized")
    
    async with _engine.begin() as conn:
        await conn.execute(sql)


