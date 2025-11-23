"""
MAXCAPITAL Bot - Testing Script
Tests various bot components
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database import init_db, close_db, get_session
from src.ai_agent import AIAgent
from src.bitrix import BitrixClient
from src.vector_store import VectorStore
from src.logger import setup_logging
import structlog

logger = structlog.get_logger()


async def test_database():
    """Test database connection"""
    print("\n🔍 Testing database connection...")
    
    try:
        await init_db()
        
        async for session in get_session():
            from src.models.user_memory import UserMemory
            
            # Try to query
            user = await UserMemory.get_or_create(session, 12345)
            
            print("✅ Database connection successful")
            print(f"   Test user ID: {user.user_id}")
            return True
    
    except Exception as e:
        print(f"❌ Database connection failed: {str(e)}")
        return False
    
    finally:
        await close_db()


async def test_openai():
    """Test OpenAI API"""
    print("\n🔍 Testing OpenAI API...")
    
    try:
        agent = AIAgent()
        
        response = await agent.generate_answer(
            user_message="Hello, test message",
            conversation_history=[],
            vector_context=None
        )
        
        print("✅ OpenAI API working")
        print(f"   Response length: {len(response)} chars")
        print(f"   Preview: {response[:100]}...")
        return True
    
    except Exception as e:
        print(f"❌ OpenAI API failed: {str(e)}")
        return False


async def test_bitrix():
    """Test Bitrix24 connection"""
    print("\n🔍 Testing Bitrix24 connection...")
    
    try:
        client = BitrixClient()
        
        # Note: This is a real API call, use with caution
        # For safer testing, just check URL format
        if not client.webhook_url:
            print("⚠️  Bitrix24 webhook URL not configured")
            return False
        
        if "bitrix24.com" not in client.webhook_url:
            print("⚠️  Invalid Bitrix24 webhook URL")
            return False
        
        print("✅ Bitrix24 webhook URL configured")
        print(f"   URL: {client.webhook_url[:50]}...")
        
        # Uncomment to test actual connection (creates test lead)
        # result = await client.create_lead(
        #     full_name="Test User",
        #     phone="+1234567890",
        #     selected_service="test",
        #     comment="Test lead from bot"
        # )
        # print(f"   Test lead result: {result}")
        
        return True
    
    except Exception as e:
        print(f"❌ Bitrix24 test failed: {str(e)}")
        return False


async def test_vector_store():
    """Test vector store"""
    print("\n🔍 Testing vector store...")
    
    try:
        await init_db()
        
        async for session in get_session():
            vector_store = VectorStore(session)
            
            # Count documents
            count = await vector_store.count_documents()
            print(f"✅ Vector store accessible")
            print(f"   Documents in store: {count}")
            
            if count > 0:
                # Test search
                results = await vector_store.search("test", limit=3)
                print(f"   Search test: found {len(results)} results")
            else:
                print("   ⚠️  No documents in store. Run 'load_documents.py' first.")
            
            return True
    
    except Exception as e:
        print(f"❌ Vector store test failed: {str(e)}")
        return False
    
    finally:
        await close_db()


async def test_all():
    """Run all tests"""
    setup_logging()
    
    print("="*60)
    print("MAXCAPITAL Bot - Component Tests")
    print("="*60)
    
    results = {
        "Database": await test_database(),
        "OpenAI API": await test_openai(),
        "Bitrix24": await test_bitrix(),
        "Vector Store": await test_vector_store()
    }
    
    print("\n" + "="*60)
    print("Test Results:")
    print("="*60)
    
    for component, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{component:20s} {status}")
    
    print("="*60)
    
    all_passed = all(results.values())
    
    if all_passed:
        print("🎉 All tests passed!")
        return 0
    else:
        print("⚠️  Some tests failed. Check configuration.")
        return 1


async def show_stats():
    """Show bot statistics"""
    print("\n📊 MAXCAPITAL Bot Statistics\n")
    
    try:
        await init_db()
        
        async for session in get_session():
            from src.models.user_memory import UserMemory
            from src.models.documents import Document
            from sqlalchemy import select, func
            
            # User count
            result = await session.execute(select(func.count(UserMemory.user_id)))
            user_count = result.scalar()
            
            # Document count
            doc_count = await Document.count_documents(session)
            
            # Users with complete profile
            result = await session.execute(
                select(func.count(UserMemory.user_id))
                .where(UserMemory.full_name.isnot(None))
                .where(UserMemory.phone.isnot(None))
            )
            complete_profiles = result.scalar()
            
            print(f"👥 Total users: {user_count}")
            print(f"✅ Complete profiles: {complete_profiles}")
            print(f"📚 Documents in vector store: {doc_count}")
            print()
    
    finally:
        await close_db()


def main():
    """Main CLI entry point"""
    if len(sys.argv) < 2:
        print("MAXCAPITAL Bot - Testing Tools")
        print("\nUsage:")
        print("  python scripts/test_bot.py all       - Run all tests")
        print("  python scripts/test_bot.py db        - Test database")
        print("  python scripts/test_bot.py openai    - Test OpenAI")
        print("  python scripts/test_bot.py bitrix    - Test Bitrix24")
        print("  python scripts/test_bot.py vector    - Test vector store")
        print("  python scripts/test_bot.py stats     - Show statistics")
        return 1
    
    command = sys.argv[1].lower()
    
    if command == "all":
        return asyncio.run(test_all())
    elif command == "db":
        return asyncio.run(test_database())
    elif command == "openai":
        return asyncio.run(test_openai())
    elif command == "bitrix":
        return asyncio.run(test_bitrix())
    elif command == "vector":
        return asyncio.run(test_vector_store())
    elif command == "stats":
        return asyncio.run(show_stats())
    else:
        print(f"❌ Unknown command: {command}")
        return 1


if __name__ == "__main__":
    sys.exit(main())


