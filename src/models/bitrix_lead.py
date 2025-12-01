"""
MAXCAPITAL Bot - Bitrix Lead Model
Stores created leads for statistics
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


class BitrixLead(Base):
    """Stores created Bitrix24 leads for statistics"""
    
    __tablename__ = "bitrix_leads"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lead_id: Mapped[int] = mapped_column(BigInteger, nullable=False, unique=True, index=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    full_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    service: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        index=True
    )
    
    # Index for faster queries
    __table_args__ = (
        Index('idx_lead_created', 'created_at'),
        Index('idx_user_lead', 'user_id', 'created_at'),
    )
    
    def __repr__(self) -> str:
        return f"<BitrixLead(id={self.id}, lead_id={self.lead_id}, user_id={self.user_id})>"
    
    @classmethod
    async def create(
        cls,
        session: AsyncSession,
        lead_id: int,
        user_id: int,
        full_name: Optional[str] = None,
        phone: Optional[str] = None,
        service: Optional[str] = None
    ) -> "BitrixLead":
        """Create a new Bitrix lead record"""
        lead = cls(
            lead_id=lead_id,
            user_id=user_id,
            full_name=full_name,
            phone=phone,
            service=service,
            created_at=datetime.utcnow()
        )
        session.add(lead)
        await session.commit()
        await session.refresh(lead)
        
        logger.info(
            "bitrix_lead_recorded",
            lead_id=lead_id,
            user_id=user_id
        )
        
        return lead
    
    @classmethod
    async def get_count(
        cls,
        session: AsyncSession,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> int:
        """Get count of leads with optional date filter"""
        query = select(func.count(cls.id))
        
        if start_date:
            query = query.where(cls.created_at >= start_date)
        
        if end_date:
            query = query.where(cls.created_at <= end_date)
        
        result = await session.execute(query)
        return result.scalar() or 0
    
    @classmethod
    async def get_today_count(cls, session: AsyncSession) -> int:
        """Get count of leads created today (UTC, naive datetime)"""
        from datetime import date
        today = date.today()
        today_start = datetime.combine(today, datetime.min.time())
        return await cls.get_count(session, start_date=today_start)

