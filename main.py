"""
MAXCAPITAL Bot - Telegram bot with Bitrix24 and Google Drive integration.

This module provides:
- Flask server with /bitrix_hook endpoint
- Telegram bot that forwards messages to Bitrix24
- Intent detection and Google Drive file search
- Comprehensive logging to bot_events.log
"""

import os
import json
import logging
from datetime import datetime
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple
from urllib.error import URLError
from urllib.request import urlopen
from threading import Thread

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # python-dotenv not installed, skip .env loading
    pass

import requests
from flask import Flask, jsonify, request
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

from intent import detect_intent, detect_services
import gdrive_service
import knowledge_base
import statistics
import ai_consultant
import conversation_state
import db
import re


# Configuration
SERVER_PORT = 8000
LOG_FILE = "bot_events.log"

# Setup logging to file
file_handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
file_handler.setLevel(logging.INFO)
file_formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
file_handler.setFormatter(file_formatter)

# Setup console logging
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(file_formatter)

# Configure root logger
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
root_logger.addHandler(file_handler)
root_logger.addHandler(console_handler)

logger = logging.getLogger(__name__)


def extract_phone(text: str) -> Optional[str]:
    """Extract phone number from text."""
    if not text:
        return None
    
    # Patterns for phone numbers
    patterns = [
        r'\+?[1-9]\d{1,14}',  # International format
        r'\+?7\s?\(?\d{3}\)?\s?\d{3}[- ]?\d{2}[- ]?\d{2}',  # Russian format
        r'\+?7\d{10}',  # Russian format without spaces
        r'\d{3}[- ]?\d{3}[- ]?\d{2}[- ]?\d{2}',  # Local format
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, text)
        if matches:
            # Clean phone number
            phone = re.sub(r'[\s\-\(\)]', '', matches[0])
            if phone.startswith('8'):
                phone = '7' + phone[1:]
            if not phone.startswith('+'):
                if phone.startswith('7'):
                    phone = '+' + phone
                else:
                    phone = '+7' + phone
            return phone
    
    return None


def extract_name(text: str) -> Optional[Dict[str, str]]:
    """Extract first and last name from text."""
    if not text:
        return None
    
    # Try to find name patterns
    # Pattern: "Имя Фамилия" or "Фамилия Имя"
    name_patterns = [
        r'([А-ЯЁ][а-яё]+)\s+([А-ЯЁ][а-яё]+)',  # Russian names
        r'([A-Z][a-z]+)\s+([A-Z][a-z]+)',  # English names
    ]
    
    for pattern in name_patterns:
        matches = re.findall(pattern, text)
        if matches:
            first_match = matches[0]
            # Assume first is first name, second is last name
            return {
                "first_name": first_match[0],
                "last_name": first_match[1]
            }
    
    # Try single name
    single_name_pattern = r'([А-ЯЁ][а-яё]+|[A-Z][a-z]+)'
    matches = re.findall(single_name_pattern, text)
    if matches:
        return {
            "first_name": matches[0],
            "last_name": None
        }
    
    return None


class BitrixConfigurationError(RuntimeError):
    """Raised when the Bitrix configuration is incomplete."""


class BitrixRequestError(RuntimeError):
    """Raised when Bitrix reports an error or the request fails."""


@dataclass
class BitrixConfig:
    inbound_webhook: Optional[str]
    outbound_webhook: Optional[str]
    default_dialog: str

    @classmethod
    def from_env(cls) -> "BitrixConfig":
        return cls(
            inbound_webhook=_clean_url(os.environ.get("BITRIX_WEBHOOK")),
            outbound_webhook=_clean_url(os.environ.get("BITRIX_OUT_HOOK")),
            default_dialog=os.environ.get("B24_DEFAULT_DIALOG", "chat1"),
        )


def _clean_url(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    return value.rstrip("/")


def log_event(event_type: str, data: Dict[str, Any]) -> None:
    """Log event to bot_events.log"""
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "event_type": event_type,
        "data": data
    }
    logger.info(f"EVENT: {json.dumps(log_entry, ensure_ascii=False)}")


def determine_public_url(port: int) -> Optional[str]:
    """Attempt to determine a publicly reachable URL for the service."""

    env_url = os.environ.get("PUBLIC_URL")
    if env_url:
        return env_url.rstrip("/")

    env_host = os.environ.get("PUBLIC_HOSTNAME")
    if env_host:
        scheme = os.environ.get("PUBLIC_SCHEME", "https")
        return f"{scheme}://{env_host.rstrip('/')}"

    try:
        with urlopen("https://ifconfig.me/ip", timeout=5) as response:
            ip = response.read().decode("utf-8").strip()
    except (URLError, OSError, ValueError):
        return None

    if not ip:
        return None

    if ":" in ip:
        return f"http://[{ip}]:{port}"

    return f"http://{ip}:{port}"


def b24_request(config: BitrixConfig, method: str, payload: Dict) -> Any:
    """Call a Bitrix inbound webhook method and return the JSON payload."""

    if not config.inbound_webhook:
        raise BitrixConfigurationError(
            "BITRIX_WEBHOOK is not configured; cannot process CRM requests."
        )

    url = f"{config.inbound_webhook}/{method}.json"

    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as exc:
        raise BitrixRequestError(f"Failed to call Bitrix method '{method}': {exc}") from exc

    if isinstance(data, dict) and "error" in data:
        raise BitrixRequestError(
            f"Bitrix error {data['error']}: {data.get('error_description')}"
        )

    return data.get("result") if isinstance(data, dict) else data


