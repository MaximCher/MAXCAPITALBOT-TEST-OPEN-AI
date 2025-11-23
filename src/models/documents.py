"""
MAXCAPITAL Bot - Documents Model
Stores documents with vector embeddings for RAG
"""

from datetime import datetime
from typing import List, Optional, Tuple
from sqlalchemy import String, Text, Integer, DateTime, select, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.ext.asyncio import AsyncSession
from pgvector.sqlalchemy import Vector
import structlog

from src.database import Base

logger = structlog.get_logger()


class Document(Base):
    """Document with vector embedding for semantic search"""
    
    __tablename__ = "documents"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    content_text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[List[float]] = mapped_column(Vector(1536), nullable=True)
    file_type: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    file_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    drive_file_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
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
        return f"<Document(id={self.id}, filename={self.filename})>"
    
    @classmethod
    async def create_document(
        cls,
        session: AsyncSession,
        filename: str,
        content_text: str,
        embedding: List[float],
        file_type: Optional[str] = None,
        file_size: Optional[int] = None,
        drive_file_id: Optional[str] = None
    ) -> "Document":
        """Create new document with embedding"""
        document = cls(
            filename=filename,
            content_text=content_text,
            embedding=embedding,
            file_type=file_type,
            file_size=file_size,
            drive_file_id=drive_file_id
        )
        
        session.add(document)
        await session.commit()
        await session.refresh(document)
        
        logger.info(
            "document_created",
            doc_id=document.id,
            filename=filename,
            size=file_size
        )
        
        return document
    
    @classmethod
    async def find_similar(
        cls,
        session: AsyncSession,
        query_embedding: List[float],
        limit: int = 5,
        similarity_threshold: float = 0.7
    ) -> List[Tuple["Document", float]]:
        """
        Find similar documents using cosine similarity
        Returns list of (document, similarity_score) tuples
        """
        # Cosine similarity: 1 - cosine_distance
        similarity = 1 - cls.embedding.cosine_distance(query_embedding)
        
        result = await session.execute(
            select(cls, similarity.label("similarity"))
            .where(similarity > similarity_threshold)
            .order_by(similarity.desc())
            .limit(limit)
        )
        
        documents = [(row[0], row[1]) for row in result.all()]
        
        logger.info(
            "similar_documents_found",
            count=len(documents),
            threshold=similarity_threshold
        )
        
        return documents
    
    @classmethod
    async def get_all_documents(
        cls,
        session: AsyncSession,
        limit: int = 100
    ) -> List["Document"]:
        """Get all documents"""
        result = await session.execute(
            select(cls)
            .order_by(cls.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
    
    @classmethod
    async def delete_document(
        cls,
        session: AsyncSession,
        doc_id: int
    ) -> bool:
        """Delete document by ID"""
        result = await session.execute(
            select(cls).where(cls.id == doc_id)
        )
        document = result.scalar_one_or_none()
        
        if document:
            await session.delete(document)
            await session.commit()
            logger.info("document_deleted", doc_id=doc_id)
            return True
        
        return False
    
    @classmethod
    async def count_documents(cls, session: AsyncSession) -> int:
        """Count total documents"""
        result = await session.execute(select(func.count(cls.id)))
        return result.scalar() or 0


