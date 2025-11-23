"""
Check available fields in Bitrix24 for leads
"""
import asyncio
import httpx
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import settings


async def check_fields():
    """Get all available fields for leads in Bitrix24"""
    
    webhook_base = settings.bitrix24_webhook_url.replace('/crm.lead.add', '')
    url = f"{webhook_base}/crm.lead.fields"
    
    print("\n" + "="*60)
    print("Bitrix24 Lead Fields")
    print("="*60 + "\n")
    
    print(f"Requesting: {url}\n")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url)
        result = response.json()
    
    if result.get('result'):
        fields = result['result']
        
        print("📝 Available comment/description fields:\n")
        
        comment_fields = {
            k: v for k, v in fields.items()
            if 'comment' in k.lower() or 'description' in k.lower() or 'desc' in k.lower()
        }
        
        if comment_fields:
            for field_name, field_info in comment_fields.items():
                print(f"  • {field_name}")
                print(f"    Type: {field_info.get('type', 'unknown')}")
                print(f"    Title: {field_info.get('formLabel', field_info.get('listLabel', 'N/A'))}")
                print()
        else:
            print("  No comment fields found with 'comment' in name")
            print("\n  Checking for custom fields (UF_CRM_*):\n")
            
            uf_fields = {k: v for k, v in fields.items() if k.startswith('UF_CRM_')}
            for field_name, field_info in list(uf_fields.items())[:10]:
                print(f"  • {field_name}")
                print(f"    Title: {field_info.get('formLabel', field_info.get('listLabel', 'N/A'))}")
                print()
        
        print(f"\n📊 Total fields available: {len(fields)}")
        print(f"📊 Custom fields (UF_CRM_*): {len([k for k in fields.keys() if k.startswith('UF_CRM_')])}")
        
        # Save to file
        with open('bitrix_fields.json', 'w', encoding='utf-8') as f:
            json.dump(fields, f, ensure_ascii=False, indent=2)
        
        print(f"\n💾 Full fields list saved to: bitrix_fields.json")
    else:
        print(f"❌ Error: {result}")
    
    print("\n" + "="*60 + "\n")


if __name__ == "__main__":
    asyncio.run(check_fields())