def b24_im(config: BitrixConfig, dialog_id: str, text: str) -> None:
    """Send a message to Bitrix24 chat."""
    if not config.outbound_webhook:
        raise BitrixConfigurationError(
            "BITRIX_OUT_HOOK is not configured; cannot send chat messages."
        )

    url = f"{config.outbound_webhook}/im.message.add.json"
    payload = {"DIALOG_ID": str(dialog_id), "MESSAGE": text}
    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise BitrixRequestError(f"Failed to send chat message: {exc}") from exc


def find_contact_by_comm(config: BitrixConfig, phone: Optional[str], email: Optional[str]) -> Optional[int]:
    """Find contact by phone or email."""
    communications = []
    if phone:
        communications.append({"TYPE": "PHONE", "VALUE": phone})
    if email:
        communications.append({"TYPE": "EMAIL", "VALUE": email})

    if not communications:
        return None

    result = b24_request(
        config,
        "crm.duplicate.findbycomm",
        {"entity_type": "CONTACT", "COMMUNICATIONS": communications},
    )

    contact_ids = (result or {}).get("CONTACT") if isinstance(result, dict) else None
    if not contact_ids:
        return None

    return int(contact_ids[0])


def upsert_contact(
    config: BitrixConfig,
    name: str,
    phone: Optional[str] = None,
    email: Optional[str] = None,
    assigned_id: Optional[int] = None,
    comment: Optional[str] = None,
) -> Tuple[int, str]:
    """Create or update a contact in Bitrix24."""
    contact_id = find_contact_by_comm(config, phone, email)

    fields = {
        "NAME": name or "—",
        "PHONE": ([{"VALUE": phone, "VALUE_TYPE": "WORK"}] if phone else []),
        "EMAIL": ([{"VALUE": email, "VALUE_TYPE": "WORK"}] if email else []),
        "COMMENTS": (comment or "")[:2000],
    }

    params = {"REGISTER_SONET_EVENT": "Y"}

    if contact_id:
        b24_request(
            config,
            "crm.contact.update",
            {"id": contact_id, "fields": fields, "params": params},
        )
        return contact_id, "updated"

    if assigned_id is not None:
        fields["ASSIGNED_BY_ID"] = int(assigned_id)

    new_id = b24_request(
        config,
        "crm.contact.add",
        {"fields": fields, "params": params},
    )

    return int(new_id), "created"


def find_user_by_email(config: BitrixConfig, email: str) -> Optional[int]:
    """Find Bitrix24 user ID by email."""
    try:
        result = b24_request(
            config,
            "user.get",
            {"filter": {"EMAIL": email}}
        )
        if result and isinstance(result, list) and len(result) > 0:
            user_id = result[0].get("ID")
            if user_id:
                return int(user_id)
    except Exception as e:
        logger.error(f"Error finding user by email {email}: {e}")
    return None


def get_assigned_manager_id(config: BitrixConfig, intent: Optional[str] = None) -> Optional[int]:
    """
    Get assigned manager ID based on intent or default.
    
    Returns:
        Manager ID from environment or None
    """
    # First, try to get default manager by email
    default_manager_email = os.environ.get("B24_DEFAULT_MANAGER_EMAIL", "theroonekz@gmail.com")
    manager_id = find_user_by_email(config, default_manager_email)
    if manager_id:
        logger.info(f"Found default manager by email {default_manager_email}: {manager_id}")
        return manager_id
    
    # Fallback to ID-based assignment
    # Get manager ID from environment based on intent
    if intent:
        intent_manager = os.environ.get(f"B24_MANAGER_{intent.upper()}")
        if intent_manager:
            try:
                return int(intent_manager)
            except ValueError:
                pass
    
    # Default manager ID
    default_manager = os.environ.get("B24_DEFAULT_MANAGER_ID")
    if default_manager:
        try:
            return int(default_manager)
        except ValueError:
            pass
    
    return None


def create_lead(
    config: BitrixConfig,
    name: str,
    phone: Optional[str] = None,
    email: Optional[str] = None,
    product: Optional[str] = None,
    comment: Optional[str] = None,
    intent: Optional[str] = None,
) -> int:
    """Create a new lead in Bitrix CRM with assigned manager."""
    fields = {
        "TITLE": name or "—",
        "NAME": name or "—",
        "PHONE": ([{"VALUE": phone, "VALUE_TYPE": "WORK"}] if phone else []),
        "EMAIL": ([{"VALUE": email, "VALUE_TYPE": "WORK"}] if email else []),
        "COMMENTS": (comment or "")[:2000],
        "SOURCE_ID": "WEB",  # Source: Web/Bot
        "SOURCE_DESCRIPTION": "MAXCAPITAL Telegram Bot",
    }

    if product:
        fields["PRODUCT_ID"] = product
    
    # Assign manager based on intent
    assigned_manager = get_assigned_manager_id(config, intent)
    if assigned_manager:
        fields["ASSIGNED_BY_ID"] = assigned_manager
        logger.info(f"Assigning lead to manager ID: {assigned_manager} (intent: {intent})")
    else:
        logger.warning("No manager assigned to lead")

    params = {"REGISTER_SONET_EVENT": "Y"}

    lead_id = b24_request(
        config,
        "crm.lead.add",
        {"fields": fields, "params": params},
    )

    return int(lead_id)


