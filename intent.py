"""
Rule-based intent detection module.

This module provides functionality to detect user intents based on keyword matching.
Supports the following intents: invest, documents, consult, support.
"""

from typing import Optional


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

