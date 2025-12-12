#!/usr/bin/env python3
"""
MAXCAPITAL Bot - Manual Drive Sync Script
Manually trigger Google Drive sync
"""

import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.auto_sync_drive import drive_sync
from src.logger import setup_logging
import structlog

logger = structlog.get_logger()


async def main():
    """Run manual drive sync"""
    setup_logging()
    
    logger.info("manual_drive_sync_starting")
    
    try:
        stats = await drive_sync.run_sync()
        
        logger.info(
            "manual_drive_sync_completed",
            synced=stats["synced"],
            skipped=stats["skipped"],
            errors=stats["errors"]
        )
        
        print("\n✅ Drive sync completed!")
        print(f"📥 Synced: {stats['synced']}")
        print(f"⏭️  Skipped: {stats['skipped']}")
        print(f"❌ Errors: {stats['errors']}")
        
    except Exception as e:
        logger.error("manual_sync_failed", error=str(e))
        print(f"\n❌ Sync failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())





