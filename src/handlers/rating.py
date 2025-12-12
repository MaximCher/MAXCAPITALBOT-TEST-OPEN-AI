"""
MAXCAPITAL Bot - Rating Handler
Handles user ratings for bot responses
"""

from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from src.models.dialog_rating import DialogRating

logger = structlog.get_logger()

router = Router()


def get_rating_keyboard() -> InlineKeyboardMarkup:
    """Create rating keyboard with 1-5 stars"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⭐", callback_data="rate:1"),
            InlineKeyboardButton(text="⭐⭐", callback_data="rate:2"),
            InlineKeyboardButton(text="⭐⭐⭐", callback_data="rate:3"),
            InlineKeyboardButton(text="⭐⭐⭐⭐", callback_data="rate:4"),
            InlineKeyboardButton(text="⭐⭐⭐⭐⭐", callback_data="rate:5"),
        ],
        [
            InlineKeyboardButton(text="Пропустить", callback_data="rate:skip")
        ]
    ])


async def ask_for_rating(
    message_or_callback,
    state: FSMContext,
    user_message: str,
    bot_response: str
):
    """Ask user to rate the bot's response"""
    # Store messages in state for rating
    await state.update_data(
        last_user_message=user_message,
        last_bot_response=bot_response
    )
    
    rating_text = "📊 Насколько полезен был мой ответ?\n\nВаша оценка помогает мне улучшаться!"
    
    try:
        if hasattr(message_or_callback, 'answer'):
            # It's a Message
            await message_or_callback.answer(
                rating_text,
                reply_markup=get_rating_keyboard()
            )
        else:
            # It's a callback
            await message_or_callback.message.answer(
                rating_text,
                reply_markup=get_rating_keyboard()
            )
    except Exception as e:
        logger.warning("rating_request_failed", error=str(e))


@router.callback_query(F.data.startswith("rate:"))
async def handle_rating(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession
):
    """Handle rating callback"""
    rating_str = callback.data.split(":")[1]
    
    if rating_str == "skip":
        await callback.message.edit_text("✅ Спасибо! Продолжаем диалог.")
        await callback.answer()
        return
    
    try:
        rating = int(rating_str)
        
        # Get stored messages
        state_data = await state.get_data()
        user_message = state_data.get('last_user_message')
        bot_response = state_data.get('last_bot_response')
        selected_service = state_data.get('selected_service')
        
        if not user_message or not bot_response:
            await callback.answer("Ошибка: сообщения не найдены")
            return
        
        # Save rating
        await DialogRating.create_rating(
            session=session,
            user_id=callback.from_user.id,
            user_message=user_message,
            bot_response=bot_response,
            rating=rating,
            service=selected_service
        )
        
        # Thank you message based on rating
        if rating >= 4:
            response = "⭐ Спасибо за высокую оценку! Рад, что смог помочь."
        elif rating == 3:
            response = "👍 Спасибо за оценку! Буду стараться отвечать лучше."
        else:
            response = "Спасибо за честность! Передам ваш отзыв команде для улучшения."
        
        await callback.message.edit_text(response)
        await callback.answer()
        
        logger.info(
            "rating_received",
            user_id=callback.from_user.id,
            rating=rating,
            service=selected_service
        )
        
        # Clear stored messages
        await state.update_data(
            last_user_message=None,
            last_bot_response=None
        )
        
    except ValueError:
        await callback.answer("Ошибка обработки оценки")
    except Exception as e:
        logger.error("rating_handling_failed", error=str(e))
        await callback.answer("Произошла ошибка")





