"""
MAXCAPITAL Bot - Bitrix24 Integration
Creates leads via Bitrix24 webhook
"""

from typing import Dict, Any, Optional
import httpx
import structlog

from src.config import settings, SERVICES

logger = structlog.get_logger()


class BitrixClient:
    """Bitrix24 CRM integration for lead creation"""
    
    def __init__(self):
        webhook_url = settings.bitrix24_webhook_url.strip()
        # Ensure URL ends with /crm.lead.add
        # Remove trailing slash if present
        webhook_url = webhook_url.rstrip('/')
        # Add method if not present
        if '/crm.lead.add' not in webhook_url:
            webhook_url = f"{webhook_url}/crm.lead.add"
        self.webhook_url = webhook_url
        self.timeout = 30.0
        logger.info("bitrix_client_initialized", webhook_url=self.webhook_url)
    
    async def create_lead(
        self,
        full_name: str,
        phone: str,
        selected_service: str,
        comment: Optional[str] = None,
        user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Create lead in Bitrix24 CRM
        
        Returns dict with:
        - success: bool
        - lead_id: int (if successful)
        - error: str (if failed)
        """
        try:
            # Parse name
            name_parts = full_name.strip().split()
            last_name = name_parts[0] if len(name_parts) > 0 else ""
            first_name = name_parts[1] if len(name_parts) > 1 else ""
            
            # Get service name (remove emojis for Bitrix24 compatibility)
            service_name_raw = SERVICES.get(selected_service, selected_service)
            # Remove emojis and extra spaces
            import re
            service_name = re.sub(r'[^\w\s\-()А-Яа-яA-Za-z]', '', service_name_raw).strip()
            
            # Format full comment first
            full_comment = self._format_comment(
                service_name=service_name,
                comment=comment,
                user_id=user_id
            )
            
            # Prepare lead data
            # Use minimal required fields first, then add optional ones
            lead_data = {
                "fields": {
                    "TITLE": f"Лид из Telegram бота - {service_name}",
                    "NAME": first_name if first_name else "",
                    "LAST_NAME": last_name if last_name else "",
                    "PHONE": [{"VALUE": phone, "VALUE_TYPE": "WORK"}],
                    "COMMENTS": full_comment
                }
            }
            
            # Add optional fields only if they exist in Bitrix24
            # SOURCE_ID and STATUS_ID may not be standard in all Bitrix24 instances
            # Try without them first, or use standard values
            # "STATUS_ID": "NEW" - may cause issues if status doesn't exist
            # "OPENED": "Y" - should be safe
            # "SOURCE_ID": "WEB" - use standard source instead of custom "TELEGRAM"
            
            logger.info(
                "creating_bitrix_lead",
                name=full_name,
                phone=phone,
                service=service_name,
                comment_length=len(full_comment),
                has_comment=bool(full_comment and full_comment.strip()),
                lead_data_fields=list(lead_data["fields"].keys())
            )
            
            # Send request to Bitrix24
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self.webhook_url,
                    json=lead_data
                )
                
                # Log response for debugging
                try:
                    result = response.json()
                except Exception:
                    result = {"error": f"Failed to parse response: {response.text[:200]}"}
                    logger.error("bitrix_response_parse_error", response_text=response.text[:500])
                
                if response.status_code != 200:
                    error_msg = result.get('error_description') or result.get('error') or response.text[:500]
                    logger.error(
                        "bitrix_api_error",
                        status_code=response.status_code,
                        error=error_msg,
                        full_response=result
                    )
                    response.raise_for_status()
            
            if result.get('result'):
                lead_id = result['result']
                logger.info(
                    "bitrix_lead_created",
                    lead_id=lead_id,
                    name=full_name,
                    service=service_name
                )
                
                # Note: Lead will be saved by the caller if session is provided
                # This is to avoid circular dependencies and session management issues
                
                return {
                    "success": True,
                    "lead_id": lead_id
                }
            else:
                error_msg = result.get('error_description', 'Unknown error')
                logger.error("bitrix_lead_failed", error=error_msg)
                
                return {
                    "success": False,
                    "error": error_msg
                }
        
        except httpx.HTTPError as e:
            logger.error("bitrix_http_error", error=str(e))
            return {
                "success": False,
                "error": f"HTTP error: {str(e)}"
            }
        
        except Exception as e:
            logger.error("bitrix_unexpected_error", error=str(e))
            return {
                "success": False,
                "error": f"Unexpected error: {str(e)}"
            }
    
    def _format_comment(
        self,
        service_name: str,
        comment: Optional[str] = None,
        user_id: Optional[int] = None
    ) -> str:
        """Format comment for Bitrix24 lead"""
        parts = [
            f"Источник: Telegram бот MAXCAPITAL",
            f"Интересующая услуга: {service_name}",
        ]
        
        if user_id:
            parts.append(f"Telegram ID: {user_id}")
        
        if comment and comment.strip():
            parts.append(f"\n{'='*40}")
            parts.append(f"РЕЗЮМЕ ЗАПРОСА КЛИЕНТА:")
            parts.append(f"{'='*40}")
            parts.append(comment)
        else:
            parts.append(f"\nКлиент выбрал услугу через Telegram бота и оставил контактные данные для связи.")
        
        return "\n".join(parts)
    
    async def test_connection(self) -> bool:
        """Test Bitrix24 webhook connection"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(self.webhook_url.replace('crm.lead.add', 'profile'))
                return response.status_code == 200
        except Exception as e:
            logger.error("bitrix_connection_test_failed", error=str(e))
            return False

