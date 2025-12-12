"""
MAXCAPITAL Bot - Lead Handler
Handles lead creation flow and Bitrix24 integration
"""

import re
from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from src.config import MESSAGES, SERVICES, settings
from src.models.user_memory import UserMemory
from src.handlers.services import LeadForm
from src.bitrix import BitrixClient
from src.ai_agent import AIAgent

logger = structlog.get_logger()

router = Router()


def parse_contact_data(text: str) -> dict:
    """
    Parse contact data from user message
    Expected format: Фамилия Имя Телефон
    Returns dict with 'full_name' and 'phone' or None if parsing failed
    """
    # Clean text
    text = text.strip()
    
    # Try to find phone number
    phone_patterns = [
        r'\+?\d[\d\s\-\(\)]{9,}',  # International format
        r'\d{10,}',  # Simple digits
    ]
    
    phone = None
    for pattern in phone_patterns:
        match = re.search(pattern, text)
        if match:
            phone = match.group(0)
            # Remove phone from text to get name
            text = text.replace(phone, '').strip()
            break
    
    if not phone:
        return None
    
    # Clean phone number
    phone = re.sub(r'[\s\-\(\)]', '', phone)
    
    # Get name (remaining text)
    name_parts = text.split()
    
    if len(name_parts) < 2:
        return None
    
    full_name = ' '.join(name_parts)
    
    return {
        'full_name': full_name,
        'phone': phone
    }


async def notify_manager(
    user_id: int,
    full_name: str,
    phone: str,
    service: str,
    comment: str
):
    """Send notification to all manager chat IDs"""
    from src.bot import bot
    
    try:
        manager_chat_ids = settings.manager_chat_ids_list
        
        if not manager_chat_ids:
            logger.warning("no_manager_chat_ids_configured")
            return
        
        notification_text = MESSAGES["lead_created"].format(
            name=full_name,
            phone=phone,
            service=SERVICES.get(service, service),
            comment=comment
        )
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="💬 Написать клиенту",
                url=f"tg://user?id={user_id}"
            )]
        ])
        
        # Send to all configured chat IDs
        success_count = 0
        for chat_id in manager_chat_ids:
            try:
                await bot.send_message(
                    chat_id=chat_id,
                    text=notification_text,
                    reply_markup=keyboard
                )
                success_count += 1
                logger.debug(
                    "notification_sent",
                    chat_id=chat_id,
                    user_id=user_id
                )
            except Exception as e:
                logger.error(
                    "notification_failed_for_chat",
                    chat_id=chat_id,
                    error=str(e)
                )
        
        logger.info(
            "manager_notified",
            total_chats=len(manager_chat_ids),
            success_count=success_count,
            user_id=user_id
        )
        
    except Exception as e:
        logger.error("manager_notification_failed", error=str(e))


