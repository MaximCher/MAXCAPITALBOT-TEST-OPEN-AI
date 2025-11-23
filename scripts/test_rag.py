"""
Quick RAG test script
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database import init_db, close_db, get_session
from src.vector_store import VectorStore


async def test_rag():
    """Test vector search with different queries"""
    
    await init_db()
    
    async for session in get_session():
        vs = VectorStore(session)
        
        queries = [
            "недвижимость Москва",
            "зарубежные карты",
            "миграция виза",
            "резиденция другая страна",
            "real estate"
        ]
        
        print("\n" + "="*60)
        print("RAG Vector Search Test")
        print("="*60 + "\n")
        
        for query in queries:
            print(f"🔍 Query: '{query}'")
            results = await vs.search(query, limit=3, similarity_threshold=0.3)
            
            if results:
                print(f"   ✅ Found {len(results)} documents:")
                for doc, score in results:
                    print(f"      - {doc.filename}")
                    print(f"        Similarity: {score:.2%}")
            else:
                print(f"   ❌ No results found")
            
            print()
    
    await close_db()


if __name__ == "__main__":
    asyncio.run(test_rag())

