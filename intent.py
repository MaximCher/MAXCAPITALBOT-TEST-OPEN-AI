"""
Rule-based intent detection module.

This module provides functionality to detect user intents based on keyword matching.
Supports the following intents: invest, documents, consult, support.
Also detects specific services offered by MAXCAPITAL.
"""

from typing import Optional, List, Dict


# Services offered by MAXCAPITAL
SERVICES = {
    "venture_capital": {
        "code": "venture_capital",
        "name": "VENTURE CAPITAL (Венчурный капитал)",
        "keywords": [
            "venture capital", "венчурный капитал", "венчур", "стартап", "стартапы",
            "seed round", "раунд а", "раунд seed", "инвестиции в стартапы",
            "фонд развития", "цифровая экономика", "gr-поддержка", "gr поддержка",
            "инвестирование в стартапы", "seed", "раунд seed", "раунд a"
        ]
    },
    "hnwi": {
        "code": "hnwi",
        "name": "HNWI Consultations (Консультации для частных лиц с крупным капиталом)",
        "keywords": [
            "hnwi", "high net worth", "крупный капитал", "частные лица",
            "консультации для частных лиц", "миллион", "1 млн", "миллион долларов",
            "крупный инвестор", "частный капитал", "личные инвестиции",
            "конфиденциальные услуги", "персональные услуги"
        ]
    },
    "real_estate": {
        "code": "real_estate",
        "name": "REAL ESTATE (Недвижимость)",
        "keywords": [
            "real estate", "недвижимость", "недвижимое имущество", "недвижимое",
            "недооцененная недвижимость", "покупка недвижимости", "аукцион",
            "аукционный дом", "объект недвижимости", "коммерческая недвижимость",
            "жилая недвижимость", "инвестиции в недвижимость"
        ]
    },
    "crypto": {
        "code": "crypto",
        "name": "CRYPTO (Криптовалюта)",
        "keywords": [
            "crypto", "криптовалюта", "крипта", "биткоин", "bitcoin", "ethereum",
            "otc", "внебиржевые сделки", "криптовалютный портфель", "майнинг",
            "инвестиции в криптовалюту", "криптоинвестиции", "криптопортфель",
            "криптовалютные сделки", "внебиржевой", "крипто"
        ]
    },
    "m_and_a": {
        "code": "m_and_a",
        "name": "M&A (Mergers & Acquisitions / Слияния и поглощения)",
        "keywords": [
            "m&a", "m and a", "слияния и поглощения", "слияние", "поглощение",
            "mergers", "acquisitions", "buy-side", "sell-side", "buy side", "sell side",
            "горизонтальная интеграция", "вертикальная интеграция", "интеграция бизнеса",
            "сделки m&a", "сопровождение сделок", "консультирование сделок"
        ]
    },
    "private_equity": {
        "code": "private_equity",
        "name": "PRIVATE EQUITY (Частный акционерный капитал)",
        "keywords": [
            "private equity", "частный акционерный капитал", "частный капитал",
            "выкуп бизнеса", "выкуп бизнес-единиц", "экспорт", "экспортная выручка",
            "экспортные рынки", "1 млрд", "миллиард", "оборот от миллиарда",
            "частные инвестиции", "акционерный капитал"
        ]
    },
    "relocation": {
        "code": "relocation",
        "name": "Relocation Support (Поддержка при релокации)",
        "keywords": [
            "relocation", "релокация", "переезд", "переезд за границу",
            "внж", "пмж", "гражданство", "вид на жительство", "постоянное место жительства",
            "международные транзакции", "получение статуса", "статус за рубежом",
            "иммиграция", "эмиграция", "переезд в другую страну"
        ]
    },
    "banking_cards": {
        "code": "banking_cards",
        "name": "ЗАРУБЕЖНЫЕ БАНКОВСКИЕ КАРТЫ",
        "keywords": [
            "банковская карта", "банковские карты", "зарубежная карта", "зарубежные карты",
            "mastercard gold", "visa platinum", "visa infinite", "карта mastercard",
            "карта visa", "оформление карты", "банковская карта за рубежом",
            "киргизия", "таджикистан", "карта в киргизии", "карта в таджикистане"
        ]
    }
}


