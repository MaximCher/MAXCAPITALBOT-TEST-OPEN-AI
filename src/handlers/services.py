"""
MAXCAPITAL Bot - Services Handler
Handles service selection and consultation requests
"""

from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession
import structlog
from typing import List, Optional

from src.config import MESSAGES, SERVICES, SERVICE_FLOWS, GLOBAL_FINAL_MESSAGE, PARTNERSHIP_AGREEMENT_TEXT
from src.models.user_memory import UserMemory

logger = structlog.get_logger()

router = Router()


class LeadForm(StatesGroup):
    """States for lead creation flow"""
    waiting_for_contact_data = State()


class ServiceQuestionnaire(StatesGroup):
    """Анкетирование по выбранному направлению"""
    waiting_for_answer = State()


def _common_actions_keyboard(extra_rows: Optional[List[List[InlineKeyboardButton]]] = None, show_wait_manager: bool = False) -> InlineKeyboardMarkup:
    """
    Общие кнопки в конце каждого сообщения:
    - ВЕРНУТЬСЯ В МЕНЮ (нейтральная)
    - ОЖИДАТЬ МЕНЕДЖЕРА - только если show_wait_manager=True
    Можно дополнительно передать extra_rows с другими кнопками.
    """
    rows: list[list[InlineKeyboardButton]] = extra_rows[:] if extra_rows else []
    
    # Только кнопка меню (по умолчанию), без "Ожидать менеджера" после создания лида
    rows.append([
        InlineKeyboardButton(
            text="⬅️ ВЕРНУТЬСЯ В МЕНЮ",
            callback_data="back_to_menu"
        )
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


class PartnershipFlow(StatesGroup):
    """Состояние для партнёрского флоу"""
    waiting_agreement = State()
    waiting_contact_data = State()


@router.callback_query(F.data.startswith("service:"))
async def handle_service_selection(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession
):
    """
    Handle service selection:
    1) показываем описание направления
    2) для партнёрства - отправляем документ с кнопкой "Согласен"
    3) задаём базовые вопросы (анкета)
    4) после анкеты переводим пользователя в режим консультации с AI
    """
    service_key = callback.data.split(":")[1]
    service_name = SERVICES.get(service_key, "Unknown service")
    flow = SERVICE_FLOWS.get(service_key)
    user_id = callback.from_user.id

    logger.info(
        "service_selected",
        user_id=user_id,
        service=service_key
    )

    # Особый случай: ПАРТНЁРСТВО — отправляем документ с кнопкой "Согласен"
    if service_key == "partnership":
        await state.clear()
        await state.update_data(selected_service=service_key)
        await state.set_state(PartnershipFlow.waiting_agreement)
        
        # Сохраняем в базе
        await UserMemory.update_user_data(
            session=session,
            user_id=user_id,
            selected_service=service_key
        )
        
        # Добавляем системное сообщение
        await UserMemory.add_message(
            session=session,
            user_id=user_id,
            role="system",
            content="Клиент выбрал: Партнёрство / Стать агентом"
        )
        
        # Отправляем описание + соглашение
        description = flow.get("description", "") if flow else ""
        full_text = f"{description}\n\n{'─'*30}\n\n{PARTNERSHIP_AGREEMENT_TEXT}"
        
        agreement_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="✅ Согласен с условиями",
                callback_data="partnership_agree"
            )],
            [InlineKeyboardButton(
                text="⬅️ Вернуться в меню",
                callback_data="back_to_menu"
            )]
        ])
        
        await callback.message.answer(
            text=full_text,
            reply_markup=agreement_keyboard
        )
        await callback.answer()
        return

    if not flow:
        # Фолбэк: если по какой-то причине нет конфигурации анкеты - сразу AI режим
        await callback.message.answer(
            text=f"✅ Отлично! Вы выбрали: {service_name}\n\n"
                 "Я готов проконсультировать вас по данной услуге.\n\n"
                 "Задайте ваши вопросы, расскажите о ваших целях и задачах.",
            reply_markup=_common_actions_keyboard()
        )
        await state.clear()
        await state.update_data(
            selected_service=service_key,
            consultation_mode=True,
            consultation_started=True
        )
        await callback.answer()
        return

    # Сохраняем выбранное направление в базе
    await UserMemory.update_user_data(
        session=session,
        user_id=user_id,
        selected_service=service_key
    )

    # Очищаем состояние и готовим данные анкеты
    await state.clear()
    await state.update_data(
        selected_service=service_key,
        questionnaire_index=0,
        questionnaire_answers=[],
        consultation_mode=False,
        consultation_started=False
    )

    # Добавляем системное сообщение в историю
    await UserMemory.add_message(
        session=session,
        user_id=user_id,
        role="system",
        content=f"Клиент выбрал направление: {flow.get('direction_label', service_name)}"
    )

    # Текст с описанием направления и первым вопросом
    description = flow.get("description", "")
    questions = flow.get("questions", [])
    first_question = questions[0] if questions else ""

    text = description
    if first_question:
        text = f"{description}\n\n{first_question}"

    await state.set_state(ServiceQuestionnaire.waiting_for_answer)

    # Отправляем новое сообщение без кнопок для естественного диалога
    await callback.message.answer(text=text)
    await callback.answer()