def process_bitrix_hook(payload: Dict[str, Any], config: BitrixConfig, session_id: Optional[str] = None, create_lead_flag: bool = True) -> Dict[str, Any]:
    """
    Process Bitrix webhook payload and return response.
    
    Args:
        payload: Webhook payload
        config: Bitrix configuration
        session_id: Optional session ID to check if lead already created
        create_lead_flag: Whether to create lead (False if already created for session)
    """
    # Detect intent
    message_text = payload.get("message") or payload.get("comment") or ""
    detected_intent = detect_intent(message_text)
    payload["detected_intent"] = detected_intent
    
    log_event("intent_detected", {
        "intent": detected_intent,
        "message": message_text
    })

    # Extract fields
    name = payload.get("name") or payload.get("NAME")
    if not name:
        raise ValueError("Missing required field 'name'")

    phone = payload.get("phone") or payload.get("PHONE")
    email = payload.get("email") or payload.get("EMAIL")
    assigned = payload.get("assigned_id") or payload.get("ASSIGNED_BY_ID")
    comment = payload.get("comment") or payload.get("COMMENTS")
    product = payload.get("product") or payload.get("PRODUCT")

    # Upsert contact (always update contact info)
    contact_id = None
    status = None
    try:
        contact_id, status = upsert_contact(
            config,
            name=name,
            phone=phone,
            email=email,
            assigned_id=int(assigned) if assigned is not None else None,
            comment=comment,
        )
        log_event("contact_upserted", {
            "contact_id": contact_id,
            "status": status,
            "name": name
        })
    except BitrixConfigurationError as exc:
        logger.error(f"Bitrix configuration error: {exc}")
        # Don't raise, allow bot to continue
    except BitrixRequestError as exc:
        logger.error(f"Failed to upsert contact: {exc}")
        # Don't raise, allow bot to continue

    # Create lead only if:
    # 1. create_lead_flag is True (not already created for this session)
    # 2. AND (intent is detected OR it's first message - session_id is None means new session)
    lead_id = None
    # Create lead on first message or when intent is detected
    should_create_lead = create_lead_flag and (session_id is None or detected_intent is not None)
    
    if should_create_lead:
        try:
            if config.inbound_webhook:  # Only try if webhook is configured
                lead_id = create_lead(
                    config,
                    name=name,
                    phone=phone,
                    email=email,
                    product=product,
                    comment=comment,
                    intent=detected_intent,
                )
                log_event("lead_created", {
                    "lead_id": lead_id,
                    "contact_id": contact_id,
                    "name": name,
                    "intent": detected_intent,
                    "session_id": session_id
                })
        except BitrixConfigurationError as exc:
            logger.error(f"Bitrix configuration error: {exc}")
            # Don't raise, allow bot to continue
        except BitrixRequestError as exc:
            logger.error(f"Failed to create lead: {exc}")
            # Don't raise, allow bot to continue
    else:
        logger.info(f"Skipping lead creation - already exists for session {session_id} or no intent detected")

    # Get materials from knowledge base based on intent
    drive_files = []
    if detected_intent:
        try:
            # Get materials from knowledge base
            materials = knowledge_base.get_materials_by_intent(detected_intent, message_text)
            if materials:
                drive_files = materials
                logger.info(f"Found {len(drive_files)} materials for intent: {detected_intent}")
                log_event("materials_found", {
                    "intent": detected_intent,
                    "count": len(drive_files)
                })
        except Exception as exc:
            logger.exception("Failed to get materials from knowledge base")
            drive_files = []
    
    # Fallback: search in root folder if no materials found and intent is "documents"
    if not drive_files and detected_intent == "documents":
        try:
            search_query = name or message_text
            drive_files = gdrive_service.find_files_by_name(search_query)
            logger.info(f"Found {len(drive_files)} files in Google Drive for query: {search_query}")
            log_event("drive_files_found", {
                "query": search_query,
                "count": len(drive_files)
            })
        except Exception as exc:
            logger.exception("Failed to search Google Drive files")
            drive_files = []

    # Send message to Bitrix chat if provided
    message = payload.get("message") or payload.get("MESSAGE")
    dialog_id = payload.get("dialog_id") or payload.get("DIALOG_ID") or config.default_dialog

    chat_status = None
    if message:
        try:
            b24_im(config, dialog_id, message)
            chat_status = "sent"
        except (BitrixConfigurationError, BitrixRequestError) as exc:
            logger.error(f"Failed to send Bitrix chat message: {exc}")

    # Build response
    response_body = {
        "detected_intent": detected_intent
    }
    
    if contact_id is not None:
        response_body["contact_id"] = contact_id
        response_body["contact_status"] = status
    
    if lead_id is not None:
        response_body["lead_id"] = lead_id
    
    if chat_status:
        response_body["chat_status"] = chat_status
        response_body["dialog_id"] = dialog_id
    
    if detected_intent == "documents" and drive_files:
        response_body["drive_files"] = drive_files

    return response_body


