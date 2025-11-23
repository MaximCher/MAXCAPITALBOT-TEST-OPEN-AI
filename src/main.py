"""
MAXCAPITAL Bot - Main Entry Point
Starts the bot and manages lifecycle
"""

import asyncio
import signal
import sys
from contextlib import asynccontextmanager
import structlog

from src.logger import setup_logging
from src.config import settings
from src.database import init_db, close_db
from src.bot import dp, bot, setup_handlers, setup_middlewares, on_startup, on_shutdown

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan():
    """Manage application lifecycle"""
    # Startup
    logger.info("application_starting")
    
    try:
        # Initialize database
        await init_db()
        
        # Setup bot
        setup_handlers()
        setup_middlewares()
        
        # Run startup tasks
        await on_startup()
        
        yield
        
    finally:
        # Shutdown
        logger.info("application_shutting_down")
        
        await on_shutdown()
        await close_db()
        
        logger.info("application_stopped")


async def main():
    """Main application entry point"""
    # Setup logging
    setup_logging()
    
    logger.info(
        "maxcapital_bot_initializing",
        version="1.0.0",
        environment="production" if not settings.debug_mode else "development"
    )
    
    # Handle graceful shutdown
    loop = asyncio.get_event_loop()
    shutdown_event = asyncio.Event()
    
    def signal_handler(sig, frame):
        logger.info("shutdown_signal_received", signal=sig)
        shutdown_event.set()
    
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        async with lifespan():
            # Start polling
            logger.info("starting_bot_polling")
            
            polling_task = asyncio.create_task(
                dp.start_polling(
                    bot,
                    allowed_updates=dp.resolve_used_update_types()
                )
            )
            
            # Wait for shutdown signal
            await shutdown_event.wait()
            
            # Cancel polling
            polling_task.cancel()
            
            try:
                await polling_task
            except asyncio.CancelledError:
                logger.info("polling_cancelled")
    
    except Exception as e:
        logger.error("application_error", error=str(e), exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("keyboard_interrupt_received")
    except Exception as e:
        logger.error("fatal_error", error=str(e), exc_info=True)
        sys.exit(1)