@router.callback_query(F.data == "partnership_agree")
async def handle_partnership_agreement(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession
):
    """Обработка согласия с партнёрским соглашением"""
    user_id = callback.from_user.id
    
    # Запрашиваем контактные данные
    await state.set_state(PartnershipFlow.waiting_contact_data)
    
    await callback.message.answer(
        "✅ Отлично! Вы согласились с условиями партнёрства.\n\n"
        "Пожалуйста, укажите ваши данные для связи:\n\n"
        "1. ФИО и компания\n"
        "2. Ваша роль / направление работы\n"
        "3. Telegram / e-mail для связи\n\n"
        "Напишите всю информацию одним сообщением:"
    )
    await callback.answer("Спасибо за согласие!")
    
    logger.info("partnership_agreement_accepted", user_id=user_id)


@router.message(PartnershipFlow.waiting_contact_data)
async def handle_partnership_contact_data(
    message: Message,
    state: FSMContext,
    session: AsyncSession
):
    """Обработка контактных данных партнёра"""
    user_id = message.from_user.id
    contact_info = message.text
    
    # Сохраняем в историю
    await UserMemory.add_message(
        session=session,
        user_id=user_id,
        role="user",
        content=f"Партнёрские контактные данные:\n{contact_info}"
    )
    
    # Создаём лид в Bitrix
    from src.bitrix import BitrixClient
    from src.models.bitrix_lead import BitrixLead
    from src.handlers.lead import notify_manager
    
    comment = f"ПАРТНЁРСКАЯ ЗАЯВКА\n\nКлиент согласился с условиями партнёрства.\n\nКонтактные данные:\n{contact_info}"
    
    bitrix_client = BitrixClient()
    result = await bitrix_client.create_lead(
        full_name=f"Партнёр {user_id}",
        phone="",
        selected_service="partnership",
        comment=comment,
        user_id=user_id
    )
    
    if result.get("success"):
        lead_id = result.get("lead_id")
        try:
            await BitrixLead.create(
                session=session,
                lead_id=lead_id,
                user_id=user_id,
                full_name=f"Партнёр {user_id}",
                phone="",
                service="partnership"
            )
        except Exception as e:
            logger.warning("partnership_lead_save_failed", error=str(e))
        
        # Уведомляем менеджеров
        try:
            await notify_manager(
                user_id=user_id,
                full_name=f"Партнёр {user_id}",
                phone="",
                service="partnership",
                comment=comment
            )
        except Exception as e:
            logger.warning("partnership_notify_failed", error=str(e))
    
    # Переводим в режим AI консультации
    await state.clear()
    await state.update_data(
        selected_service="partnership",
        consultation_mode=True,
        consultation_started=True
    )
    
    await message.answer(
        "🎉 Спасибо! Ваша заявка на партнёрство отправлена.\n\n"
        "Наша команда партнёрств свяжется с вами в ближайшее время.\n\n"
        "А пока вы можете задать мне любые вопросы о партнёрстве с MAXCAPITAL! 💬",
        reply_markup=_common_actions_keyboard()
    )
    
    logger.info("partnership_application_submitted", user_id=user_id)


