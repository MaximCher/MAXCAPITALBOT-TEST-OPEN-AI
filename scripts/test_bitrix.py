"""
Test Bitrix24 lead creation
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.bitrix import BitrixClient
from src.logger import setup_logging


async def test_bitrix():
    """Test Bitrix24 lead creation"""
    
    setup_logging()
    
    print("\n" + "="*60)
    print("Testing Bitrix24 Lead Creation")
    print("="*60 + "\n")
    
    client = BitrixClient()
    
    print(f"Webhook URL: {client.webhook_url}\n")
    
    print("Creating test lead...")
    
    result = await client.create_lead(
        full_name="Тестов Тест",
        phone="+1234567890",
        selected_service="venture_capital",
        comment="Тестовый лид из бота. Интересуется венчурными инвестициями.",
        user_id=12345
    )
    
    print("\nResult:")
    print(f"  Success: {result.get('success')}")
    
    if result.get('success'):
        print(f"  Lead ID: {result.get('lead_id')}")
        print("\n✅ Bitrix24 lead created successfully!")
        print("\nCheck your Bitrix24 CRM for the new lead.")
    else:
        print(f"  Error: {result.get('error')}")
        print("\n❌ Lead creation failed!")
        print("\nPossible issues:")
        print("  1. Check webhook URL in .env")
        print("  2. Verify webhook permissions in Bitrix24")
        print("  3. Check if webhook is active")
    
    print("\n" + "="*60 + "\n")


if __name__ == "__main__":
    asyncio.run(test_bitrix())


