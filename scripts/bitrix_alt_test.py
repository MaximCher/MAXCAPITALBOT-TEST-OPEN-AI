"""
Alternative Bitrix24 test - put comment in TITLE
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.bitrix import BitrixClient
from src.config import SERVICES
import httpx


async def test_with_title():
    """Test with comment in TITLE field"""
    
    print("\n" + "="*60)
    print("Testing Alternative Approach: Comment in TITLE")
    print("="*60 + "\n")
    
    client = BitrixClient()
    
    # Prepare data with comment in title
    lead_data = {
        "fields": {
            "TITLE": "Лид из ТГ | Real Estate | Бюджет $500K, доход 8%+",
            "NAME": "Тест",
            "LAST_NAME": "Альтернатива",
            "PHONE": [{"VALUE": "+9999999999", "VALUE_TYPE": "WORK"}],
            "SOURCE_ID": "TELEGRAM",
            "STATUS_ID": "NEW",
            "OPENED": "Y",
            "COMMENTS": """Источник: Telegram бот MAXCAPITAL
Интересующая услуга: 🏛 Real Estate
Telegram ID: 12345

========================================
РЕЗЮМЕ ЗАПРОСА КЛИЕНТА:
========================================
Клиент интересуется инвестицией в недвижимость с бюджетом $500K.
Требования: доходность от 8% годовых.
Рекомендуется связаться в течение 24 часов."""
        }
    }
    
    print(f"Webhook URL: {client.webhook_url}\n")
    print("Creating lead with detailed comment...")
    print(f"\nTITLE: {lead_data['fields']['TITLE']}")
    print(f"\nCOMMENTS (first 100 chars):")
    print(lead_data['fields']['COMMENTS'][:100] + "...\n")
    
    async with httpx.AsyncClient(timeout=30.0) as http_client:
        response = await http_client.post(
            client.webhook_url,
            json=lead_data
        )
        
        result = response.json()
    
    if result.get('result'):
        print(f"✅ Lead created: ID = {result['result']}")
        print(f"\nCheck this lead in Bitrix24:")
        print(f"https://b24-qtrjoh.bitrix24.kz/crm/lead/details/{result['result']}/")
    else:
        print(f"❌ Error: {result}")
    
    print("\n" + "="*60 + "\n")


if __name__ == "__main__":
    asyncio.run(test_with_title())


