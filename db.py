"""
Database module for MAXCAPITAL Bot.
Handles PostgreSQL database operations for statistics and user tracking.
"""

import os
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from contextlib import contextmanager

try:
    import psycopg2
    from psycopg2 import pool, sql
    from psycopg2.extras import RealDictCursor
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False
    psycopg2 = None

logger = logging.getLogger(__name__)


class DatabaseConfig:
    """Database configuration."""
    
    def __init__(self):
        self.host = os.environ.get("DB_HOST", "localhost")
        self.port = int(os.environ.get("DB_PORT", 5432))
        self.database = os.environ.get("DB_NAME", "maxcapital_bot")
        self.user = os.environ.get("DB_USER", "postgres")
        self.password = os.environ.get("DB_PASSWORD", "")
        self.min_conn = int(os.environ.get("DB_MIN_CONN", 1))
        self.max_conn = int(os.environ.get("DB_MAX_CONN", 10))
    
    def get_connection_string(self) -> str:
        """Get PostgreSQL connection string."""
        return f"host={self.host} port={self.port} dbname={self.database} user={self.user} password={self.password}"


class Database:
    """Database connection manager."""
    
    def __init__(self, config: Optional[DatabaseConfig] = None):
        self.config = config or DatabaseConfig()
        self.connection_pool = None
        
        if not PSYCOPG2_AVAILABLE:
            logger.warning("psycopg2 not installed. Database features will be disabled.")
            return
        
        try:
            self.connection_pool = psycopg2.pool.ThreadedConnectionPool(
                self.config.min_conn,
                self.config.max_conn,
                self.config.get_connection_string()
            )
            logger.info("Database connection pool created successfully")
            # Initialize database schema
            self._initialize_schema()
        except Exception as e:
            logger.error(f"Failed to create database connection pool: {e}")
            self.connection_pool = None
    
    def _initialize_schema(self):
        """Initialize database schema - create tables if they don't exist."""
        if not self.is_available():
            return
        
        try:
            schema_sql = """
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
                status VARCHAR(50) DEFAULT 'active',
                services_interested TEXT[],
                lead_id INTEGER,
                contact_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            -- Таблица для отслеживания сообщений в сессиях
            CREATE TABLE IF NOT EXISTS bot_messages (
                id SERIAL PRIMARY KEY,
                session_id INTEGER REFERENCES bot_sessions(id) ON DELETE CASCADE,
                message_text TEXT NOT NULL,
                message_type VARCHAR(20) NOT NULL,
                detected_intent VARCHAR(100),
                detected_services TEXT[],
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            -- Таблица для отслеживания интереса к услугам
            CREATE TABLE IF NOT EXISTS service_interests (
                id SERIAL PRIMARY KEY,
                session_id INTEGER REFERENCES bot_sessions(id) ON DELETE CASCADE,
                service_code VARCHAR(100) NOT NULL,
                service_name VARCHAR(255) NOT NULL,
                interest_level VARCHAR(50) DEFAULT 'interested',
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
            DROP TRIGGER IF EXISTS update_bot_users_updated_at ON bot_users;
            CREATE TRIGGER update_bot_users_updated_at BEFORE UPDATE ON bot_users
                FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

            DROP TRIGGER IF EXISTS update_bot_sessions_updated_at ON bot_sessions;
            CREATE TRIGGER update_bot_sessions_updated_at BEFORE UPDATE ON bot_sessions
                FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

            DROP TRIGGER IF EXISTS update_service_interests_updated_at ON service_interests;
            CREATE TRIGGER update_service_interests_updated_at BEFORE UPDATE ON service_interests
                FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
            """
            
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(schema_sql)
                    logger.info("Database schema initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing database schema: {e}")
            # Don't raise - allow bot to continue without DB
    
    def is_available(self) -> bool:
        """Check if database is available."""
        return PSYCOPG2_AVAILABLE and self.connection_pool is not None
    
    @contextmanager
    def get_connection(self):
        """Get database connection from pool."""
        if not self.is_available():
            raise RuntimeError("Database is not available")
        
        conn = self.connection_pool.getconn()
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            error_msg = str(e)
            # Don't log as error if tables don't exist (database not set up)
            if "does not exist" in error_msg or "relation" in error_msg.lower():
                logger.debug(f"Database tables not found: {e}")
            else:
                logger.error(f"Database error: {e}")
            raise
        finally:
            self.connection_pool.putconn(conn)
    
    def upsert_user(
        self,
        telegram_user_id: int,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        phone: Optional[str] = None
    ) -> Optional[int]:
        """Create or update user."""
        if not self.is_available():
            return None
        
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO bot_users (telegram_user_id, username, first_name, last_name, phone)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (telegram_user_id) 
                        DO UPDATE SET
                            username = EXCLUDED.username,
                            first_name = EXCLUDED.first_name,
                            last_name = EXCLUDED.last_name,
                            phone = COALESCE(EXCLUDED.phone, bot_users.phone),
                            updated_at = CURRENT_TIMESTAMP
                        RETURNING id
                    """, (telegram_user_id, username, first_name, last_name, phone))
                    result = cur.fetchone()
                    return result[0] if result else None
        except Exception as e:
            error_msg = str(e)
            # Don't log as error if tables don't exist (database not set up)
            if "does not exist" in error_msg or "relation" in error_msg.lower():
                logger.debug(f"Database tables not found, skipping user upsert: {e}")
            else:
                logger.error(f"Error upserting user: {e}")
            return None
    
    def create_session(
        self,
        user_id: int,
        telegram_user_id: int,
        status: str = "active"
    ) -> Optional[int]:
        """Create a new session."""
        if not self.is_available():
            return None
        
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO bot_sessions (user_id, telegram_user_id, status)
                        VALUES (%s, %s, %s)
                        RETURNING id
                    """, (user_id, telegram_user_id, status))
                    result = cur.fetchone()
                    return result[0] if result else None
        except Exception as e:
            logger.error(f"Error creating session: {e}")
            return None
    
    def update_session(
        self,
        session_id: int,
        status: Optional[str] = None,
        services_interested: Optional[List[str]] = None,
        lead_id: Optional[int] = None,
        contact_id: Optional[int] = None
    ) -> bool:
        """Update session."""
        if not self.is_available():
            return False
        
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    updates = []
                    params = []
                    
                    if status:
                        updates.append("status = %s")
                        params.append(status)
                    
                    if services_interested is not None:
                        updates.append("services_interested = %s")
                        params.append(services_interested)
                    
                    if lead_id is not None:
                        updates.append("lead_id = %s")
                        params.append(lead_id)
                    
                    if contact_id is not None:
                        updates.append("contact_id = %s")
                        params.append(contact_id)
                    
                    if updates:
                        params.append(session_id)
                        cur.execute(
                            f"UPDATE bot_sessions SET {', '.join(updates)} WHERE id = %s",
                            params
                        )
                    return True
        except Exception as e:
            logger.error(f"Error updating session: {e}")
            return False
    
    def add_message(
        self,
        session_id: int,
        message_text: str,
        message_type: str,
        detected_intent: Optional[str] = None,
        detected_services: Optional[List[str]] = None
    ) -> Optional[int]:
        """Add message to session."""
        if not self.is_available():
            return None
        
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO bot_messages (session_id, message_text, message_type, detected_intent, detected_services)
                        VALUES (%s, %s, %s, %s, %s)
                        RETURNING id
                    """, (session_id, message_text, message_type, detected_intent, detected_services))
                    result = cur.fetchone()
                    return result[0] if result else None
        except Exception as e:
            logger.error(f"Error adding message: {e}")
            return None
    
    def add_service_interest(
        self,
        session_id: int,
        service_code: str,
        service_name: str,
        interest_level: str = "interested"
    ) -> Optional[int]:
        """Add or update service interest."""
        if not self.is_available():
            return None
        
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO service_interests (session_id, service_code, service_name, interest_level)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (session_id, service_code)
                        DO UPDATE SET
                            interest_level = EXCLUDED.interest_level,
                            updated_at = CURRENT_TIMESTAMP
                        RETURNING id
                    """, (session_id, service_code, service_name, interest_level))
                    result = cur.fetchone()
                    return result[0] if result else None
        except Exception as e:
            logger.error(f"Error adding service interest: {e}")
            return None
    
    def get_user_session(self, telegram_user_id: int) -> Optional[int]:
        """Get active session ID for user."""
        if not self.is_available():
            return None
        
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        SELECT id FROM bot_sessions
                        WHERE telegram_user_id = %s
                        AND status != 'completed'
                        ORDER BY session_started_at DESC
                        LIMIT 1
                    """, (telegram_user_id,))
                    result = cur.fetchone()
                    return result['id'] if result else None
        except Exception as e:
            logger.error(f"Error getting user session: {e}")
            return None
    
    def get_session_messages(self, session_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        """Get conversation history from database for a session."""
        if not self.is_available():
            return []
        
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        SELECT message_text, message_type, detected_intent, created_at
                        FROM bot_messages
                        WHERE session_id = %s
                        ORDER BY created_at ASC
                        LIMIT %s
                    """, (session_id, limit))
                    messages = cur.fetchall()
                    # Convert to format expected by AI: [{"role": "user/assistant", "content": "..."}]
                    result = []
                    for msg in messages:
                        role = "user" if msg['message_type'] == "user" else "assistant"
                        result.append({
                            "role": role,
                            "content": msg['message_text']
                        })
                    return result
        except Exception as e:
            logger.error(f"Error getting session messages: {e}")
            return []
    
    def get_session_lead_id(self, session_id: int) -> Optional[int]:
        """Get lead_id for a session if it exists."""
        if not self.is_available():
            return None
        
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        SELECT lead_id FROM bot_sessions
                        WHERE id = %s
                    """, (session_id,))
                    result = cur.fetchone()
                    return result['lead_id'] if result and result['lead_id'] else None
        except Exception as e:
            logger.error(f"Error getting session lead_id: {e}")
            return None
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get bot statistics."""
        if not self.is_available():
            return {
                "total_visitors": 0,
                "total_interested": 0,
                "total_leads": 0,
                "service_distribution": {},
                "daily_stats": []
            }
        
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    # Overall statistics
                    # total_visitors = все, кто обратился (status = 'active' или любой статус)
                    # total_interested = заинтересовались услугами (status = 'interested')
                    # total_leads = создали лид и ждут звонка (status = 'converted_to_lead' или lead_id IS NOT NULL)
                    cur.execute("""
                        SELECT 
                            COUNT(DISTINCT id) as total_visitors,
                            COUNT(DISTINCT id) FILTER (WHERE status = 'interested') as total_interested,
                            COUNT(DISTINCT id) FILTER (WHERE status = 'converted_to_lead' OR lead_id IS NOT NULL) as total_leads
                        FROM bot_sessions
                    """)
                    stats = cur.fetchone()
                    
                    # Service distribution
                    cur.execute("""
                        SELECT service_code, service_name, COUNT(*) as count
                        FROM service_interests
                        GROUP BY service_code, service_name
                        ORDER BY count DESC
                    """)
                    services = cur.fetchall()
                    service_distribution = {
                        row['service_code']: {
                            'name': row['service_name'],
                            'count': row['count']
                        }
                        for row in services
                    }
                    
                    # Daily statistics for last 7 days
                    cur.execute("""
                        SELECT 
                            DATE(session_started_at) as date,
                            COUNT(*) as visitors,
                            COUNT(*) FILTER (WHERE status = 'interested') as interested,
                            COUNT(*) FILTER (WHERE status = 'converted_to_lead' OR lead_id IS NOT NULL) as leads
                        FROM bot_sessions
                        WHERE session_started_at >= CURRENT_DATE - INTERVAL '7 days'
                        GROUP BY DATE(session_started_at)
                        ORDER BY date DESC
                    """)
                    daily_stats = [dict(row) for row in cur.fetchall()]
                    
                    return {
                        "total_visitors": stats['total_visitors'] or 0,
                        "total_interested": stats['total_interested'] or 0,
                        "total_leads": stats['total_leads'] or 0,
                        "service_distribution": service_distribution,
                        "daily_stats": daily_stats
                    }
        except Exception as e:
            logger.error(f"Error getting statistics: {e}")
            return {
                "total_visitors": 0,
                "total_interested": 0,
                "total_leads": 0,
                "service_distribution": {},
                "daily_stats": []
            }
    
    def close(self):
        """Close database connection pool."""
        if self.connection_pool:
            self.connection_pool.closeall()
            logger.info("Database connection pool closed")


# Global database instance
database = Database()


