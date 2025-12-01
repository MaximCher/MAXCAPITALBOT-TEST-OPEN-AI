"""
MAXCAPITAL Bot - Chat Handler
Handles AI-powered conversations with RAG support
"""

from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from src.models.user_memory import UserMemory
from src.models.dialog_message import DialogMessage
from src.vector_store import VectorStore
from src.ai_agent import AIAgent

logger = structlog.get_logger()

router = Router()


@router.message(F.text & ~F.text.startswith('/'))
async def handle_text_message(
    message: Message,
    state: FSMContext,
    session: AsyncSession
):
    """
    Handle all text messages (AI consultation)
    This handler should be registered last (lowest priority)
    """
    user_id = message.from_user.id
    user_message = message.text
    
    if not user_message or len(user_message) > 4000:
        await message.answer(
            "❌ Сообщение слишком длинное. Пожалуйста, сократите ваш вопрос."
        )
        return
    
    logger.info(
        "user_message_received",
        user_id=user_id,
        message_length=len(user_message)
    )
    
    # Get state data
    state_data = await state.get_data()
    consultation_mode = state_data.get('consultation_mode', False)
    lead_created = state_data.get('lead_created', False)
    awaiting_contact = state_data.get('awaiting_contact_confirmation', False)
    
    # Don't respond if waiting for contact confirmation/input
    if awaiting_contact:
        return
    
    # Only respond with AI if in consultation mode or after lead creation
    if not (consultation_mode or lead_created):
        # User hasn't started proper flow, redirect to /start
        await message.answer(
            "Пожалуйста, начните с выбора услуги.\n\n"
            "Используйте /start для начала работы."
        )
        return
    
    # Show typing indicator
    await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")
    
    try:
        # Get user data
        user = await UserMemory.get_or_create(session, user_id)
        
        # Add user message to history
        await UserMemory.add_message(
            session=session,
            user_id=user_id,
            role="user",
            content=user_message
        )
        
        # Save user message to dialog history for admin panel
        await DialogMessage.create(
            session=session,
            user_id=user_id,
            username=message.from_user.username,
            full_name=user.full_name,
            phone=user.phone,
            message_text=user_message,
            role="user",
            chat_id=message.chat.id,
            message_id=message.message_id
        )
        
        # Get conversation history
        conversation_history = await UserMemory.get_conversation_history(
            session=session,
            user_id=user_id,
            limit=10
        )
        
        # Get relevant context from vector store (RAG)
        vector_store = VectorStore(session)
        vector_context = await vector_store.get_context_for_query(
            query=user_message,
            max_context_length=2000
        )
        
        logger.info(
            "rag_context_retrieved",
            user_id=user_id,
            context_length=len(vector_context) if vector_context else 0,
            has_context=bool(vector_context)
        )
        
        # Generate AI response
        # Use selected_service from state if available, otherwise from user
        selected_service = state_data.get('selected_service') or user.selected_service
        
        ai_agent = AIAgent()
        ai_response = await ai_agent.generate_answer(
            user_message=user_message,
            conversation_history=conversation_history,
            vector_context=vector_context,
            user_name=user.full_name,
            selected_service=selected_service
        )
        
        # Add AI response to history
        await UserMemory.add_message(
            session=session,
            user_id=user_id,
            role="assistant",
            content=ai_response
        )
        
        # Save AI response to dialog history for admin panel
        await DialogMessage.create(
            session=session,
            user_id=user_id,
            username=message.from_user.username,
            full_name=user.full_name,
            phone=user.phone,
            message_text=ai_response,
            role="assistant",
            chat_id=message.chat.id
        )
        
        # Check if in active consultation mode
        is_consultation = state_data.get('consultation_started', False)
        consultation_finished = state_data.get('consultation_finished', False)
        consultation_mode = state_data.get('consultation_mode', False)
        
        # Add finish dialog button for active consultations
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        reply_markup = None
        if (is_consultation or consultation_mode) and not consultation_finished:
            reply_markup = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text="✅ Завершить диалог",
                    callback_data="finish_dialog"
                )]
            ])
        
        # Send response to user
        await message.answer(ai_response, reply_markup=reply_markup)
        
        logger.info(
            "ai_response_sent",
            user_id=user_id,
            response_length=len(ai_response),
            is_consultation=is_consultation
        )
        
    except Exception as e:
        logger.error("chat_handling_failed", user_id=user_id, error=str(e))
        
        await message.answer(
            "❌ Извините, произошла ошибка при обработке вашего сообщения.\n\n"
            "Попробуйте еще раз или свяжитесь с нашим менеджером: "
            "https://maxcapital.ch/contacts"
        )