# Mapping of keywords to intents (English and Russian)
INTENT_KEYWORDS = {
    "invest": [
        "invest", "investment", "investing", "investor", "capital", "portfolio",
        "assets", "fund", "funds", "financial", "finance",
        "инвестировать", "инвестиция", "инвестиции", "инвестор", "капитал",
        "портфель", "активы", "фонд", "фонды", "финансовый", "финансы",
        "вложить", "вложение", "вложения", "хочу инвестировать", "инвестирую",
        "инвестиционный", "инвестиционные", "инвестиционное",
    ],
    "documents": [
        "documents", "document", "doc", "paperwork", "papers", "file", "files",
        "certificate", "certificates", "contract", "contracts", "agreement", "agreements",
        "презентация", "презентации", "документ", "документы", "документация",
        "файл", "файлы", "справка", "справки", "сертификат", "сертификаты",
        "договор", "договоры", "соглашение", "соглашения", "проект", "проекты",
        "нужна презентация", "нужны документы", "нужен файл", "хочу посмотреть",
        "покажите", "покажи", "отправьте", "отправь", "пришлите", "пришли",
    ],
    "consult": [
        "consult", "consultation", "consulting", "advice", "advisor", "adviser",
        "guidance", "help", "recommendation", "recommendations", "expert", "expertise",
        "консультация", "консультации", "консультирование", "совет", "советы",
        "советник", "рекомендация", "рекомендации", "эксперт", "экспертиза",
        "помощь", "помочь",
    ],
    "support": [
        "support", "assistance", "help", "issue", "issues", "problem", "problems",
        "trouble", "error", "errors", "bug", "bugs", "technical", "service",
        "поддержка", "помощь", "помочь", "проблема", "проблемы", "ошибка",
        "ошибки", "неполадка", "неполадки", "технический", "техническая",
        "сервис", "служба поддержки",
    ],
}


def detect_intent(text: str) -> Optional[str]:
    """
    Detect user intent from text using rule-based keyword matching.

    Args:
        text: Input text to analyze for intent detection.

    Returns:
        Detected intent as a string ('invest', 'documents', 'consult', 'support')
        or None if no intent is detected.

    Examples:
        >>> detect_intent("I want to invest in stocks")
        'invest'
        >>> detect_intent("Need help with documents")
        'documents'
        >>> detect_intent("Can I get a consultation?")
        'consult'
        >>> detect_intent("I need technical support")
        'support'
        >>> detect_intent("Hello, how are you?")
        None
    """
    if not text or not isinstance(text, str):
        return None

    # Normalize text to lowercase for case-insensitive matching
    text_lower = text.lower()

    # Count matches for each intent
    intent_scores = {}
    for intent, keywords in INTENT_KEYWORDS.items():
        score = sum(1 for keyword in keywords if keyword in text_lower)
        if score > 0:
            intent_scores[intent] = score

    # Return the intent with the highest score, or None if no matches
    if intent_scores:
        return max(intent_scores, key=intent_scores.get)

    return None


def detect_services(text: str) -> List[Dict[str, str]]:
    """
    Detect services mentioned in text.

    Args:
        text: Input text to analyze for service detection.

    Returns:
        List of detected services with code and name.

    Examples:
        >>> detect_services("Интересует венчурный капитал и криптовалюта")
        [{'code': 'venture_capital', 'name': 'VENTURE CAPITAL (Венчурный капитал)'}, 
         {'code': 'crypto', 'name': 'CRYPTO (Криптовалюта)'}]
    """
    if not text or not isinstance(text, str):
        return []

    text_lower = text.lower()
    detected_services = []

    for service_code, service_data in SERVICES.items():
        keywords = service_data["keywords"]
        # Check if any keyword matches
        if any(keyword in text_lower for keyword in keywords):
            detected_services.append({
                "code": service_data["code"],
                "name": service_data["name"]
            })

    return detected_services


def get_service_info(service_code: str) -> Optional[Dict[str, str]]:
    """
    Get service information by code.

    Args:
        service_code: Service code.

    Returns:
        Service information dict or None if not found.
    """
    return SERVICES.get(service_code)


def get_all_services() -> Dict[str, Dict[str, str]]:
    """
    Get all available services.

    Returns:
        Dictionary of all services.
    """
    return SERVICES

