"""
MAXCAPITAL Bot - Start Handler
Handles /start command and welcome message
"""

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from src.config import MESSAGES, SERVICES
from src.models.user_memory import UserMemory

logger = structlog.get_logger()

router = Router()


def get_welcome_keyboard() -> InlineKeyboardMarkup:
    """Create welcome keyboard with service selection"""
    buttons = []
    
    # Service buttons (2 per row)
    service_items = list(SERVICES.items())
    for i in range(0, len(service_items), 2):
        row = []
        for key, name in service_items[i:i+2]:
            row.append(InlineKeyboardButton(
                text=name,
                callback_data=f"service:{key}"
            ))
        buttons.append(row)
    
    # Consultation button
    buttons.append([
        InlineKeyboardButton(
            text="💬 Получить консультацию онлайн",
            callback_data="consultation"
        )
    ])
    
    # Contact manager button
    buttons.append([
        InlineKeyboardButton(
            text="📞 Связаться с менеджером",
            callback_data="contact_manager"
        )
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message(Command("start"))
async def cmd_start(
    message: Message,
    state: FSMContext,
    session: AsyncSession
):
    """Handle /start command"""
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    
    logger.info(
        "user_started_bot",
        user_id=user_id,
        username=username
    )
    
    # Create or get user in database
    user = await UserMemory.get_or_create(session, user_id)
    
    # Clear any previous state
    await state.clear()
    
    # Send welcome message
    await message.answer(
        text=MESSAGES["welcome"],
        reply_markup=get_welcome_keyboard()
    )
    
    logger.debug("welcome_message_sent", user_id=user_id)


@router.message(Command("help"))
async def cmd_help(message: Message):
    """Handle /help command"""
    help_text = """🤖 MAXCAPITAL Bot - Помощь

Доступные команды:
/start - Начать работу с ботом
/call - Завершить консультацию и связаться с менеджером
/help - Показать это сообщение
/services - Выбрать услугу
/cancel - Отменить текущее действие

Как использовать бота:
1️⃣ Выберите интересующую услугу
2️⃣ Получите консультацию от AI-ассистента
3️⃣ Напишите /call для связи с менеджером
4️⃣ Подтвердите контактные данные
5️⃣ Менеджер свяжется с вами

🌐 Наш сайт: https://maxcapital.ch/
📧 Контакты: https://maxcapital.ch/contacts"""
    
    await message.answer(help_text)


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    """Handle /cancel command"""
    current_state = await state.get_state()
    
    if current_state is None:
        await message.answer(
            "Нет активных действий для отмены.\n\n"
            "Используйте /start для начала работы."
        )
        return
    
    await state.clear()
    await message.answer(
        "✅ Действие отменено.\n\n"
        "Используйте /start для начала работы.",
        reply_markup=get_welcome_keyboard()
    )
    
    logger.info("user_cancelled_action", user_id=message.from_user.id)


@router.message(Command("services"))
async def cmd_services(message: Message):
    """Handle /services command"""
    await message.answer(
        MESSAGES["select_service"],
        reply_markup=get_welcome_keyboard()
    )

