"""
MAXCAPITAL Bot - AI Agent Module
OpenAI-powered conversational agent with RAG support
"""

from typing import List, Dict, Any, Optional
from openai import AsyncOpenAI
import structlog

from src.config import settings, SERVICES

logger = structlog.get_logger()

# Initialize OpenAI async client
client = AsyncOpenAI(api_key=settings.openai_api_key)


class AIAgent:
    """AI Agent for premium consulting conversations"""
    
    SYSTEM_PROMPT = """Вы — премиальный AI-консультант компании MAXCAPITAL (https://maxcapital.ch/).

MAXCAPITAL — международная консалтинговая и инвестиционная компания, специализирующаяся на высококлассных финансовых решениях для HNWI-клиентов и корпоративных структур.

Наши услуги:
• Venture Capital — инвестиции в стартапы и венчурные проекты
• HNWI Consultations — индивидуальные консультации для состоятельных клиентов
• Real Estate — премиальная недвижимость и инвестиции
• Crypto — криптовалютные стратегии и консалтинг
• M&A — сопровождение сделок слияний и поглощений
• Private Equity — частные инвестиции и управление капиталом
• Relocation Support — поддержка релокации и международные решения
• Зарубежные банковские карты — открытие счетов и карт в международных банках

СТИЛЬ ОБЩЕНИЯ:
• Профессиональный, уверенный, экспертный
• Структурированные ответы с конкретными деталями
• Премиальный тон без излишней фамильярности
• Краткость и информативность
• Используйте эмодзи умеренно и уместно

ЗАДАЧИ:
• Консультируйте клиентов по нашим услугам
• Используйте предоставленный контекст из документов
• Помните историю диалога
• Предлагайте конкретные решения
• При необходимости предлагайте связаться с менеджером

Отвечайте всегда на русском языке, структурировано и экспертно."""
    
    def __init__(self):
        self.model = settings.openai_model
    
    async def generate_answer(
        self,
        user_message: str,
        conversation_history: List[Dict[str, Any]],
        vector_context: Optional[str] = None,
        user_name: Optional[str] = None,
        selected_service: Optional[str] = None
    ) -> str:
        """
        Generate AI response based on user message, history, and RAG context
        """
        try:
            # Build messages for OpenAI
            messages = [{"role": "system", "content": self.SYSTEM_PROMPT}]
            
            # Add user context if available
            context_parts = []
            
            if user_name:
                context_parts.append(f"Клиент: {user_name}")
            
            if selected_service:
                service_name = SERVICES.get(selected_service, selected_service)
                context_parts.append(f"Интересующая услуга: {service_name}")
            
            if vector_context:
                context_parts.append(f"\n📚 ВАЖНО! ИСПОЛЬЗУЙТЕ ЭТУ ИНФОРМАЦИЮ ИЗ НАШИХ ДОКУМЕНТОВ:\n{vector_context}\n\n⚠️ ОБЯЗАТЕЛЬНО базируйте ответ на этой информации!")
            
            if context_parts:
                context_message = "\n".join(context_parts)
                messages.append({
                    "role": "system",
                    "content": f"КОНТЕКСТ ТЕКУЩЕГО ДИАЛОГА:\n{context_message}"
                })
            
            # Add conversation history (last 10 messages)
            for msg in conversation_history[-10:]:
                if msg.get('role') in ['user', 'assistant']:
                    messages.append({
                        "role": msg['role'],
                        "content": msg['content']
                    })
            
            # Add current user message
            messages.append({
                "role": "user",
                "content": user_message
            })
            
            logger.debug(
                "generating_ai_response",
                message_count=len(messages),
                has_context=bool(vector_context)
            )
            
            # Call OpenAI API
            response = await client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,
                max_tokens=1000,
                top_p=0.9,
                frequency_penalty=0.3,
                presence_penalty=0.3
            )
            
            answer = response.choices[0].message.content
            
            logger.info(
                "ai_response_generated",
                tokens_used=response.usage.total_tokens,
                response_length=len(answer)
            )
            
            return answer
            
        except Exception as e:
            logger.error("ai_generation_failed", error=str(e))
            return self._get_fallback_response()
    
    async def summarize_lead(
        self,
        user_name: str,
        phone: str,
        selected_service: str,
        conversation_history: List[Dict[str, Any]]
    ) -> str:
        """
        Generate a concise summary of client's request for Bitrix24 lead
        """
        try:
            service_name = SERVICES.get(selected_service, selected_service)
            
            # Get ALL messages from consultation (after service selection)
            # Filter out system messages about service selection, keep user messages
            consultation_messages = []
            service_selected = False
            
            for msg in conversation_history:
                if msg.get('role') == 'system' and 'выбрал услугу' in msg.get('content', ''):
                    service_selected = True
                    continue
                
                if service_selected and msg.get('role') == 'user':
                    # Skip contact data messages
                    if 'Контактные данные' not in msg.get('content', ''):
                        consultation_messages.append(msg['content'])
            
            # If no messages, use all recent user messages
            if not consultation_messages:
                consultation_messages = [
                    msg['content'] for msg in conversation_history[-10:]
                    if msg.get('role') == 'user' and 'Контактные данные' not in msg.get('content', '')
                ]
            
            messages = [
                {
                    "role": "system",
                    "content": """Вы — AI-помощник MAXCAPITAL. Создайте информативное резюме запроса клиента для менеджера.

ОБЯЗАТЕЛЬНО укажите:
• Выбранная услуга и её категория
• Что именно интересует клиента (инвестиции, консультация, покупка и т.д.)
• Предполагаемая сумма или масштаб (если упоминалось)
• Срочность и приоритет
• Дополнительные пожелания или вопросы клиента

ФОРМАТ:
2-3 абзаца, 200-400 символов
Конкретно и по делу

Стиль: деловой, структурированный, информативный."""
                },
                {
                    "role": "user",
                    "content": f"""НОВЫЙ ЛИД из Telegram бота:

👤 Клиент: {user_name}
📱 Телефон: {phone}
🎯 Выбранная услуга: {service_name}

💬 ПОЛНАЯ ИСТОРИЯ КОНСУЛЬТАЦИИ:
{chr(10).join(consultation_messages) if consultation_messages else 'Клиент выбрал услугу через кнопку в боте и сразу запросил звонок менеджера без дополнительных вопросов.'}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Создайте детальное резюме для менеджера (200-400 символов):

✓ Что конкретно хочет клиент
✓ Какие суммы/сроки/требования обсуждались
✓ Основные вопросы и интересы
✓ На что обратить внимание при звонке
✓ Срочность и приоритет

Будьте конкретны и информативны."""
                }
            ]
            
            response = await client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,
                max_tokens=400
            )
            
            summary = response.choices[0].message.content.strip()
            
            logger.info(
                "lead_summary_created",
                length=len(summary),
                summary=summary[:200]  # Log first 200 chars
            )
            
            return summary
            
        except Exception as e:
            logger.error("lead_summary_failed", error=str(e))
            return f"Клиент заинтересован в услуге: {SERVICES.get(selected_service, selected_service)}. Требуется консультация менеджера."
    
    def _get_fallback_response(self) -> str:
        """Fallback response if AI fails"""
        return """Благодарю за ваш вопрос! 

К сожалению, в данный момент я испытываю технические сложности с формированием ответа.

🤝 Рекомендую связаться с нашим менеджером напрямую для получения детальной консультации:
📧 https://maxcapital.ch/contacts

Приношу извинения за неудобства."""

