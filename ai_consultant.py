"""
AI Consultant module for MAXCAPITAL Bot.

Uses OpenAI API to provide intelligent consultation and conversation with clients.
"""

import os
import json
from typing import List, Dict, Optional, Any

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False


# System prompt for the AI consultant
SYSTEM_PROMPT = """Ты - профессиональный консультант компании MAXCAPITAL.

Твоя задача:
1. Вежливо и дружелюбно общаться с клиентами
2. Активно узнавать, какие услуги их интересуют из списка услуг MAXCAPITAL
3. Консультировать клиентов по интересующим их услугам
4. Задавать уточняющие вопросы для понимания потребностей клиента
5. Помогать клиентам определиться с выбором

Услуги MAXCAPITAL:
1. VENTURE CAPITAL (Венчурный капитал) - Инвестирование в стартапы (seed round и A round). Совместная работа с Фондом развития цифровой экономики, включая GR-поддержку проектам.

2. HNWI Consultations (Консультации для частных лиц с крупным капиталом) - Предоставление персональных и конфиденциальных услуг клиентам с инвестиционным капиталом от $1 млн.

3. REAL ESTATE (Недвижимость) - Поиск и приобретение недооцененных объектов недвижимости через партнеров, площадки и аукционные дома.

4. CRYPTO (Криптовалюта) - Услуги внебиржевых (OTC) сделок с криптовалютой. Консультирование по вопросам составления криптовалютных портфелей и инвестиций в майнинг.

5. M&A (Mergers & Acquisitions / Слияния и поглощения) - Консультирование и сопровождение сделок слияний и поглощений как на стороне покупателя (Buy-side), так и на стороне продавца (Sell-side). Помощь в осуществлении горизонтальной или вертикальной интеграции бизнеса.

6. PRIVATE EQUITY (Частный акционерный капитал) - Фокус на выкупе бизнес-единиц, производящих продукцию для экспортных рынков и имеющих потенциал роста экспортной выручки (начальный оборот от 1 млрд в год).

7. Relocation Support (Поддержка при релокации) - Поддержка и сопровождение в вопросах международных транзакций. Помощь в получении статуса (ВНЖ, ПМЖ, Гражданства) за рубежом на законных основаниях.

8. ЗАРУБЕЖНЫЕ БАНКОВСКИЕ КАРТЫ - Предоставление возможности оформления зарубежных банковских карт (MASTERCARD GOLD, VISA PLATINUM и VISA INFINITE) через банки-партнеры в Киргизии и Таджикистане.

Важно:
- Будь дружелюбным, профессиональным и заинтересованным
- АКТИВНО задавай вопросы! Не жди, пока клиент сам все расскажет - проявляй инициативу
- Если клиент упоминает услугу или интересуется ею, предоставь подробную консультацию по этой услуге
- ОБЯЗАТЕЛЬНО задавай уточняющие вопросы в зависимости от услуги:
  * Для венчурного капитала: "На каком этапе находится ваш стартап?", "Какую сумму вы планируете привлечь?", "В какой сфере работает ваш проект?"
  * Для HNWI: "Какой размер капитала вы рассматриваете?", "Какие цели инвестирования?", "Какой срок инвестирования?"
  * Для недвижимости: "Какой тип недвижимости интересует?", "В каком регионе?", "Какой бюджет?"
  * Для криптовалюты: "Какие криптовалюты вас интересуют?", "Какой объем сделок?", "Интересует ли майнинг?"
  * Для M&A: "Вы покупаете или продаете бизнес?", "В какой сфере?", "Какой размер сделки?"
  * Для Private Equity: "Какой оборот у вашего бизнеса?", "Работаете ли на экспорт?", "Какой потенциал роста?"
  * Для релокации: "В какую страну планируете переезд?", "Нужен ли ВНЖ, ПМЖ или гражданство?", "Какой срок?"
  * Для банковских карт: "Какая карта вас интересует?", "Для каких целей нужна карта?"
- Задавай минимум 2-3 вопроса в каждом ответе, чтобы лучше понять потребности клиента
- Не создавай лиды и контакты самостоятельно - это делается автоматически после сбора данных клиента
- Если клиент выражает готовность (говорит "хочу", "интересует", "да, готов", "хочу оформить"), попроси его предоставить ФИО и номер телефона для создания заявки
- Используй информацию об услугах MAXCAPITAL для консультаций
- Будь естественным в общении, как живой консультант, который хочет помочь
- Если клиент интересуется несколькими услугами, консультируй по каждой из них и задавай вопросы по каждой
- Не ограничивайся одним вопросом - задавай несколько вопросов подряд для глубокого понимания потребностей

Отвечай на русском языке. Будь информативным и активным в консультировании. ВАЖНО: В каждом ответе задавай минимум 2-3 уточняющих вопроса, чтобы лучше понять потребности клиента и предоставить максимально полезную консультацию."""


