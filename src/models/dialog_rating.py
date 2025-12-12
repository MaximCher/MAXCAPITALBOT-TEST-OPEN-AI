"""
MAXCAPITAL Bot - Dialog Rating Model
Stores user ratings for AI responses to enable self-learning
"""

from datetime import datetime
from typing import Optional, List
from sqlalchemy import BigInteger, Integer, Text, DateTime, Boolean, Float
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc
import structlog

from src.database import Base

logger = structlog.get_logger()


class DialogRating(Base):
    """Stores ratings for bot responses to learn from good interactions"""
    
    __tablename__ = "dialog_ratings"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    user_message: Mapped[str] = mapped_column(Text, nullable=False)
    bot_response: Mapped[str] = mapped_column(Text, nullable=False)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-5 stars
    service: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Flags
    is_added_to_knowledge: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    relevance_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        index=True
    )
    
    def __repr__(self) -> str:
        return f"<DialogRating(id={self.id}, user_id={self.user_id}, rating={self.rating})>"
    
    @classmethod
    async def create_rating(
        cls,
        session: AsyncSession,
        user_id: int,
        user_message: str,
        bot_response: str,
        rating: int,
        service: Optional[str] = None
    ) -> "DialogRating":
        """Create a new rating for a dialog"""
        rating_obj = cls(
            user_id=user_id,
            user_message=user_message,
            bot_response=bot_response,
            rating=rating,
            service=service,
            created_at=datetime.utcnow()
        )
        session.add(rating_obj)
        await session.commit()
        await session.refresh(rating_obj)
        
        logger.info(
            "dialog_rating_created",
            rating_id=rating_obj.id,
            user_id=user_id,
            rating=rating
        )
        
        return rating_obj
    
    @classmethod
    async def get_highly_rated_dialogs(
        cls,
        session: AsyncSession,
        min_rating: int = 4,
        limit: int = 100,
        not_added_only: bool = True
    ) -> List["DialogRating"]:
        """Get highly rated dialogs for learning"""
        query = select(cls).where(cls.rating >= min_rating)
        
        if not_added_only:
            query = query.where(cls.is_added_to_knowledge == False)
        
        query = query.order_by(desc(cls.rating), desc(cls.created_at)).limit(limit)
        
        result = await session.execute(query)
        return list(result.scalars().all())
    
    @classmethod
    async def mark_as_added_to_knowledge(
        cls,
        session: AsyncSession,
        rating_id: int
    ) -> None:
        """Mark dialog as added to knowledge base"""
        result = await session.execute(
            select(cls).where(cls.id == rating_id)
        )
        rating = result.scalar_one_or_none()
        
        if rating:
            rating.is_added_to_knowledge = True
            await session.commit()
            
            logger.info(
                "dialog_marked_as_learned",
                rating_id=rating_id
            )
    
    @classmethod
    async def get_average_rating(
        cls,
        session: AsyncSession,
        days: int = 7
    ) -> float:
        """Get average rating for last N days"""
        from datetime import timedelta
        from sqlalchemy import func
        
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        result = await session.execute(
            select(func.avg(cls.rating)).where(cls.created_at >= cutoff_date)
        )
        
        avg = result.scalar()
        return float(avg) if avg else 0.0