@router.callback_query(F.data == "consultation")
async def handle_consultation_request(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession
):
    """Handle general consultation request"""
    user_id = callback.from_user.id
    
    # Clear state and enable consultation mode (используем продукт 'Индивидуальная консультация')
    await state.clear()
    await state.update_data(
        selected_service="individual_consultation",
        consultation_mode=True,
        consultation_started=True
    )
    # Добавляем системное сообщение для последующего резюме
    await UserMemory.add_message(
        session=session,
        user_id=user_id,
        role="system",
        content=f"Клиент выбрал услугу: {SERVICES.get('individual_consultation', 'Индивидуальная консультация')}"
    )
    
    # Отправляем новое сообщение вместо редактирования
    await callback.message.answer(
        text=MESSAGES["consultation"],
        reply_markup=_common_actions_keyboard()
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
            text="⬅️ В главное меню",
            callback_data="back_to_menu"
        )],
    ])
    # Отправляем новое сообщение вместо редактирования
    await callback.message.answer(
        text=contact_text,
        reply_markup=keyboard
    )
    await callback.answer()
    
    logger.info("contact_manager_requested", user_id=callback.from_user.id)




@router.callback_query(F.data == "back_to_menu")
async def handle_back_to_menu(
    callback: CallbackQuery,
    state: FSMContext
):
    """Вернуться в главное меню (эквивалент /start, но без команды)"""
    from src.handlers.start import get_welcome_keyboard
    
    await state.clear()
    
    # Короткое приветствие без перечисления услуг (они на кнопках)
    welcome_text = MESSAGES["welcome"]
    
    # Отправляем новое сообщение вместо редактирования
    await callback.message.answer(
        text=welcome_text,
        reply_markup=get_welcome_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "wait_manager")
async def handle_wait_manager(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession
):
    """
    ОЖИДАТЬ МЕНЕДЖЕРА — запускает существующий финальный флоу:
    завершаем консультацию и запрашиваем/подтверждаем контакты.
    """
    from src.handlers.lead import handle_finish_dialog
    
    # Проксируем в уже существующий обработчик, чтобы не дублировать логику
    await handle_finish_dialog(callback, state, session)


