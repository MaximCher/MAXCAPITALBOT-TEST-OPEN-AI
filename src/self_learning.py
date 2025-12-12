"""
MAXCAPITAL Bot - Self Learning Module
Learns from highly rated dialogs and adds them to knowledge base
"""

import asyncio
from typing import List, Optional
from datetime import datetime, timedelta
import structlog

from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_session
from src.models.dialog_rating import DialogRating
from src.vector_store import VectorStore
from src.config import SERVICES

logger = structlog.get_logger()


class SelfLearning:
    """Self-learning system that adds good dialogs to knowledge base"""
    
    def __init__(self):
        self.min_rating_threshold = 4  # Only 4-5 star ratings
        self.learning_interval_minutes = 120  # Learn every 2 hours
        self.batch_size = 50  # Process 50 dialogs at a time
        self.last_learning: Optional[datetime] = None
        
    async def should_learn(self) -> bool:
        """Check if we should run learning"""
        if not self.last_learning:
            return True
        
        time_since_learning = datetime.utcnow() - self.last_learning
        return time_since_learning > timedelta(minutes=self.learning_interval_minutes)
    
    async def format_dialog_as_document(
        self,
        rating: DialogRating
    ) -> str:
        """Format a rated dialog as a knowledge base document"""
        service_name = SERVICES.get(rating.service, "Общая консультация")
        
        content = f"""# Диалог с клиентом - {service_name}

## Вопрос клиента:
{rating.user_message}

## Ответ эксперта MAXCAPITAL:
{rating.bot_response}

---
Источник: Реальный диалог с клиентом
Оценка качества: {rating.rating}/5 ⭐
Дата: {rating.created_at.strftime('%Y-%m-%d')}
Услуга: {service_name}

Этот диалог был высоко оценен клиентом и добавлен в базу знаний для улучшения качества консультаций.
"""
        return content
    
    async def add_dialog_to_knowledge(
        self,
        session: AsyncSession,
        rating: DialogRating
    ) -> bool:
        """Add a single dialog to knowledge base"""
        try:
            # Format as document
            content = await self.format_dialog_as_document(rating)
            
            # Create filename
            filename = f"learned_dialog_{rating.id}_{rating.created_at.strftime('%Y%m%d')}.txt"
            
            # Add to vector store
            vector_store = VectorStore(session)
            document = await vector_store.add_document(
                filename=filename,
                content=content,
                file_type="text/plain",
                file_size=len(content)
            )
            
            # Mark as added
            await DialogRating.mark_as_added_to_knowledge(session, rating.id)
            
            logger.info(
                "dialog_learned",
                rating_id=rating.id,
                document_id=document.id,
                rating=rating.rating,
                service=rating.service
            )
            
            return True
            
        except Exception as e:
            logger.error(
                "dialog_learning_failed",
                rating_id=rating.id,
                error=str(e)
            )
            return False
    
    async def learn_from_dialogs(self) -> dict:
        """Process highly rated dialogs and add to knowledge base"""
        if not await self.should_learn():
            logger.debug("learning_skipped", reason="too_soon")
            return {"learned": 0, "errors": 0}
        
        logger.info("self_learning_starting")
        
        stats = {
            "learned": 0,
            "errors": 0,
            "start_time": datetime.utcnow()
        }
        
        try:
            async for session in get_session():
                # Get highly rated dialogs
                highly_rated = await DialogRating.get_highly_rated_dialogs(
                    session=session,
                    min_rating=self.min_rating_threshold,
                    limit=self.batch_size,
                    not_added_only=True
                )
                
                if not highly_rated:
                    logger.info("no_dialogs_to_learn")
                    break
                
                logger.info(
                    "learning_dialogs_found",
                    count=len(highly_rated),
                    min_rating=self.min_rating_threshold
                )
                
                # Process each dialog
                for rating in highly_rated:
                    success = await self.add_dialog_to_knowledge(session, rating)
                    
                    if success:
                        stats["learned"] += 1
                    else:
                        stats["errors"] += 1
                
                break  # Exit session generator
            
            self.last_learning = datetime.utcnow()
            stats["end_time"] = datetime.utcnow()
            stats["duration_seconds"] = (stats["end_time"] - stats["start_time"]).total_seconds()
            
            logger.info(
                "self_learning_completed",
                learned=stats["learned"],
                errors=stats["errors"],
                duration=stats["duration_seconds"]
            )
            
            return stats
            
        except Exception as e:
            logger.error("self_learning_error", error=str(e))
            stats["errors"] += 1
            return stats
    
    async def get_learning_statistics(self, session: AsyncSession) -> dict:
        """Get statistics about learned dialogs"""
        # Total rated dialogs
        from sqlalchemy import select, func
        
        total_ratings = await session.execute(
            select(func.count(DialogRating.id))
        )
        
        learned_count = await session.execute(
            select(func.count(DialogRating.id)).where(
                DialogRating.is_added_to_knowledge == True
            )
        )
        
        avg_rating = await DialogRating.get_average_rating(session, days=30)
        
        pending_count = await session.execute(
            select(func.count(DialogRating.id)).where(
                DialogRating.rating >= self.min_rating_threshold,
                DialogRating.is_added_to_knowledge == False
            )
        )
        
        return {
            "total_ratings": total_ratings.scalar() or 0,
            "learned_dialogs": learned_count.scalar() or 0,
            "pending_to_learn": pending_count.scalar() or 0,
            "avg_rating_30d": round(avg_rating, 2)
        }
    
    async def start_background_learning(self):
        """Start background learning loop"""
        logger.info(
            "self_learning_started",
            interval_minutes=self.learning_interval_minutes,
            min_rating=self.min_rating_threshold
        )
        
        while True:
            try:
                await self.learn_from_dialogs()
            except Exception as e:
                logger.error("background_learning_error", error=str(e))
            
            # Wait before next learning cycle
            await asyncio.sleep(self.learning_interval_minutes * 60)


# Global instance
self_learning = SelfLearning()





