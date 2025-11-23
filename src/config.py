"""
MAXCAPITAL Bot - Configuration Module
Handles all environment variables and app settings
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional


class Settings(BaseSettings):
    """Application configuration from environment variables"""
    
    # Telegram Bot
    telegram_bot_token: str = Field(..., alias="TELEGRAM_BOT_TOKEN")
    manager_chat_id: str = Field(..., alias="MANAGER_CHAT_ID")
    
    # PostgreSQL Database
    postgres_host: str = Field(default="db", alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, alias="POSTGRES_PORT")
    postgres_db: str = Field(..., alias="POSTGRES_DB")
    postgres_user: str = Field(..., alias="POSTGRES_USER")
    postgres_password: str = Field(..., alias="POSTGRES_PASSWORD")
    
    # OpenAI API
    openai_api_key: str = Field(..., alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4-turbo-preview", alias="OPENAI_MODEL")
    embedding_model: str = Field(default="text-embedding-3-small", alias="EMBEDDING_MODEL")
    
    # Bitrix24 Webhook
    bitrix24_webhook_url: str = Field(..., alias="BITRIX24_WEBHOOK_URL")
    
    # Google Drive API
    google_drive_folder_id: Optional[str] = Field(default=None, alias="GOOGLE_DRIVE_FOLDER_ID")
    google_credentials_file: str = Field(default="credentials.json", alias="GOOGLE_CREDENTIALS_FILE")
    
    # App Settings
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    debug_mode: bool = Field(default=False, alias="DEBUG_MODE")
    
    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"  # Ignore extra fields (BOM issues)
    
    @property
    def database_url(self) -> str:
        """Construct PostgreSQL connection URL"""
        return f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
    
    @property
    def database_url_sync(self) -> str:
        """Construct synchronous PostgreSQL connection URL"""
        return f"postgresql://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"


# Global settings instance
settings = Settings()


# MAXCAPITAL Services List
SERVICES = {
    "venture_capital": "🚀 Venture Capital",
    "hnwi": "💎 HNWI Consultations",
    "real_estate": "🏛 Real Estate",
    "crypto": "₿ Crypto",
    "ma": "🤝 M&A",
    "private_equity": "📊 Private Equity",
    "relocation": "🌍 Relocation Support",
    "bank_cards": "💳 Зарубежные банковские карты"
}

# Bot messages
MESSAGES = {
    "welcome": """👋 Добро пожаловать в MAXCAPITAL!

Мы — международная консалтинговая и инвестиционная компания, специализирующаяся на премиальных финансовых решениях для наших клиентов.

🌐 Наш сайт: https://maxcapital.ch/

Выберите интересующую вас услугу или получите персональную консультацию от нашего AI-ассистента.""",
    
    "select_service": "Пожалуйста, выберите интересующую вас услугу:",
    
    "service_selected": """✅ Отлично! Вы выбрали: {service}

Для предоставления качественной консультации, пожалуйста, укажите ваши контактные данные.

Формат: Фамилия Имя Телефон
Например: Иванов Иван +41791234567""",
    
    "data_received": """✅ Спасибо, {name}!

Ваши данные получены:
📱 Телефон: {phone}
🎯 Услуга: {service}

Наш менеджер свяжется с вами в ближайшее время.""",
    
    "lead_created": """🔔 Новый лид MAXCAPITAL

👤 ФИО: {name}
📱 Телефон: {phone}
🎯 Услуга: {service}

💬 Комментарий:
{comment}""",
    
    "error_parsing": """❌ Не удалось распознать данные.

Пожалуйста, укажите в формате:
Фамилия Имя Телефон

Например: Иванов Иван +41791234567""",
    
    "consultation": """💬 Я готов проконсультировать вас по услугам MAXCAPITAL.

Задайте ваши вопросы, расскажите о целях и задачах.""",
    
    "contact_manager": "📞 Свяжитесь с нашим менеджером напрямую по телефону или напишите нам на сайте: https://maxcapital.ch/contacts"
}

