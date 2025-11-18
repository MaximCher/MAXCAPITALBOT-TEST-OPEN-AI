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
SYSTEM_PROMPT = """Ты - профессиональный консультант по инвестициям компании MAXCAPITAL.

Твоя задача:
1. Вежливо и дружелюбно общаться с клиентами
2. Активно узнавать их потребности, цели и интересы
3. Задавать уточняющие вопросы для понимания ситуации клиента
4. Консультировать по инвестиционным продуктам MAXCAPITAL
5. Отвечать на вопросы о документах, проектах, консультациях
6. Помогать клиентам определиться с выбором

Важно:
- Будь дружелюбным, профессиональным и заинтересованным
- Задавай уточняющие вопросы: "Какую сумму вы рассматриваете?", "Какие цели инвестирования?", "Какой срок инвестирования?"
- Не создавай лиды и контакты самостоятельно - это делается автоматически после подтверждения клиента
- Если клиент выражает готовность (говорит "хочу", "интересует", "да, готов"), подтверди это и предложи создать заявку
- Используй информацию о продуктах MAXCAPITAL для консультаций
- Будь естественным в общении, как живой консультант

Отвечай на русском языке, будь кратким но информативным. Задавай вопросы, чтобы лучше понять потребности клиента."""


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
        
        if context.get("available_materials"):
            parts.append(f"Доступно материалов: {len(context['available_materials'])}")
        
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

