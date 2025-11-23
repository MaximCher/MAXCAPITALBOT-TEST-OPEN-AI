"""
MAXCAPITAL Bot - User Memory Model
Stores user conversation history and profile data
"""

from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy import BigInteger, String, Text, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
import structlog

from src.database import Base

logger = structlog.get_logger()


class UserMemory(Base):
    """User memory and conversation history"""
    
    __tablename__ = "user_memory"
    
    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    full_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    selected_service: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    conversation_history: Mapped[List[Dict[str, Any]]] = mapped_column(
        JSON, 
        default=list,
        nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, 
        default=datetime.utcnow,
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, 
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )
    
    def __repr__(self) -> str:
        return f"<UserMemory(user_id={self.user_id}, name={self.full_name})>"
    
    @classmethod
    async def get_or_create(
        cls, 
        session: AsyncSession, 
        user_id: int
    ) -> "UserMemory":
        """Get existing user or create new one"""
        result = await session.execute(
            select(cls).where(cls.user_id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            user = cls(user_id=user_id, conversation_history=[])
            session.add(user)
            await session.commit()
            await session.refresh(user)
            logger.info("user_created", user_id=user_id)
        
        return user
    
    @classmethod
    async def update_user_data(
        cls,
        session: AsyncSession,
        user_id: int,
        full_name: Optional[str] = None,
        phone: Optional[str] = None,
        selected_service: Optional[str] = None
    ) -> "UserMemory":
        """Update user profile data"""
        user = await cls.get_or_create(session, user_id)
        
        if full_name:
            user.full_name = full_name
        if phone:
            user.phone = phone
        if selected_service:
            user.selected_service = selected_service
        
        user.updated_at = datetime.utcnow()
        await session.commit()
        await session.refresh(user)
        
        logger.info(
            "user_data_updated",
            user_id=user_id,
            name=full_name,
            service=selected_service
        )
        
        return user
    
    @classmethod
    async def add_message(
        cls,
        session: AsyncSession,
        user_id: int,
        role: str,
        content: str
    ) -> None:
        """Add message to conversation history"""
        user = await cls.get_or_create(session, user_id)
        
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Keep only last 20 messages to avoid token limits
        history = user.conversation_history or []
        history.append(message)
        if len(history) > 20:
            history = history[-20:]
        
        await session.execute(
            update(cls)
            .where(cls.user_id == user_id)
            .values(
                conversation_history=history,
                updated_at=datetime.utcnow()
            )
        )
        await session.commit()
        
        logger.debug("message_added", user_id=user_id, role=role)
    
    @classmethod
    async def get_conversation_history(
        cls,
        session: AsyncSession,
        user_id: int,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get recent conversation history"""
        user = await cls.get_or_create(session, user_id)
        history = user.conversation_history or []
        return history[-limit:] if history else []