async def create_lead_and_notify(
    message,  # Can be Message or CallbackQuery.message
    user_id: int,
    full_name: str,
    phone: str,
    selected_service: str,
    session: AsyncSession,
    state: FSMContext,
    loading_message=None  # Message to delete after lead creation
):
    """Create lead in Bitrix24 and notify manager (extracted for reuse)"""
    
    logger.info(
        "contact_data_received",
        user_id=user_id,
        name=full_name,
        phone=phone,
        service=selected_service
    )
    
    # Update user data in database
    await UserMemory.update_user_data(
        session=session,
        user_id=user_id,
        full_name=full_name,
        phone=phone,
        selected_service=selected_service
    )
    
    # Add to conversation history
    await UserMemory.add_message(
        session=session,
        user_id=user_id,
        role="user",
        content=f"Контактные данные: {full_name}, {phone}"
    )
    
    # Generate lead summary with AI
    try:
        ai_agent = AIAgent()
        conversation_history = await UserMemory.get_conversation_history(
            session=session,
            user_id=user_id
        )
        
        comment = await ai_agent.summarize_lead(
            user_name=full_name,
            phone=phone,
            selected_service=selected_service,
            conversation_history=conversation_history
        )
        
        logger.info(
            "lead_comment_generated",
            user_id=user_id,
            comment_length=len(comment) if comment else 0,
            comment_preview=comment[:100] if comment else "empty"
        )
    except Exception as e:
        logger.error("lead_summary_generation_failed", error=str(e))
        comment = f"Клиент заинтересован в услуге: {SERVICES.get(selected_service, selected_service)}"
    
    # Create lead in Bitrix24
    bitrix_client = BitrixClient()
    result = await bitrix_client.create_lead(
        full_name=full_name,
        phone=phone,
        selected_service=selected_service,
        comment=comment,
        user_id=user_id
    )
    
    if result.get('success'):
        lead_id = result.get('lead_id')
        logger.info(
            "lead_created_successfully",
            user_id=user_id,
            lead_id=lead_id
        )
        
        # Save lead to database for statistics
        try:
            from src.models.bitrix_lead import BitrixLead
            await BitrixLead.create(
                session=session,
                lead_id=lead_id,
                user_id=user_id,
                full_name=full_name,
                phone=phone,
                service=selected_service
            )
        except Exception as e:
            logger.warning("bitrix_lead_save_failed", error=str(e))
            # Don't fail the whole operation if saving fails
        
        # Notify manager
        await notify_manager(
            user_id=user_id,
            full_name=full_name,
            phone=phone,
            service=selected_service,
            comment=comment
        )
        
        # Delete loading message if it exists
        if loading_message:
            try:
                await loading_message.delete()
            except Exception as e:
                logger.warning("failed_to_delete_loading_message", error=str(e))
        
        # Send confirmation to user
        service_name = SERVICES.get(selected_service, selected_service)
        await message.answer(
            text=MESSAGES["data_received"].format(
                name=full_name,
                phone=phone,
                service=service_name
            ),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text="📞 Связаться с менеджером",
                    callback_data="contact_manager"
                )]
            ])
        )
        
        # Clear state and enable consultation mode
        await state.clear()
        await state.update_data(
            consultation_mode=True,
            lead_created=True
        )
        
    else:
        # Delete loading message if it exists
        if loading_message:
            try:
                await loading_message.delete()
            except Exception as e:
                logger.warning("failed_to_delete_loading_message", error=str(e))
        
        error_message = result.get('error', 'Unknown error')
        logger.error("lead_creation_failed", error=error_message)
        
        await message.answer(
            "❌ Произошла ошибка при создании заявки. "
            "Пожалуйста, свяжитесь с нами напрямую: https://maxcapital.ch/contacts"
        )


@router.message(LeadForm.waiting_for_contact_data)
async def handle_contact_data(
    message: Message,
    state: FSMContext,
    session: AsyncSession
):
    """Handle contact data input from user"""
    user_id = message.from_user.id
    text = message.text
    
    # Parse contact data
    contact_data = parse_contact_data(text)
    
    if not contact_data:
        # Показываем только текст ошибки без кнопок, чтобы не мешать диалогу
        await message.answer(
            text=MESSAGES["error_parsing"]
        )
        return
    
    full_name = contact_data['full_name']
    phone = contact_data['phone']
    
    # Get state data
    state_data = await state.get_data()
    selected_service = state_data.get('selected_service', 'unknown')
    
    # Send "Заявка создается..." message
    loading_message = await message.answer("⏳ Заявка создается...")
    
    # Create lead using the extracted function
    await create_lead_and_notify(
        message=message,
        user_id=user_id,
        full_name=full_name,
        phone=phone,
        selected_service=selected_service,
        session=session,
        state=state,
        loading_message=loading_message
    )


@router.callback_query(F.data == "finish_dialog")
async def handle_finish_dialog(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession
):
    """Handle finish dialog button - finish consultation and request contact data"""
    user_id = callback.from_user.id
    
    # Check if consultation mode is active
    state_data = await state.get_data()
    consultation_started = state_data.get('consultation_started', False)
    consultation_mode = state_data.get('consultation_mode', False)
    selected_service = state_data.get('selected_service')
    
    # Answer callback immediately
    await callback.answer()
    
    if not (consultation_started or consultation_mode):
        await callback.message.answer(
            "❌ Сначала выберите услугу и начните консультацию.\n\n"
            "Используйте /start для начала."
        )
        return
    
    # If no service selected, use general consultation
    if not selected_service:
        selected_service = "general_consultation"
        await state.update_data(selected_service=selected_service)
    
    logger.info(
        "finish_dialog_clicked",
        user_id=user_id,
        selected_service=selected_service
    )
    
    # Mark that consultation is finished
    await state.update_data(
        consultation_finished=True,
        awaiting_contact_confirmation=True
    )
    
    # Get user data
    user = await UserMemory.get_or_create(session, user_id)
    
    # Check if user already has contact data
    if user.full_name and user.phone:
        # Show confirmation with existing data
        if selected_service == "general_consultation":
            service_name = "Общая консультация"
        else:
            service_name = SERVICES.get(selected_service, selected_service)
        
        confirmation_text = f"""Ваши данные в системе:

👤 ФИО: {user.full_name}
📞 Телефон: {user.phone}
⚙️ Услуга: {service_name}

Всё верно?"""
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="✅ Верно",
                callback_data="confirm_call_data"
            )],
            [InlineKeyboardButton(
                text="✏️ Изменить",
                callback_data="change_call_data"
            )]
        ])
        
        await callback.message.answer(
            text=confirmation_text,
            reply_markup=keyboard
        )
        
        logger.info(
            "showing_existing_data_confirmation",
            user_id=user_id,
            has_data=True
        )
    else:
        # No existing data - ask for contact data
        await callback.message.answer(
            text="📞 Отлично! Для связи с менеджером укажите ваши контактные данные.\n\n"
                 "Формат: Фамилия Имя Телефон\n"
                 "Например: Иванов Иван +41791234567"
        )
        
        # Set state to waiting for contact data
        await state.set_state(LeadForm.waiting_for_contact_data)
        
        logger.info(
            "requesting_contact_data",
            user_id=user_id,
            has_data=False
        )