@router.message(ServiceQuestionnaire.waiting_for_answer)
async def handle_questionnaire_answer(
    message: Message,
    state: FSMContext,
    session: AsyncSession
):
    """Обработка ответов на вопросы анкеты по услуге (текстовые сообщения пользователя)"""
    user_id = message.from_user.id
    user_answer = message.text or ""

    state_data = await state.get_data()
    service_key = state_data.get("selected_service")
    index = state_data.get("questionnaire_index", 0)
    answers = state_data.get("questionnaire_answers", [])

    flow = SERVICE_FLOWS.get(service_key)
    if not flow:
        # Если конфиг потерян — просто выходим в главное меню
        from src.handlers.start import get_welcome_keyboard
        await state.clear()
        await message.answer(
            "Анкета по данному направлению временно недоступна.\n\n"
            "Пожалуйста, выберите другое направление.",
            reply_markup=get_welcome_keyboard()
        )
        return

    questions = flow.get("questions", [])

    # Сохраняем ответ в историю диалога как системное сообщение
    if 0 <= index < len(questions):
        question_text = questions[index]
        answers.append({"question": question_text, "answer": user_answer})
        await UserMemory.add_message(
            session=session,
            user_id=user_id,
            role="user",
            content=f"{question_text}\nОтвет: {user_answer}"
        )

    index += 1

    if index >= len(questions):
        # Анкета завершена — формируем лид в Bitrix и финальное сообщение
        await state.update_data(
            questionnaire_index=index,
            questionnaire_answers=answers,
        )

        # Собираем текст анкеты
        direction_label = flow.get('direction_label', SERVICES.get(service_key, ''))
        summary_lines = [f"Анкета по направлению: {direction_label}"]
        all_answer_texts = []
        for item in answers:
            q = item['question']
            a = item['answer']
            summary_lines.append(f"{q}\nОтвет: {a}")
            all_answer_texts.append(f"{q} Ответ: {a}")
        summary_text = "\n\n".join(summary_lines)

        # Пытаемся вытащить ФИО и телефон из ответов
        full_name = ""
        phone = ""
        if answers:
            # В большинстве анкет первый вопрос — ФИО / Как вас зовут
            full_name = answers[0]['answer'].strip()
        import re
        joined_answers = " ".join(a['answer'] for a in answers)
        phone_match = re.search(r'\+?\d[\d\s\-\(\)]{9,}', joined_answers)
        if phone_match:
            phone = re.sub(r'[\s\-\(\)]', '', phone_match.group(0))

        # Пишем системное сообщение с анкетой в историю
        await UserMemory.add_message(
            session=session,
            user_id=user_id,
            role="system",
            content=summary_text
        )

        # Создаём лид в Bitrix с полной анкетой
        from src.bitrix import BitrixClient
        from src.models.bitrix_lead import BitrixLead
        from src.handlers.lead import notify_manager

        comment_for_bitrix = summary_text
        bitrix_client = BitrixClient()
        result = await bitrix_client.create_lead(
            full_name=full_name or f"Telegram пользователь {user_id}",
            phone=phone or "",
            selected_service=service_key,
            comment=comment_for_bitrix,
            user_id=user_id
        )

        if result.get("success"):
            lead_id = result.get("lead_id")
            logger.info(
                "service_questionnaire_lead_created",
                user_id=user_id,
                service=service_key,
                lead_id=lead_id
            )
            # Сохраняем лид в БД (как и в общем флоу)
            try:
                await BitrixLead.create(
                    session=session,
                    lead_id=lead_id,
                    user_id=user_id,
                    full_name=full_name or "",
                    phone=phone or "",
                    service=service_key
                )
            except Exception as e:
                logger.warning("service_questionnaire_lead_save_failed", error=str(e))

            # Уведомляем менеджеров
            try:
                await notify_manager(
                    user_id=user_id,
                    full_name=full_name or f"Telegram пользователь {user_id}",
                    phone=phone or "",
                    service=service_key,
                    comment=comment_for_bitrix
                )
            except Exception as e:
                logger.warning("service_questionnaire_notify_failed", error=str(e))
        else:
            logger.error(
                "service_questionnaire_lead_failed",
                user_id=user_id,
                service=service_key,
                error=result.get("error")
            )

        # Финальный текст для пользователя (как в ТЗ)
        final_text = flow.get("final_text", "")
        combined_final = f"{final_text}\n\n{GLOBAL_FINAL_MESSAGE}" if final_text else GLOBAL_FINAL_MESSAGE
        
        # Добавляем приглашение к AI консультации
        combined_final += "\n\n💬 А пока вы можете задать мне любые вопросы по выбранной услуге!"

        await message.answer(
            combined_final,
            reply_markup=_common_actions_keyboard()
        )

        logger.info(
            "service_questionnaire_completed",
            user_id=user_id,
            service=service_key
        )
        
        # После анкеты - включаем режим AI консультации
        await state.clear()
        await state.update_data(
            selected_service=service_key,
            consultation_mode=True,
            consultation_started=True,
            questionnaire_completed=True
        )
        return

    # Есть ещё вопросы — задаём следующий
    await state.update_data(
        questionnaire_index=index,
        questionnaire_answers=answers
    )

    next_question = questions[index]
    # Следующие вопросы анкеты отправляем без кнопок, чтобы диалог выглядел естественно
    await message.answer(
        text=next_question
    )

