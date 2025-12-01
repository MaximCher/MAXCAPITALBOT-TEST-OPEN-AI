"""
MAXCAPITAL Bot - Dialog Message Model
Stores all messages from all conversations for admin panel
"""

from datetime import datetime
from typing import Optional
from sqlalchemy import BigInteger, String, Text, DateTime, Integer, Index
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
import structlog

from src.database import Base

logger = structlog.get_logger()


class DialogMessage(Base):
    """Stores all messages from all conversations"""
    
    __tablename__ = "dialog_messages"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    full_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    message_text: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # 'user' or 'assistant'
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    message_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        index=True
    )
    
    # Index for faster queries
    __table_args__ = (
        Index('idx_user_created', 'user_id', 'created_at'),
        Index('idx_chat_created', 'chat_id', 'created_at'),
    )
    
    def __repr__(self) -> str:
        return f"<DialogMessage(id={self.id}, user_id={self.user_id}, role={self.role})>"
    
    @classmethod
    async def create(
        cls,
        session: AsyncSession,
        user_id: int,
        message_text: str,
        role: str,
        chat_id: int,
        message_id: Optional[int] = None,
        username: Optional[str] = None,
        full_name: Optional[str] = None,
        phone: Optional[str] = None
    ) -> "DialogMessage":
        """Create a new dialog message"""
        dialog_msg = cls(
            user_id=user_id,
            username=username,
            full_name=full_name,
            phone=phone,
            message_text=message_text,
            role=role,
            chat_id=chat_id,
            message_id=message_id,
            created_at=datetime.utcnow()
        )
        session.add(dialog_msg)
        await session.commit()
        await session.refresh(dialog_msg)
        
        logger.debug(
            "dialog_message_created",
            message_id=dialog_msg.id,
            user_id=user_id,
            role=role
        )
        
        return dialog_msg
    
    @classmethod
    async def get_user_dialogs(
        cls,
        session: AsyncSession,
        user_id: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0
    ) -> list["DialogMessage"]:
        """Get dialog messages with filters"""
        query = select(cls)
        
        if user_id:
            query = query.where(cls.user_id == user_id)
        
        if start_date:
            query = query.where(cls.created_at >= start_date)
        
        if end_date:
            query = query.where(cls.created_at <= end_date)
        
        query = query.order_by(desc(cls.created_at)).limit(limit).offset(offset)
        
        result = await session.execute(query)
        return list(result.scalars().all())
    
    @classmethod
    async def get_unique_users(
        cls,
        session: AsyncSession,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> list[dict]:
        """Get list of unique users with their message counts"""
        # Build base query with filters
        base_conditions = []
        if start_date:
            base_conditions.append(cls.created_at >= start_date)
        if end_date:
            base_conditions.append(cls.created_at <= end_date)
        
        # Get all messages for users (with filters)
        query = select(cls)
        if base_conditions:
            from sqlalchemy import and_
            query = query.where(and_(*base_conditions))
        
        result = await session.execute(query)
        all_messages = list(result.scalars().all())
        
        if not all_messages:
            return []
        
        # Group by user_id and aggregate data
        users_dict = {}
        for msg in all_messages:
            user_id = msg.user_id
            
            if user_id not in users_dict:
                users_dict[user_id] = {
                    'user_id': user_id,
                    'full_name': None,
                    'phone': None,
                    'username': None,
                    'message_count': 0,
                    'last_message_at': None
                }
            
            user_data = users_dict[user_id]
            user_data['message_count'] += 1
            
            # Update fields with non-null values (prefer more recent)
            if msg.full_name and (not user_data['full_name'] or msg.created_at > (user_data['last_message_at'] or datetime.min)):
                user_data['full_name'] = msg.full_name
            if msg.phone and (not user_data['phone'] or msg.created_at > (user_data['last_message_at'] or datetime.min)):
                user_data['phone'] = msg.phone
            if msg.username and (not user_data['username'] or msg.created_at > (user_data['last_message_at'] or datetime.min)):
                user_data['username'] = msg.username
            
            # Update last message time
            if not user_data['last_message_at'] or msg.created_at > user_data['last_message_at']:
                user_data['last_message_at'] = msg.created_at
        
        # Convert to list and sort by last message date
        users_list = list(users_dict.values())
        users_list.sort(key=lambda x: x['last_message_at'] or datetime.min, reverse=True)
        
        return users_list
    
    @classmethod
    async def get_conversation(
        cls,
        session: AsyncSession,
        user_id: int,
        limit: int = 50
    ) -> list["DialogMessage"]:
        """Get conversation history for a specific user"""
        query = select(cls).where(
            cls.user_id == user_id
        ).order_by(cls.created_at).limit(limit)
        
        result = await session.execute(query)
        return list(result.scalars().all())


