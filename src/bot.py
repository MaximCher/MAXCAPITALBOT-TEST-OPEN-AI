"""
MAXCAPITAL Bot - Main Bot Setup
Configures and initializes the Telegram bot
"""

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
import structlog

from src.config import settings
from src.handlers import (
    start_router,
    services_router,
    lead_router,
    chat_router
)

logger = structlog.get_logger()

# Initialize bot with parse mode
bot = Bot(
    token=settings.telegram_bot_token,
    parse_mode=ParseMode.HTML
)

# Initialize dispatcher with FSM storage
storage = MemoryStorage()
dp = Dispatcher(storage=storage)


def setup_handlers() -> None:
    """Register all handlers in correct order"""
    # Order matters! More specific handlers should be registered first
    # Chat handler should be last as it catches all text messages
    
    dp.include_router(start_router)
    dp.include_router(services_router)
    dp.include_router(lead_router)
    dp.include_router(chat_router)  # Should be last
    
    logger.info("handlers_registered")


def setup_middlewares() -> None:
    """Setup middlewares for database sessions and logging"""
    from aiogram import BaseMiddleware
    from aiogram.types import TelegramObject
    from typing import Callable, Dict, Any, Awaitable
    from sqlalchemy.ext.asyncio import AsyncSession
    
    from src.database import get_session
    
    class DatabaseMiddleware(BaseMiddleware):
        """Middleware to inject database session into handlers"""
        
        async def __call__(
            self,
            handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
            event: TelegramObject,
            data: Dict[str, Any]
        ) -> Any:
            async for session in get_session():
                data["session"] = session
                return await handler(event, data)
    
    # Register middleware
    dp.update.middleware(DatabaseMiddleware())
    
    logger.info("middlewares_registered")


async def setup_bot_commands():
    """Set bot commands in Telegram menu"""
    from aiogram.types import BotCommand
    
    commands = [
        BotCommand(command="start", description="Начать работу с ботом"),
        BotCommand(command="call", description="Завершить консультацию и связаться с менеджером"),
        BotCommand(command="help", description="Помощь"),
        BotCommand(command="services", description="Выбрать услугу"),
        BotCommand(command="cancel", description="Отменить текущее действие"),
    ]
    
    await bot.set_my_commands(commands)
    logger.info("bot_commands_set")


async def on_startup():
    """Actions on bot startup"""
    logger.info("bot_starting")
    
    # Set bot commands
    await setup_bot_commands()
    
    # Get bot info
    bot_info = await bot.get_me()
    logger.info(
        "bot_started",
        bot_id=bot_info.id,
        bot_username=bot_info.username,
        bot_name=bot_info.first_name
    )


async def on_shutdown():
    """Actions on bot shutdown"""
    logger.info("bot_shutting_down")
    await bot.session.close()
    logger.info("bot_stopped")

