"""
MAXCAPITAL Bot - Vector Store Module
Manages document embeddings and semantic search (RAG)
"""

from typing import List, Tuple, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from openai import AsyncOpenAI
import structlog

from src.config import settings
from src.models.documents import Document

logger = structlog.get_logger()

# Initialize OpenAI async client
client = AsyncOpenAI(api_key=settings.openai_api_key)


class VectorStore:
    """Manages vector embeddings and semantic search"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.embedding_model = settings.embedding_model
    
    async def create_embedding(self, text: str) -> List[float]:
        """Create embedding vector for text using OpenAI"""
        try:
            # Clean and truncate text if needed (max ~8000 tokens ~ 10000 chars for Russian)
            original_length = len(text)
            text = text.strip()
            if len(text) > 10000:  # Very conservative char limit for Russian text (8000 tokens ~ 10000 chars cyrillic)
                text = text[:10000]
                logger.warning("text_truncated_for_embedding", original_length=original_length, truncated_to=10000)
            
            response = await client.embeddings.create(
                model=self.embedding_model,
                input=text
            )
            
            embedding = response.data[0].embedding
            logger.debug(
                "embedding_created",
                text_length=len(text),
                embedding_dim=len(embedding)
            )
            
            return embedding
            
        except Exception as e:
            logger.error("embedding_failed", error=str(e))
            raise
    
    async def add_document(
        self,
        filename: str,
        content: str,
        file_type: Optional[str] = None,
        file_size: Optional[int] = None,
        drive_file_id: Optional[str] = None
    ) -> Document:
        """Add document with embedding to vector store"""
        try:
            # Ensure file_size is int or None
            if file_size is not None:
                file_size = int(file_size)
            
            # Create embedding
            embedding = await self.create_embedding(content)
            
            # Save to database
            document = await Document.create_document(
                session=self.session,
                filename=filename,
                content_text=content,
                embedding=embedding,
                file_type=file_type,
                file_size=file_size,
                drive_file_id=drive_file_id
            )
            
            logger.info(
                "document_added_to_vector_store",
                doc_id=document.id,
                filename=filename
            )
            
            return document
            
        except Exception as e:
            logger.error("add_document_failed", filename=filename, error=str(e))
            raise
    
    async def search(
        self,
        query: str,
        limit: int = 5,
        similarity_threshold: float = 0.25
    ) -> List[Tuple[Document, float]]:
        """
        Search for similar documents using semantic similarity
        Returns list of (document, similarity_score) tuples
        """
        try:
            # Create query embedding
            query_embedding = await self.create_embedding(query)
            
            # Search similar documents
            results = await Document.find_similar(
                session=self.session,
                query_embedding=query_embedding,
                limit=limit,
                similarity_threshold=similarity_threshold
            )
            
            logger.info(
                "vector_search_completed",
                query_length=len(query),
                results_count=len(results)
            )
            
            return results
            
        except Exception as e:
            logger.error("vector_search_failed", error=str(e))
            return []
    
    async def get_context_for_query(
        self,
        query: str,
        max_context_length: int = 3000
    ) -> str:
        """
        Get relevant context from documents for RAG
        Returns concatenated relevant document excerpts
        """
        results = await self.search(query, limit=5, similarity_threshold=0.25)
        
        if not results:
            logger.info("no_relevant_context_found")
            return ""
        
        context_parts = []
        total_length = 0
        
        for doc, similarity in results:
            # Add document with similarity score
            part = f"[Документ: {doc.filename}, релевантность: {similarity:.2f}]\n{doc.content_text}\n"
            
            if total_length + len(part) > max_context_length:
                # Truncate if needed
                remaining = max_context_length - total_length
                if remaining > 200:  # Only add if meaningful chunk remains
                    context_parts.append(part[:remaining] + "...")
                break
            
            context_parts.append(part)
            total_length += len(part)
        
        context = "\n---\n".join(context_parts)
        
        logger.info(
            "context_prepared",
            documents_used=len(context_parts),
            context_length=len(context)
        )
        
        return context
    
    async def count_documents(self) -> int:
        """Get total number of documents in vector store"""
        return await Document.count_documents(self.session)
    
    async def list_all_documents(self, limit: int = 100) -> List[Document]:
        """List all documents in store"""
        return await Document.get_all_documents(self.session, limit=limit)

