"""
MAXCAPITAL Bot - Services Handler
Handles service selection and consultation requests
"""

from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from src.config import MESSAGES, SERVICES
from src.models.user_memory import UserMemory

logger = structlog.get_logger()

router = Router()


class LeadForm(StatesGroup):
    """States for lead creation flow"""
    waiting_for_contact_data = State()


def get_back_keyboard() -> InlineKeyboardMarkup:
    """Create keyboard with back button"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад к услугам", callback_data="back_to_services")]
    ])


@router.callback_query(F.data.startswith("service:"))
async def handle_service_selection(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession
):
    """Handle service selection - start consultation immediately"""
    service_key = callback.data.split(":")[1]
    service_name = SERVICES.get(service_key, "Unknown service")
    
    user_id = callback.from_user.id
    
    logger.info(
        "service_selected",
        user_id=user_id,
        service=service_key
    )
    
    # Save selected service to database
    await UserMemory.update_user_data(
        session=session,
        user_id=user_id,
        selected_service=service_key
    )
    
    # Save to FSM state and enable consultation mode
    await state.clear()
    await state.update_data(
        selected_service=service_key,
        consultation_mode=True,
        consultation_started=True
    )
    
    # Add service selection to conversation history
    await UserMemory.add_message(
        session=session,
        user_id=user_id,
        role="system",
        content=f"Клиент выбрал услугу: {service_name}"
    )
    
    # Start consultation immediately
    consultation_text = f"""✅ Отлично! Вы выбрали: {service_name}

Я готов проконсультировать вас по данной услуге. 

Задайте ваши вопросы, расскажите о ваших целях и задачах. 
Я предоставлю детальную информацию на основе экспертизы MAXCAPITAL."""
    
    # Add finish dialog button
    finish_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="✅ Завершить диалог",
            callback_data="finish_dialog"
        )]
    ])
    
    await callback.message.edit_text(
        text=consultation_text,
        reply_markup=finish_keyboard
    )
    
    await callback.answer()
    
    logger.info(
        "consultation_started_with_service",
        user_id=user_id,
        service=service_key
    )


@router.callback_query(F.data == "consultation")
async def handle_consultation_request(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession
):
    """Handle general consultation request"""
    user_id = callback.from_user.id
    
    # Clear state and enable consultation mode
    await state.clear()
    await state.update_data(
        consultation_mode=True,
        consultation_started=True
    )
    
    # Add finish dialog button
    finish_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="✅ Завершить диалог",
            callback_data="finish_dialog"
        )],
        [InlineKeyboardButton(
            text="⬅️ Назад к услугам",
            callback_data="back_to_services"
        )]
    ])
    
    await callback.message.edit_text(
        text=MESSAGES["consultation"],
        reply_markup=finish_keyboard
    )
    
    await callback.answer()
    
    logger.info("consultation_mode_activated", user_id=callback.from_user.id)


@router.callback_query(F.data == "contact_manager")
async def handle_contact_manager(callback: CallbackQuery):
    """Handle contact manager request"""
    contact_text = MESSAGES["contact_manager"]
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🌐 Открыть сайт",
            url="https://maxcapital.ch/contacts"
        )],
        [InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data="back_to_services"
        )]
    ])
    
    await callback.message.edit_text(
        text=contact_text,
        reply_markup=keyboard
    )
    
    await callback.answer()
    
    logger.info("contact_manager_requested", user_id=callback.from_user.id)




@router.callback_query(F.data == "back_to_services")
async def handle_back_to_services(
    callback: CallbackQuery,
    state: FSMContext
):
    """Handle back to services button"""
    await state.clear()
    
    from src.handlers.start import get_welcome_keyboard
    
    await callback.message.edit_text(
        text=MESSAGES["select_service"],
        reply_markup=get_welcome_keyboard()
    )
    
    await callback.answer()

