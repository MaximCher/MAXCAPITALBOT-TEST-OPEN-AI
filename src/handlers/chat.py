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
from src.vector_store import VectorStore
from src.ai_agent import AIAgent

logger = structlog.get_logger()

router = Router()


@router.message(F.text)
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
        ai_agent = AIAgent()
        ai_response = await ai_agent.generate_answer(
            user_message=user_message,
            conversation_history=conversation_history,
            vector_context=vector_context,
            user_name=user.full_name,
            selected_service=user.selected_service
        )
        
        # Add AI response to history
        await UserMemory.add_message(
            session=session,
            user_id=user_id,
            role="assistant",
            content=ai_response
        )
        
        # Check if in active consultation mode
        is_consultation = state_data.get('consultation_started', False)
        consultation_finished = state_data.get('consultation_finished', False)
        
        # Add /call reminder for active consultations
        if is_consultation and not consultation_finished:
            ai_response += "\n\n💡 Задайте следующий вопрос.\n\n"
            ai_response += "[Чтобы завершить консультацию и ожидать звонка менеджера, напишите /call]"
        
        # Send response to user
        await message.answer(ai_response)
        
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

