"""
MAXCAPITAL Bot - Document Loader Script
Loads documents from Google Drive into vector store
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database import init_db, close_db, get_session
from src.google_drive_loader import GoogleDriveLoader
from src.vector_store import VectorStore
from src.logger import setup_logging
import structlog

logger = structlog.get_logger()


async def load_documents_from_drive():
    """Load all documents from Google Drive to vector store"""
    
    # Setup logging
    setup_logging()
    
    logger.info("starting_document_load")
    
    try:
        # Initialize database
        await init_db()
        
        # Get database session
        async for session in get_session():
            # Initialize loader and vector store
            loader = GoogleDriveLoader()
            vector_store = VectorStore(session)
            
            # Check current document count
            current_count = await vector_store.count_documents()
            logger.info("current_documents_in_store", count=current_count)
            
            # Load documents from Google Drive
            logger.info("loading_documents_from_google_drive")
            documents = await loader.load_all_documents()
            
            if not documents:
                logger.warning("no_documents_found")
                print("⚠️  No documents found in Google Drive")
                return
            
            logger.info("documents_loaded_from_drive", count=len(documents))
            print(f"✅ Loaded {len(documents)} documents from Google Drive")
            
            # Add each document to vector store
            success_count = 0
            for i, doc in enumerate(documents, 1):
                try:
                    print(f"Processing {i}/{len(documents)}: {doc['filename']}")
                    
                    await vector_store.add_document(
                        filename=doc['filename'],
                        content=doc['content'],
                        file_type=doc.get('file_type'),
                        file_size=doc.get('file_size'),
                        drive_file_id=doc.get('drive_file_id')
                    )
                    
                    success_count += 1
                    print(f"  ✅ Added to vector store")
                    
                except Exception as e:
                    logger.error(
                        "document_add_failed",
                        filename=doc['filename'],
                        error=str(e)
                    )
                    print(f"  ❌ Failed: {str(e)}")
            
            # Final statistics
            new_count = await vector_store.count_documents()
            logger.info(
                "document_load_completed",
                total_documents=new_count,
                added=success_count
            )
            
            print(f"\n{'='*50}")
            print(f"✅ Document loading completed")
            print(f"📊 Total documents in store: {new_count}")
            print(f"➕ Successfully added: {success_count}/{len(documents)}")
            print(f"{'='*50}")
    
    except Exception as e:
        logger.error("document_load_error", error=str(e), exc_info=True)
        print(f"❌ Error: {str(e)}")
        return 1
    
    finally:
        await close_db()
    
    return 0


async def list_documents():
    """List all documents in vector store"""
    
    setup_logging()
    
    try:
        await init_db()
        
        async for session in get_session():
            vector_store = VectorStore(session)
            
            documents = await vector_store.list_all_documents()
            
            print(f"\n{'='*70}")
            print(f"📚 Documents in Vector Store: {len(documents)}")
            print(f"{'='*70}\n")
            
            for i, doc in enumerate(documents, 1):
                print(f"{i}. {doc.filename}")
                print(f"   ID: {doc.id}")
                print(f"   Type: {doc.file_type or 'unknown'}")
                print(f"   Size: {doc.file_size or 0} bytes")
                print(f"   Content length: {len(doc.content_text)} chars")
                print(f"   Created: {doc.created_at}")
                print()
    
    finally:
        await close_db()


async def test_search(query: str):
    """Test vector search with a query"""
    
    setup_logging()
    
    try:
        await init_db()
        
        async for session in get_session():
            vector_store = VectorStore(session)
            
            print(f"\n🔍 Searching for: '{query}'\n")
            
            results = await vector_store.search(query, limit=5, similarity_threshold=0.5)
            
            if not results:
                print("❌ No results found")
                return
            
            print(f"✅ Found {len(results)} results:\n")
            
            for i, (doc, similarity) in enumerate(results, 1):
                print(f"{i}. {doc.filename}")
                print(f"   Similarity: {similarity:.2%}")
                print(f"   Preview: {doc.content_text[:200]}...")
                print()
    
    finally:
        await close_db()


def main():
    """Main CLI entry point"""
    import sys
    
    if len(sys.argv) < 2:
        print("MAXCAPITAL Bot - Document Management")
        print("\nUsage:")
        print("  python scripts/load_documents.py load     - Load documents from Google Drive")
        print("  python scripts/load_documents.py list     - List all documents in vector store")
        print("  python scripts/load_documents.py search 'query'  - Test vector search")
        print("\nExamples:")
        print("  python scripts/load_documents.py load")
        print("  python scripts/load_documents.py search 'venture capital'")
        return 1
    
    command = sys.argv[1].lower()
    
    if command == "load":
        return asyncio.run(load_documents_from_drive())
    elif command == "list":
        return asyncio.run(list_documents())
    elif command == "search":
        if len(sys.argv) < 3:
            print("❌ Please provide search query")
            return 1
        query = " ".join(sys.argv[2:])
        return asyncio.run(test_search(query))
    else:
        print(f"❌ Unknown command: {command}")
        return 1


if __name__ == "__main__":
    sys.exit(main())


