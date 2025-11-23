"""
Check specific lead in Bitrix24 to see if comments are saved
"""
import asyncio
import httpx
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import settings


async def check_lead(lead_id):
    """Get lead details from Bitrix24"""
    
    webhook_base = settings.bitrix24_webhook_url.replace('/crm.lead.add', '')
    url = f"{webhook_base}/crm.lead.get"
    
    print("\n" + "="*60)
    print(f"Checking Lead #{lead_id} in Bitrix24")
    print("="*60 + "\n")
    
    params = {"id": lead_id}
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(url, json=params)
        result = response.json()
    
    if result.get('result'):
        lead = result['result']
        
        print(f"📋 Lead Information:\n")
        print(f"  ID: {lead.get('ID')}")
        print(f"  Title: {lead.get('TITLE')}")
        print(f"  Name: {lead.get('NAME')} {lead.get('LAST_NAME')}")
        print(f"  Phone: {lead.get('PHONE')}")
        print(f"  Status: {lead.get('STATUS_ID')}")
        print(f"  Source: {lead.get('SOURCE_ID')}")
        print()
        
        print(f"💬 COMMENTS Field:")
        print("-" * 60)
        comments = lead.get('COMMENTS', '')
        if comments:
            print(comments)
        else:
            print("(empty)")
        print("-" * 60)
        print()
        
        # Save full lead data
        with open(f'lead_{lead_id}.json', 'w', encoding='utf-8') as f:
            json.dump(lead, f, ensure_ascii=False, indent=2)
        
        print(f"💾 Full lead data saved to: lead_{lead_id}.json")
        
        # Check if comments field exists and has value
        if comments and len(comments) > 10:
            print(f"\n✅ COMMENTS field has data ({len(comments)} chars)")
        else:
            print(f"\n⚠️  COMMENTS field is empty or very short")
            print(f"\n  Possible reasons:")
            print(f"    1. Bitrix24 didn't save the field")
            print(f"    2. Field is saved but shown in different place")
            print(f"    3. Need different field name")
    else:
        print(f"❌ Error: {result}")
    
    print("\n" + "="*60 + "\n")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python check_lead.py <lead_id>")
        print("Example: python check_lead.py 178")
        sys.exit(1)
    
    lead_id = sys.argv[1]
    asyncio.run(check_lead(lead_id))


