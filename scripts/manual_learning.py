#!/usr/bin/env python3
"""
MAXCAPITAL Bot - Manual Learning Script
Manually trigger self-learning from rated dialogs
"""

import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.self_learning import self_learning
from src.database import get_session
from src.logger import setup_logging
import structlog

logger = structlog.get_logger()


async def main():
    """Run manual self-learning"""
    setup_logging()
    
    logger.info("manual_learning_starting")
    
    try:
        # Get learning statistics first
        async for session in get_session():
            stats = await self_learning.get_learning_statistics(session)
            
            print("\n📊 Current Statistics:")
            print(f"Total ratings: {stats['total_ratings']}")
            print(f"Already learned: {stats['learned_dialogs']}")
            print(f"Pending to learn: {stats['pending_to_learn']}")
            print(f"Avg rating (30d): {stats['avg_rating_30d']}")
            print()
            
            break
        
        # Run learning
        result = await self_learning.learn_from_dialogs()
        
        logger.info(
            "manual_learning_completed",
            learned=result["learned"],
            errors=result["errors"]
        )
        
        print("\n✅ Self-learning completed!")
        print(f"🧠 Learned: {result['learned']} dialogs")
        print(f"❌ Errors: {result['errors']}")
        
    except Exception as e:
        logger.error("manual_learning_failed", error=str(e))
        print(f"\n❌ Learning failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())





