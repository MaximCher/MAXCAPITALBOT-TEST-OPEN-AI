"""
MAXCAPITAL Bot - Document Sender Module
Handles sending PDF documents to users on request
"""

import os
import re
from typing import Optional, List, Dict
from aiogram.types import FSInputFile, Message
import structlog

logger = structlog.get_logger()

# Папка с документами
DOCUMENTS_DIR = "/app/documents"

# Маппинг ключевых слов к документам (реальные файлы из Google Drive)
DOCUMENT_KEYWORDS: Dict[str, List[str]] = {
    # Зарубежные карты
    "MAXCAPITAL_ZARUBEZHNYE_KARTY.pdf": [
        "зарубежн", "банковск", "международн", "иностранн",
        "таджик", "карт", "visa", "mastercard", "эмитент"
    ],
    # Резиденции и миграция
    "MAXCAPITAL_Rezidencii_migracionnye_resheniya.pdf": [
        "резиденц", "миграц", "внж", "пмж", "гражданств",
        "релокац", "переезд", "паспорт"
    ],
    # Международная недвижимость
    "MAXCAPITAL_Mezhdunarodnaya_nedvizhimost.pdf": [
        "международн", "зарубежн", "дубай", "бали", "майами", 
        "таиланд", "маврикий", "за рубеж"
    ],
    # Недвижимость Москвы
    "MAXCAPITAL_Vysokodohodnaya_nedvizhimost_Moskvy.pdf": [
        "москв", "высокодоход", "коммерческ"
    ],
    # NDA
    "nda.pdf": ["nda", "неразглашен", "конфиденциальн"],
    # КП (коммерческое предложение)
    "kp.pdf": ["презентац", " кп ", "о компании", "maxcapital"],
}


def get_available_documents() -> List[str]:
    """Получить список доступных документов"""
    if not os.path.exists(DOCUMENTS_DIR):
        return []
    
    return [f for f in os.listdir(DOCUMENTS_DIR) if f.endswith('.pdf')]


def find_document_by_request(user_message: str) -> Optional[str]:
    """
    Найти документ по запросу пользователя
    Returns filename or None
    """
    message_lower = user_message.lower()
    
    # Проверяем наличие запроса на документ
    doc_request_patterns = [
        r'(пришли|отправь|скинь|дай|можно|хочу|нужен|нужна|пришлите|отправьте|получить|скачать)',
        r'(pdf|документ|файл|презентаци|брошюр)',
    ]
    
    # Должен быть хотя бы один глагол запроса ИЛИ слово про документ
    has_request_verb = bool(re.search(doc_request_patterns[0], message_lower))
    has_doc_word = bool(re.search(doc_request_patterns[1], message_lower))
    
    if not (has_request_verb or has_doc_word):
        return None
    
    # Ищем подходящий документ по ключевым словам с подсчетом совпадений
    available_docs = get_available_documents()
    matches: Dict[str, int] = {}
    
    for filename, keywords in DOCUMENT_KEYWORDS.items():
        if filename not in available_docs:
            continue
        
        match_count = 0
        for keyword in keywords:
            if keyword in message_lower:
                match_count += 1
        
        if match_count > 0:
            matches[filename] = match_count
    
    # Возвращаем документ с наибольшим количеством совпадений
    if matches:
        best_match = max(matches.items(), key=lambda x: x[1])
        return best_match[0]
    
    # Если запрос общий на презентацию - возвращаем kp.pdf
    if has_request_verb and any(word in message_lower for word in ['презентаци', 'о компании', 'maxcapital']):
        if "kp.pdf" in available_docs:
            return "kp.pdf"
    
    return None


async def send_document(message: Message, filename: str) -> bool:
    """
    Отправить документ пользователю
    Returns True if successful
    """
    filepath = os.path.join(DOCUMENTS_DIR, filename)
    
    if not os.path.exists(filepath):
        logger.warning("document_not_found", filename=filename, filepath=filepath)
        return False
    
    try:
        document = FSInputFile(filepath, filename=filename)
        await message.answer_document(
            document=document,
            caption=f"📄 Документ: {filename}\n\nЕсли у вас есть вопросы по содержанию — задавайте!"
        )
        
        logger.info("document_sent", 
                   user_id=message.from_user.id, 
                   filename=filename)
        return True
        
    except Exception as e:
        logger.error("document_send_failed", 
                    filename=filename, 
                    error=str(e))
        return False


def get_documents_list_text() -> str:
    """Получить текст со списком доступных документов"""
    docs = get_available_documents()
    
    if not docs:
        return "К сожалению, документы пока недоступны."
    
    text = "📚 Доступные документы:\n\n"
    
    doc_names = {
        "MAXCAPITAL_ZARUBEZHNYE_KARTY.pdf": "💳 Зарубежные банковские карты",
        "MAXCAPITAL_Rezidencii_migracionnye_resheniya.pdf": "🏠 Резиденции и миграционные решения",
        "MAXCAPITAL_Mezhdunarodnaya_nedvizhimost.pdf": "🌏 Международная недвижимость",
        "MAXCAPITAL_Vysokodohodnaya_nedvizhimost_Moskvy.pdf": "🏙 Высокодоходная недвижимость Москвы",
        "kp.pdf": "📊 Презентация MAXCAPITAL",
        "nda.pdf": "📋 NDA (соглашение о неразглашении)",
    }
    
    for doc in docs:
        name = doc_names.get(doc, f"📄 {doc}")
        text += f"• {name}\n"
    
    text += "\nЧтобы получить документ, напишите, например:\n"
    text += "«Пришли PDF про зарубежные карты» или «Отправь презентацию компании»"
    
    return text