def create_app(port: int = SERVER_PORT) -> Flask:
    """Create and configure the Flask application."""

    app = Flask(__name__)
    app.config["SERVER_PORT"] = port
    app.config.setdefault("_cached_public_url", None)
    app.config["BITRIX"] = BitrixConfig.from_env()

    def resolve_public_url() -> Optional[str]:
        cached = app.config.get("_cached_public_url")
        if cached is not None:
            return cached or None

        url = determine_public_url(app.config["SERVER_PORT"])
        if url:
            app.config["_cached_public_url"] = url
            return url

        app.config["_cached_public_url"] = ""
        return None

    @app.route("/")
    def home():
        """Return a simple status message for health checks."""
        return "Server is running 🚀", 200

    @app.route("/bitrix_hook", methods=["POST"])
    def bitrix_hook():
        """Upsert a Bitrix contact and optionally send a chat message."""
        if not request.is_json:
            logger.warning("Received non-JSON payload on /bitrix_hook")
            return jsonify({"error": "Expected JSON payload"}), 400

        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            logger.warning("Failed to parse JSON payload on /bitrix_hook: %r", payload)
            return jsonify({"error": "Invalid JSON payload"}), 400

        log_event("payload_received", payload)

        config: BitrixConfig = app.config["BITRIX"]

        try:
            response_body = process_bitrix_hook(payload, config)
            logger.info(f"Processed webhook successfully: {response_body}")
            return jsonify(response_body), 200
        except ValueError as exc:
            logger.error(f"Validation error: {exc}")
            return jsonify({"error": str(exc)}), 400
        except BitrixConfigurationError as exc:
            logger.error(f"Bitrix configuration error: {exc}")
            return jsonify({"error": str(exc)}), 503
        except BitrixRequestError as exc:
            logger.exception("Bitrix request failed")
            return jsonify({"error": str(exc)}), 502
        except Exception as exc:
            logger.exception("Unexpected error processing webhook")
            return jsonify({"error": "Internal server error"}), 500

    @app.route("/public_url")
    def public_url():
        """Return the best-known public URL for the running service."""
        url = resolve_public_url()
        if not url:
            url = request.host_url.rstrip("/")
        return jsonify({"public_url": url}), 200

    @app.route("/statistics")
    def get_statistics():
        """Get bot usage statistics."""
        stats_data = statistics.stats.get_statistics()
        return jsonify(stats_data), 200

    @app.route("/statistics/user/<int:user_id>")
    def get_user_statistics(user_id: int):
        """Get user journey statistics."""
        journey = statistics.stats.get_user_journey(user_id)
        if journey:
            return jsonify(journey), 200
        return jsonify({"error": "User not found"}), 404

    return app