@router.message(Command("call"))
async def handle_call_command(
    message: Message,
    state: FSMContext,
    session: AsyncSession
):
    """
    Handle /call command - redirect to finish dialog button
    """
    user_id = message.from_user.id
    
    # Check if consultation mode is active
    state_data = await state.get_data()
    consultation_started = state_data.get('consultation_started', False)
    selected_service = state_data.get('selected_service')
    
    if not consultation_started or not selected_service:
        await message.answer(
            "❌ Сначала выберите услугу и начните консультацию.\n\n"
            "Используйте /start для начала."
        )
        return
    
    logger.info(
        "call_command_received",
        user_id=user_id,
        service=selected_service
    )
    
    # Get user data
    user = await UserMemory.get_or_create(session, user_id)
    
    # Mark that consultation is finished
    await state.update_data(
        consultation_finished=True,
        awaiting_contact_confirmation=True
    )
    
    # Check if user has existing contact data
    if user.full_name and user.phone:
        # Show existing data with confirmation buttons
        service_name = SERVICES.get(selected_service, selected_service)
        
        confirm_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="✅ Верно",
                callback_data="confirm_call_data"
            )],
            [InlineKeyboardButton(
                text="✏️ Изменить",
                callback_data="change_call_data"
            )]
        ])
        
        await message.answer(
            text=f"📋 Ваши данные в системе:\n\n"
                 f"👤 ФИО: {user.full_name}\n"
                 f"📱 Телефон: {user.phone}\n"
                 f"🎯 Услуга: {service_name}\n\n"
                 f"Всё верно?",
            reply_markup=confirm_keyboard
        )
        
        logger.info(
            "existing_contact_data_shown",
            user_id=user_id,
            has_data=True
        )
    else:
        # No existing data - ask for contact data
        await message.answer(
            text="📞 Отлично! Для связи с менеджером укажите ваши контактные данные.\n\n"
                 "Формат: Фамилия Имя Телефон\n"
                 "Например: Иванов Иван +41791234567"
        )
        
        # Set state to waiting for contact data
        await state.set_state(LeadForm.waiting_for_contact_data)
        
        logger.info(
            "requesting_contact_data",
            user_id=user_id,
            has_data=False
        )


@router.callback_query(F.data == "confirm_call_data")
async def handle_confirm_call_data(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession
):
    """Handle confirmation of contact data after /call"""
    user_id = callback.from_user.id
    
    # Answer callback immediately
    await callback.answer("⏳ Создаю заявку...")
    
    # Get user and state data
    user = await UserMemory.get_or_create(session, user_id)
    state_data = await state.get_data()
    selected_service = state_data.get('selected_service')
    
    if not user.full_name or not user.phone or not selected_service:
        await callback.message.answer("❌ Ошибка: данные не найдены")
        return
    
    # Send "Заявка создается..." message
    loading_message = await callback.message.answer("⏳ Заявка создается...")
    
    # Create lead with conversation summary
    await create_lead_and_notify(
        message=callback.message,
        user_id=user_id,
        full_name=user.full_name,
        phone=user.phone,
        selected_service=selected_service,
        session=session,
        state=state,
        loading_message=loading_message
    )
    
    logger.info("call_data_confirmed", user_id=user_id)


@router.callback_query(F.data == "change_call_data")
async def handle_change_call_data(
    callback: CallbackQuery,
    state: FSMContext
):
    """Handle request to change contact data after /call"""
    await callback.message.edit_text(
        text="📝 Пожалуйста, укажите ваши контактные данные.\n\n"
             "Формат: Фамилия Имя Телефон\n"
             "Например: Иванов Иван +41791234567"
    )
    
    # Set state to waiting for contact data
    await state.set_state(LeadForm.waiting_for_contact_data)
    
    await callback.answer()
    
    logger.info("call_data_change_requested", user_id=callback.from_user.id)