class AIConsultant:
    """AI Consultant using OpenAI API."""
    
    def __init__(self):
        self.api_key = os.environ.get("OPENAI_API_KEY")
        self.model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
        self.client = None
        
        if OPENAI_AVAILABLE and self.api_key:
            try:
                self.client = OpenAI(api_key=self.api_key)
            except Exception as e:
                print(f"Warning: Failed to initialize OpenAI client: {e}")
                self.client = None
        else:
            if not OPENAI_AVAILABLE:
                print("Warning: openai package not installed. Install with: pip install openai")
            if not self.api_key:
                print("Warning: OPENAI_API_KEY not set. AI consultation will be disabled.")
    
    def is_available(self) -> bool:
        """Check if AI consultant is available."""
        return self.client is not None
    
    def get_response(
        self,
        user_message: str,
        conversation_history: List[Dict[str, str]],
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Get AI response to user message.
        
        Args:
            user_message: User's message
            conversation_history: List of previous messages [{"role": "user/assistant", "content": "..."}]
            context: Optional context (detected intent, available materials, etc.)
        
        Returns:
            AI response text
        """
        if not self.is_available():
            return self._fallback_response(user_message, context)
        
        try:
            # Build messages for API
            messages = [{"role": "system", "content": SYSTEM_PROMPT}]
            
            # Add context if available
            if context:
                context_text = self._format_context(context)
                if context_text:
                    messages.append({
                        "role": "system",
                        "content": f"Контекст: {context_text}"
                    })
            
            # Add conversation history
            messages.extend(conversation_history[-10:])  # Last 10 messages for context
            
            # Add current user message
            messages.append({"role": "user", "content": user_message})
            
            # Call OpenAI API
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,
                max_tokens=500
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            print(f"Error calling OpenAI API: {e}")
            return self._fallback_response(user_message, context)
    
    def _format_context(self, context: Dict[str, Any]) -> str:
        """Format context for AI prompt."""
        parts = []
        
        if context.get("detected_intent"):
            intent_names = {
                "invest": "инвестиции",
                "documents": "документы",
                "consult": "консультация",
                "support": "поддержка"
            }
            intent = intent_names.get(context["detected_intent"], context["detected_intent"])
            parts.append(f"Определено намерение клиента: {intent}")
        
        if context.get("detected_services"):
            services = [s.get("name", s.get("code", "")) for s in context["detected_services"]]
            if services:
                parts.append(f"Обнаруженные услуги, которые интересуют клиента: {', '.join(services)}")
        
        if context.get("selected_services"):
            services = [s.get("name", s.get("code", "")) for s in context["selected_services"]]
            if services:
                parts.append(f"Услуги, по которым клиент уже консультируется: {', '.join(services)}")
        
        if context.get("available_materials"):
            parts.append(f"Доступно материалов: {len(context['available_materials'])}")
        
        if context.get("collecting_data"):
            parts.append("ВАЖНО: Клиент готов к оформлению заявки. Необходимо собрать ФИО и номер телефона.")
        
        return ". ".join(parts) if parts else ""
    
    def _fallback_response(self, user_message: str, context: Optional[Dict[str, Any]] = None) -> str:
        """Fallback response when AI is not available."""
        detected_intent = context.get("detected_intent") if context else None
        
        if detected_intent == "invest":
            return "Спасибо за интерес к нашим инвестиционным продуктам! Расскажите, пожалуйста, какую сумму вы хотели бы инвестировать и какие цели преследуете?"
        elif detected_intent == "documents":
            return "Конечно! Какие именно документы вас интересуют? Презентации проектов, договоры или другая информация?"
        elif detected_intent == "consult":
            return "Буду рад помочь вам с консультацией! По какому вопросу вы хотели бы получить консультацию?"
        elif detected_intent == "support":
            return "Конечно, помогу решить вашу проблему! Расскажите, пожалуйста, с чем именно возникли трудности?"
        else:
            return "Здравствуйте! Я консультант MAXCAPITAL. Чем могу помочь? Расскажите о ваших инвестиционных целях или задайте вопрос."
    
    def check_confirmation(self, user_message: str, conversation_history: List[Dict[str, str]]) -> bool:
        """
        Check if user confirmed their intention to proceed.
        
        Returns:
            True if user confirmed, False otherwise
        """
        # Simple keyword-based confirmation (works without AI)
        confirmation_keywords = [
            "да", "да, хочу", "согласен", "подтверждаю", "готов", "хочу",
            "давайте", "начнем", "продолжить", "да, готов", "подтверждаю",
            "интересует", "интересно", "хочу инвестировать", "хочу получить",
            "нужна консультация", "нужны документы", "хочу посмотреть"
        ]
        message_lower = user_message.lower()
        
        # Check for explicit confirmation
        if any(keyword in message_lower for keyword in confirmation_keywords):
            return True
        
        # Use AI for more nuanced confirmation if available
        if self.is_available():
            try:
                confirmation_prompt = """Проанализируй сообщение пользователя и определи, подтверждает ли он свое намерение продолжить работу с компанией (инвестировать, получить документы, консультацию и т.д.).

Ответь только "ДА" если пользователь явно подтверждает намерение или выражает готовность, или "НЕТ" если это просто вопрос без подтверждения.

Сообщение: {user_message}"""
                
                messages = [
                    {"role": "system", "content": confirmation_prompt.format(user_message=user_message)},
                    {"role": "user", "content": user_message}
                ]
                
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=0.3,
                    max_tokens=10
                )
                
                answer = response.choices[0].message.content.strip().upper()
                return "ДА" in answer or "YES" in answer
                
            except Exception:
                pass
        
        return False


# Global AI consultant instance
ai_consultant = AIConsultant()