# Telegram Bot Handlers
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command."""
    user = update.effective_user
    
    # Reset conversation state for new session
    conversation_state.conversation_state.reset_state(user.id)
    
    # Start statistics session
    session_id = statistics.stats.start_session(
        user.id,
        user.username,
        user.first_name,
        user.last_name
    )
    
    # Get AI greeting with services list
    greeting = (
        "Здравствуйте! 👋\n\n"
        "Я консультант MAXCAPITAL. Мы предоставляем следующие услуги:\n\n"
        "1. VENTURE CAPITAL (Венчурный капитал)\n"
        "2. HNWI Consultations (Консультации для частных лиц с крупным капиталом)\n"
        "3. REAL ESTATE (Недвижимость)\n"
        "4. CRYPTO (Криптовалюта)\n"
        "5. M&A (Слияния и поглощения)\n"
        "6. PRIVATE EQUITY (Частный акционерный капитал)\n"
        "7. Relocation Support (Поддержка при релокации)\n"
        "8. ЗАРУБЕЖНЫЕ БАНКОВСКИЕ КАРТЫ\n\n"
        "Какие услуги вас интересуют? Расскажите, пожалуйста, чем могу помочь?"
    )
    
    # Update conversation state
    conversation_state.conversation_state.update_state(
        user.id,
        state="greeting"
    )
    conversation_state.conversation_state.add_assistant_message(user.id, greeting)
    
    await update.message.reply_text(greeting)
    log_event("telegram_command", {
        "command": "start",
        "user_id": user.id,
        "username": user.username,
        "session_id": session_id
    })


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /stats command - show bot statistics."""
    user = update.effective_user
    
    # Get statistics from database
    stats_data = statistics.stats.get_statistics()
    
    # Format statistics message
    total_visitors = stats_data.get("total_visitors", 0)
    total_interested = stats_data.get("total_interested", 0)
    total_leads = stats_data.get("total_leads", 0)
    
    # Calculate percentages
    interested_percent = (total_interested / total_visitors * 100) if total_visitors > 0 else 0
    leads_percent = (total_leads / total_visitors * 100) if total_visitors > 0 else 0
    
    stats_message = (
        "📊 <b>СТАТИСТИКА БОТА MAXCAPITAL</b>\n\n"
        f"👥 Всего обратились к боту: <b>{total_visitors}</b>\n"
        f"🎯 Заинтересовались услугами: <b>{total_interested}</b> ({interested_percent:.1f}%)\n"
        f"📞 Создали лид (ждут звонка): <b>{total_leads}</b> ({leads_percent:.1f}%)\n\n"
    )
    
    # Add service distribution if available
    service_distribution = stats_data.get("service_distribution", {})
    if service_distribution:
        stats_message += "📋 <b>Популярные услуги:</b>\n"
        for service_code, service_info in list(service_distribution.items())[:5]:
            service_name = service_info.get("name", service_code)
            count = service_info.get("count", 0)
            stats_message += f"• {service_name}: {count}\n"
        stats_message += "\n"
    
    # Add daily stats for last 7 days
    daily_stats = stats_data.get("daily_stats", [])
    if daily_stats:
        stats_message += "📅 <b>За последние 7 дней:</b>\n"
        for day in daily_stats[:7]:
            date = day.get("date", "")
            visitors = day.get("visitors", 0)
            interested = day.get("interested", 0)
            leads = day.get("leads", 0)
            stats_message += f"{date}: {visitors} обращений, {interested} заинтересовались, {leads} лидов\n"
    
    await update.message.reply_text(stats_message, parse_mode="HTML")
    
    log_event("telegram_command", {
        "command": "stats",
        "user_id": user.id,
        "username": user.username
    })


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming Telegram messages with AI consultation."""
    user = update.effective_user
    message_text = update.message.text
    
    # Get or create session for statistics
    session_id = statistics.stats.get_session(user.id)
    if not session_id:
        session_id = statistics.stats.start_session(
            user.id,
            user.username,
            user.first_name,
            user.last_name
        )
    
    # Get conversation state
    conv_state = conversation_state.conversation_state.get_state(user.id)
    current_state = conv_state["state"]
    
    log_event("telegram_message_received", {
        "user_id": user.id,
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "message": message_text,
        "session_id": session_id,
        "conversation_state": current_state
    })

    try:
        # Detect intent and services
        detected_intent = detect_intent(message_text)
        detected_services_list = detect_services(message_text)
        
        # Update conversation state with detected services
        if detected_services_list:
            conversation_state.conversation_state.update_state(
                user.id,
                detected_services=detected_services_list
            )
            # Update session status to "interested" if services detected
            if db.database.is_available() and session_id in statistics.stats.stats["sessions"]:
                db_session_id = statistics.stats.stats["sessions"][session_id].get("db_session_id")
                if db_session_id:
                    try:
                        db.database.update_session(
                            session_id=db_session_id,
                            status="interested"
                        )
                    except Exception as e:
                        logger.error(f"Error updating session status to interested: {e}")
            
            # Add to selected services if user confirms interest
            conv_state = conversation_state.conversation_state.get_state(user.id)
            if conv_state.get("confirmed_intent"):
                conversation_state.conversation_state.update_state(
                    user.id,
                    selected_services=detected_services_list
                )
        
        # Handle data collection state
        collected_info = conv_state.get("collected_info", {})
        collecting_data = current_state == "collecting_data"
        
        # Extract phone and name - try to extract from ANY message if we're collecting data
        # or if we don't have phone yet
        if collecting_data or not collected_info.get("phone"):
            phone = extract_phone(message_text)
            name_data = extract_name(message_text)
            
            if phone:
                collected_info["phone"] = phone
                logger.info(f"Extracted phone: {phone}")
            if name_data:
                if name_data.get("first_name"):
                    collected_info["first_name"] = name_data["first_name"]
                if name_data.get("last_name"):
                    collected_info["last_name"] = name_data["last_name"]
                logger.info(f"Extracted name: {name_data}")
            
            # Update collected info if we found something
            if phone or name_data:
                conversation_state.conversation_state.update_state(
                    user.id,
                    info=collected_info
                )
                conv_state = conversation_state.conversation_state.get_state(user.id)
                collected_info = conv_state.get("collected_info", {})
                logger.info(f"Updated collected info: {collected_info}")
        
        # Also try to extract phone/name from current message even if not in collecting_data state
        # This ensures we capture data whenever user provides it
        if not collected_info.get("phone"):
            phone = extract_phone(message_text)
            if phone:
                collected_info["phone"] = phone
                logger.info(f"Extracted phone from message: {phone}")
                conversation_state.conversation_state.update_state(user.id, info=collected_info)
        
        if not collected_info.get("first_name") and not collected_info.get("last_name"):
            name_data = extract_name(message_text)
            if name_data:
                if name_data.get("first_name"):
                    collected_info["first_name"] = name_data["first_name"]
                if name_data.get("last_name"):
                    collected_info["last_name"] = name_data["last_name"]
                logger.info(f"Extracted name from message: {name_data}")
                conversation_state.conversation_state.update_state(user.id, info=collected_info)
        
        # Update conversation state (this adds user message to history)
        conversation_state.conversation_state.update_state(
            user.id,
            message=message_text,
            intent=detected_intent if detected_intent else conv_state.get("detected_intent")
        )
        
        # Refresh conv_state after update to get latest history
        conv_state = conversation_state.conversation_state.get_state(user.id)
        
        # Update statistics
        statistics.stats.add_message(session_id, message_text, detected_intent, detected_services_list)
        
        # Get database session ID for loading history from DB
        db_session_id = None
        if db.database.is_available() and session_id in statistics.stats.stats["sessions"]:
            db_session_id = statistics.stats.stats["sessions"][session_id].get("db_session_id")
        
        # Get conversation history for AI (from DB if available)
        history = conversation_state.conversation_state.get_conversation_history(user.id, db_session_id=db_session_id)
        
        # Prepare context for AI
        ai_context = {
            "detected_intent": detected_intent or conv_state.get("detected_intent"),
            "detected_services": detected_services_list or conv_state.get("detected_services", []),
            "selected_services": conv_state.get("selected_services", []),
            "current_state": current_state,
            "confirmed_intent": conv_state.get("confirmed_intent", False),
            "collecting_data": collecting_data
        }
        
        # Get materials if intent detected
        drive_files = []
        if detected_intent:
            try:
                materials = knowledge_base.get_materials_by_intent(detected_intent, message_text)
                if materials:
                    drive_files = materials
                    ai_context["available_materials"] = materials
            except Exception:
                pass
        
        # Get AI response
        ai_response = ai_consultant.ai_consultant.get_response(
            message_text,
            history,
            ai_context
        )
        
        # Check if user confirmed intention
        confirmed = False
        intent_to_confirm = detected_intent or conv_state.get("detected_intent")
        has_services = len(detected_services_list) > 0 or len(conv_state.get("selected_services", [])) > 0
        
        if (intent_to_confirm or has_services) and current_state in ["consulting", "greeting"]:
            confirmed = ai_consultant.ai_consultant.check_confirmation(message_text, history)
            if confirmed:
                conversation_state.conversation_state.update_state(
                    user.id,
                    state="consulting",
                    confirmed=True,
                    selected_services=detected_services_list if detected_services_list else conv_state.get("selected_services", [])
                )
                
                # Update session status to "interested" in database
                if db.database.is_available() and session_id in statistics.stats.stats["sessions"]:
                    db_session_id = statistics.stats.stats["sessions"][session_id].get("db_session_id")
                    if db_session_id:
                        try:
                            db.database.update_session(
                                session_id=db_session_id,
                                status="interested"
                            )
                        except Exception as e:
                            logger.error(f"Error updating session status to interested: {e}")
                
                # Move to collecting data if not already collected
                if not conversation_state.conversation_state.has_collected_all_data(user.id):
                    conversation_state.conversation_state.update_state(user.id, state="collecting_data")
                    ai_response += (
                        "\n\n📝 Отлично! Для создания заявки мне нужна дополнительная информация:\n"
                        "• Ваше ФИО (Фамилия и Имя)\n"
                        "• Номер телефона\n\n"
                        "Пожалуйста, предоставьте эти данные."
                    )
        
        # Refresh conv_state AFTER all updates to get latest data
        conv_state = conversation_state.conversation_state.get_state(user.id)
        collected_info = conv_state.get("collected_info", {})
        
        # Check if we have all data and can create lead
        # Check AFTER extracting phone/name from current message
        should_create_lead = conversation_state.conversation_state.is_ready_for_lead(user.id, telegram_user=user)
        
        logger.info(f"=== LEAD CREATION CHECK ===")
        logger.info(f"Should create lead: {should_create_lead}")
        logger.info(f"Collected info: {collected_info}")
        logger.info(f"Phone: {collected_info.get('phone')}")
        logger.info(f"State: {conv_state.get('state')}")
        logger.info(f"Confirmed: {conv_state.get('confirmed_intent')}")
        logger.info(f"Services: selected={len(conv_state.get('selected_services', []))}, detected={len(conv_state.get('detected_services', []))}")
        logger.info(f"Intent: {conv_state.get('detected_intent')}")
        
        # Save assistant response to conversation history BEFORE checking for lead creation
        # This ensures the last bot message is in history
        conversation_state.conversation_state.add_assistant_message(user.id, ai_response)
        
        # Save assistant message to database
        if db_session_id:
            try:
                db.database.add_message(
                    session_id=db_session_id,
                    message_text=ai_response,
                    message_type="assistant",
                    detected_intent=None,
                    detected_services=None
                )
            except Exception as e:
                logger.error(f"Error saving assistant message to database: {e}")
        
        # Create contact and lead if ready
        contact_id = None
        lead_id = None
        if should_create_lead:
            # Check if lead already exists for this session (only when trying to create)
            existing_lead_id = None
            if db_session_id:
                try:
                    existing_lead_id = db.database.get_session_lead_id(db_session_id)
                except Exception as e:
                    logger.error(f"Error checking existing lead: {e}")
            
            # Also check in statistics JSON
            if not existing_lead_id and session_id in statistics.stats.stats["sessions"]:
                existing_lead_id = statistics.stats.stats["sessions"][session_id].get("lead_id")
            
            # Only create lead if it doesn't exist yet
            if existing_lead_id:
                logger.info(f"Lead already exists for this session (ID: {existing_lead_id}), skipping creation")
                # Don't block conversation - just skip lead creation and continue dialog
            else:
                try:
                    config = app.config["BITRIX"]
                    first_name = collected_info.get("first_name") or user.first_name or ""
                    last_name = collected_info.get("last_name") or user.last_name or ""
                    phone = collected_info.get("phone")
                    
                    name = f"{first_name} {last_name}".strip() or user.username or f"User_{user.id}"
                    
                    # Get services info for comment
                    selected_services = conv_state.get("selected_services", [])
                    detected_services = conv_state.get("detected_services", [])
                    all_services = selected_services if selected_services else detected_services
                    
                    services_list = []
                    if all_services:
                        for service in all_services:
                            service_name = service.get("name", service.get("code", ""))
                            services_list.append(f"• {service_name}")
                        services_text = "\n".join(services_list)
                    else:
                        services_text = "Не указаны"
                    
                    # Build summary comment for Bitrix24 (brief, one paragraph)
                    # Extract key information from conversation
                    full_state = conversation_state.conversation_state.get_state(user.id)
                    history = full_state.get("conversation_history", [])
                    
                    # Extract user's key messages and interests
                    user_messages = []
                    key_info = []
                    
                    for msg in history:
                        role = msg.get("role", "")
                        content = msg.get("content", "")
                        if role == "user" and content:
                            user_messages.append(content)
                        elif role == "assistant" and content:
                            # Extract questions bot asked to understand what client wants
                            if "?" in content or "какую" in content.lower() or "какой" in content.lower():
                                key_info.append(content[:100])
                    
                    # Build services summary
                    services_summary = ", ".join([s.get("name", s.get("code", "")).split("(")[0].strip() for s in all_services]) if all_services else "не указаны"
                    
                    # Build brief summary
                    summary_parts = []
                    summary_parts.append(f"Клиент интересуется услугами: {services_summary}.")
                    
                    # Add key user messages (what client wants)
                    if user_messages:
                        # Get last few user messages that contain actual requests
                        relevant_messages = []
                        for msg in user_messages[-5:]:  # Last 5 user messages
                            if len(msg) > 10 and not msg.lower().startswith(("да", "нет", "хорошо", "ок")):
                                relevant_messages.append(msg[:150])
                        
                        if relevant_messages:
                            client_wants = " ".join(relevant_messages[:2])  # First 2 relevant messages
                            summary_parts.append(f"Клиент сообщил: {client_wants}.")
                    
                    # Add intent if available
                    intent = conv_state.get('detected_intent')
                    if intent:
                        intent_names = {
                            "invest": "инвестиции",
                            "documents": "документы",
                            "consult": "консультация",
                            "support": "поддержка"
                        }
                        intent_ru = intent_names.get(intent, intent)
                        summary_parts.append(f"Тип запроса: {intent_ru}.")
                    
                    # Join summary into one paragraph
                    summary = " ".join(summary_parts)
                    
                    # Build comment with HTML line breaks for Bitrix24
                    comment = f"<b>Краткая информация о клиенте:</b><br><br>{summary}"
                    
                    logger.info(f"Summary comment length: {len(comment)}")
                    logger.info(f"Summary: {summary}")
                    
                    # Truncate if too long (Bitrix24 limit is 2000 chars)
                    if len(comment) > 2000:
                        comment = comment[:1997] + "..."
                    
                    logger.info(f"Final comment length: {len(comment)}")
                    logger.info(f"Comment that will be sent to Bitrix24:\n{comment}")
                    
                    # Create contact
                    try:
                        contact_id, status = upsert_contact(
                            config,
                            name=name,
                            phone=phone,
                            email=None,
                            comment=comment
                        )
                    except Exception as e:
                        logger.error(f"Failed to create contact: {e}")
                    
                    # Create lead - MUST create if we reached this point
                    service_codes = [s.get("code") for s in all_services] if all_services else None
                    
                    # Create lead title with service info
                    lead_title = name
                    if all_services:
                        # Add first service to title if available
                        first_service_name = all_services[0].get("name", "").split("(")[0].strip()
                        if first_service_name:
                            lead_title = f"{name} - {first_service_name}"
                    
                    # Log comment before sending to Bitrix24
                    logger.info(f"=== CREATING LEAD ===")
                    logger.info(f"Config inbound_webhook exists: {bool(config.inbound_webhook)}")
                    logger.info(f"Name: {name}")
                    logger.info(f"Lead title: {lead_title}")
                    logger.info(f"Phone: {phone}")
                    logger.info(f"Services: {service_codes}")
                    logger.info(f"Comment length: {len(comment)}")
                    logger.info(f"Comment content:\n{comment}")
                    
                    if not config.inbound_webhook:
                        logger.error("❌ CANNOT CREATE LEAD: inbound_webhook is not configured!")
                        ai_response += "\n\n⚠️ Произошла ошибка конфигурации. Пожалуйста, обратитесь к администратору."
                    elif not phone:
                        logger.error(f"❌ CANNOT CREATE LEAD: phone is missing. Collected info: {collected_info}")
                        ai_response += "\n\n⚠️ Для создания заявки необходим номер телефона. Пожалуйста, предоставьте его."
                    else:
                        try:
                            lead_id = create_lead(
                                config,
                                name=lead_title,
                                phone=phone,
                                email=None,
                                comment=comment,
                                intent=conv_state.get("detected_intent")
                            )
                            
                            if lead_id:
                                logger.info(f"✅ Lead created successfully with ID: {lead_id}")
                                
                                # Mark as lead in statistics
                                statistics.stats.convert_to_lead(
                                    session_id, 
                                    lead_id, 
                                    contact_id,
                                    services_interested=service_codes
                                )
                                
                                # Update database session
                                if db.database.is_available() and session_id in statistics.stats.stats["sessions"]:
                                    db_session_id = statistics.stats.stats["sessions"][session_id].get("db_session_id")
                                    if db_session_id:
                                        try:
                                            db.database.update_session(
                                                session_id=db_session_id,
                                                status="converted_to_lead",
                                                services_interested=service_codes,
                                                lead_id=lead_id,
                                                contact_id=contact_id
                                            )
                                        except Exception as e:
                                            logger.error(f"Error updating database session: {e}")
                                
                                # Update conversation state
                                conversation_state.conversation_state.update_state(
                                    user.id,
                                    state="completed"
                                )
                                
                                # Replace AI response with confirmation message
                                ai_response = (
                                    "✅ Отлично! Я создал заявку для вас. Наш менеджер свяжется с вами в ближайшее время.\n\n"
                                    f"📋 Номер заявки: {lead_id}\n\n"
                                    "Спасибо за обращение в MAXCAPITAL!"
                                )
                                
                                # Update assistant message in history
                                conversation_state.conversation_state.add_assistant_message(user.id, ai_response)
                                
                                # Save updated assistant message to database
                                if db_session_id:
                                    try:
                                        db.database.add_message(
                                            session_id=db_session_id,
                                            message_text=ai_response,
                                            message_type="assistant",
                                            detected_intent=None,
                                            detected_services=None
                                        )
                                    except Exception as e:
                                        logger.error(f"Error saving updated assistant message to database: {e}")
                                
                                log_event("lead_created_after_confirmation", {
                                    "user_id": user.id,
                                    "lead_id": lead_id,
                                    "contact_id": contact_id,
                                    "intent": conv_state.get("detected_intent"),
                                    "services": service_codes,
                                    "session_id": session_id
                                })
                            else:
                                logger.error("❌ ERROR: create_lead returned None or 0! Lead may not have been created in Bitrix24!")
                                ai_response += "\n\n⚠️ Произошла ошибка при создании заявки. Попробуйте позже."
                                raise Exception("create_lead returned invalid ID")
                        except Exception as e:
                            logger.error(f"❌ ERROR creating lead: {e}", exc_info=True)
                            ai_response += "\n\n⚠️ Произошла ошибка при создании заявки. Попробуйте позже."
                            raise  # Re-raise to be caught by outer except
                except Exception as e:
                    logger.exception("Error creating contact/lead")
        
        # Update conversation state based on response
        if (detected_intent or detected_services_list) and not conv_state.get("confirmed_intent"):
            if current_state == "greeting":
                # Move to consulting when intent/services detected
                conversation_state.conversation_state.update_state(user.id, state="consulting")
        
        # Add materials to response if available
        if drive_files and detected_intent:
            files_text = knowledge_base.format_files_for_telegram(drive_files)
            ai_response += f"\n\n{files_text}"
        
        # Note: Assistant response is saved earlier, before lead creation check
        # This ensures all messages are in history when creating lead
        
        # Send response to user
        await update.message.reply_text(ai_response, parse_mode="Markdown")
        
        log_event("telegram_message_sent", {
            "user_id": user.id,
            "response": ai_response,
            "session_id": session_id,
            "detected_intent": detected_intent,
            "detected_services": [s.get("code") for s in detected_services_list],
            "confirmed": confirmed,
            "lead_created": lead_id is not None
        })
        
    except Exception as exc:
        logger.exception("Error processing Telegram message")
        error_msg = (
            "Извините, произошла ошибка при обработке вашего сообщения.\n\n"
            "Попробуйте переформулировать вопрос или обратитесь позже."
        )
        await update.message.reply_text(error_msg)
        log_event("telegram_error", {
            "user_id": user.id,
            "error": str(exc),
            "session_id": session_id
        })


def run_telegram_bot():
    """Run Telegram bot in a separate thread."""
    import asyncio
    
    token = os.environ.get("TELEGRAM_TOKEN")
    if not token:
        logger.warning("TELEGRAM_TOKEN not set, Telegram bot will not start")
        return

    async def post_init(app: Application) -> None:
        logger.info("Telegram bot started successfully")

    async def main():
        """Main async function to run the bot."""
        application = Application.builder().token(token).post_init(post_init).build()

        # Add handlers
        application.add_handler(CommandHandler("start", start_command))
        application.add_handler(CommandHandler("stats", stats_command))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

        # Initialize and start polling
        await application.initialize()
        await application.start()
        await application.updater.start_polling(allowed_updates=Update.ALL_TYPES)
        
        logger.info("Telegram bot started successfully")
        
        # Keep running until stopped
        try:
            await asyncio.Event().wait()  # Wait indefinitely
        except asyncio.CancelledError:
            pass
        finally:
            await application.stop()
            await application.shutdown()

    # Create new event loop for this thread
    if os.name == 'nt':  # Windows
        loop = asyncio.ProactorEventLoop()
    else:
        loop = asyncio.new_event_loop()
    
    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        logger.info("Telegram bot stopped by user")
    except Exception as e:
        logger.exception(f"Error in Telegram bot thread: {e}")
    finally:
        try:
            # Cancel all pending tasks
            pending = [task for task in asyncio.all_tasks(loop) if not task.done()]
            for task in pending:
                task.cancel()
            if pending:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        except Exception:
            pass
        finally:
            loop.close()


# Initialize Flask app
app = create_app()


if __name__ == "__main__":
    # Determine public URL
    discovered_url = app.config.get("_cached_public_url")
    if not discovered_url:
        discovered_url = determine_public_url(SERVER_PORT)
        if discovered_url:
            app.config["_cached_public_url"] = discovered_url
        else:
            app.config["_cached_public_url"] = ""

    if discovered_url:
        print(f"🌐 Public URL: {discovered_url}")
    else:
        print("⚠️  Unable to determine the public URL automatically.")

    # Start Telegram bot in a separate thread
    bot_thread = Thread(target=run_telegram_bot, daemon=True)
    bot_thread.start()

    # Start Flask server
    logger.info(f"Starting Flask server on 0.0.0.0:{SERVER_PORT}")
    app.run(host="0.0.0.0", port=SERVER_PORT, debug=False)
