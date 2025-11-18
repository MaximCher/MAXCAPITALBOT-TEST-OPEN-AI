-- SQL скрипт для создания таблицы статистики бота MAXCAPITAL
-- PostgreSQL Database Schema

-- Таблица для отслеживания пользователей бота
CREATE TABLE IF NOT EXISTS bot_users (
    id SERIAL PRIMARY KEY,
    telegram_user_id BIGINT UNIQUE NOT NULL,
    username VARCHAR(255),
    first_name VARCHAR(255),
    last_name VARCHAR(255),
    phone VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Таблица для отслеживания сессий (обращений к боту)
CREATE TABLE IF NOT EXISTS bot_sessions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES bot_users(id) ON DELETE CASCADE,
    telegram_user_id BIGINT NOT NULL,
    session_started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    session_ended_at TIMESTAMP,
    status VARCHAR(50) DEFAULT 'active', -- active, interested, converted_to_lead, completed
    services_interested TEXT[], -- Массив услуг, которые заинтересовали пользователя
    lead_id INTEGER, -- ID лида в Bitrix24
    contact_id INTEGER, -- ID контакта в Bitrix24
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Таблица для отслеживания сообщений в сессиях
CREATE TABLE IF NOT EXISTS bot_messages (
    id SERIAL PRIMARY KEY,
    session_id INTEGER REFERENCES bot_sessions(id) ON DELETE CASCADE,
    message_text TEXT NOT NULL,
    message_type VARCHAR(20) NOT NULL, -- user, assistant
    detected_intent VARCHAR(100),
    detected_services TEXT[], -- Массив услуг, обнаруженных в сообщении
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Таблица для отслеживания интереса к услугам
CREATE TABLE IF NOT EXISTS service_interests (
    id SERIAL PRIMARY KEY,
    session_id INTEGER REFERENCES bot_sessions(id) ON DELETE CASCADE,
    service_code VARCHAR(100) NOT NULL, -- Код услуги (venture_capital, hnwi, real_estate, etc.)
    service_name VARCHAR(255) NOT NULL, -- Название услуги
    interest_level VARCHAR(50) DEFAULT 'interested', -- interested, consulting, confirmed
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(session_id, service_code)
);

-- Индексы для оптимизации запросов
CREATE INDEX IF NOT EXISTS idx_bot_users_telegram_id ON bot_users(telegram_user_id);
CREATE INDEX IF NOT EXISTS idx_bot_sessions_user_id ON bot_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_bot_sessions_telegram_user_id ON bot_sessions(telegram_user_id);
CREATE INDEX IF NOT EXISTS idx_bot_sessions_status ON bot_sessions(status);
CREATE INDEX IF NOT EXISTS idx_bot_sessions_created_at ON bot_sessions(created_at);
CREATE INDEX IF NOT EXISTS idx_bot_messages_session_id ON bot_messages(session_id);
CREATE INDEX IF NOT EXISTS idx_bot_messages_created_at ON bot_messages(created_at);
CREATE INDEX IF NOT EXISTS idx_service_interests_session_id ON service_interests(session_id);
CREATE INDEX IF NOT EXISTS idx_service_interests_service_code ON service_interests(service_code);

-- Функция для автоматического обновления updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Триггеры для автоматического обновления updated_at
CREATE TRIGGER update_bot_users_updated_at BEFORE UPDATE ON bot_users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_bot_sessions_updated_at BEFORE UPDATE ON bot_sessions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_service_interests_updated_at BEFORE UPDATE ON service_interests
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Представление для статистики
CREATE OR REPLACE VIEW bot_statistics_view AS
SELECT 
    COUNT(DISTINCT bs.id) FILTER (WHERE bs.status = 'active') as total_visitors,
    COUNT(DISTINCT bs.id) FILTER (WHERE bs.status IN ('interested', 'converted_to_lead', 'completed')) as total_interested,
    COUNT(DISTINCT bs.id) FILTER (WHERE bs.status = 'converted_to_lead' OR bs.lead_id IS NOT NULL) as total_leads,
    COUNT(DISTINCT si.service_code) as unique_services_interest,
    COUNT(DISTINCT DATE(bs.session_started_at)) as active_days
FROM bot_sessions bs
LEFT JOIN service_interests si ON si.session_id = bs.id;

-- Комментарии к таблицам
COMMENT ON TABLE bot_users IS 'Пользователи Telegram бота';
COMMENT ON TABLE bot_sessions IS 'Сессии (обращения) пользователей к боту';
COMMENT ON TABLE bot_messages IS 'Сообщения в сессиях';
COMMENT ON TABLE service_interests IS 'Интерес пользователей к услугам';

COMMENT ON COLUMN bot_sessions.status IS 'Статус сессии: active - просто обратился, interested - заинтересовался услугами, converted_to_lead - создан лид, completed - завершена';
COMMENT ON COLUMN bot_sessions.services_interested IS 'Массив кодов услуг, которые заинтересовали пользователя';
COMMENT ON COLUMN bot_messages.detected_services IS 'Массив кодов услуг, обнаруженных в сообщении';


