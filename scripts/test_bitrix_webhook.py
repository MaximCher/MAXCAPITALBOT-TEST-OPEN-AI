"""
Test Bitrix24 webhook with correct URL
"""
import asyncio
import sys
import httpx
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


async def test_webhook():
    """Test Bitrix24 webhook directly"""
    
    webhook_url = "https://chgroup.bitrix24.ru/rest/1/09szi5uuafhikfjb/crm.lead.add"
    
    print("\n" + "="*60)
    print("Testing Bitrix24 Webhook")
    print("="*60 + "\n")
    print(f"Webhook URL: {webhook_url}\n")
    
    # Test data - minimal required fields
    lead_data = {
        "fields": {
            "TITLE": "Тестовый лид из бота",
            "NAME": "Тест",
            "LAST_NAME": "Тестов",
            "PHONE": [{"VALUE": "+1234567890", "VALUE_TYPE": "WORK"}],
            "COMMENTS": "Тестовый лид для проверки вебхука"
        }
    }
    
    print("Sending request with data:")
    print(f"  TITLE: {lead_data['fields']['TITLE']}")
    print(f"  NAME: {lead_data['fields']['NAME']}")
    print(f"  LAST_NAME: {lead_data['fields']['LAST_NAME']}")
    print(f"  PHONE: {lead_data['fields']['PHONE']}")
    print()
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                webhook_url,
                json=lead_data
            )
            
            print(f"Response Status: {response.status_code}")
            print(f"Response Headers: {dict(response.headers)}\n")
            
            try:
                result = response.json()
                print("Response JSON:")
                import json
                print(json.dumps(result, indent=2, ensure_ascii=False))
                print()
                
                if result.get('result'):
                    lead_id = result['result']
                    print(f"✅ SUCCESS! Lead created with ID: {lead_id}")
                elif result.get('error') or result.get('error_description'):
                    error = result.get('error_description') or result.get('error', 'Unknown error')
                    print(f"❌ ERROR: {error}")
                    
                    # Check if it's a permission issue
                    if 'Access denied' in error or 'permission' in error.lower():
                        print("\n⚠️  This webhook may not have permission to create leads.")
                        print("   It might only have permission to create deals (crm.deal.add)")
                        print("   Check webhook permissions in Bitrix24 settings.")
                else:
                    print("❌ Unexpected response format")
                    
            except Exception as e:
                print(f"❌ Failed to parse JSON response: {e}")
                print(f"Response text: {response.text[:500]}")
                
    except httpx.HTTPError as e:
        print(f"❌ HTTP Error: {e}")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    print("\n" + "="*60 + "\n")


if __name__ == "__main__":
    asyncio.run(test_webhook())

