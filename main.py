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

from intent import detect_intent
import gdrive_service
import knowledge_base
import statistics
import ai_consultant
import conversation_state


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


def get_assigned_manager_id(intent: Optional[str] = None) -> Optional[int]:
    """
    Get assigned manager ID based on intent or round-robin.
    
    Returns:
        Manager ID from environment or None
    """
    # Get manager ID from environment based on intent
    if intent:
        intent_manager = os.environ.get(f"B24_MANAGER_{intent.upper()}")
        if intent_manager:
            try:
                return int(intent_manager)
            except ValueError:
                pass
    
    # Default manager or round-robin
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
    assigned_manager = get_assigned_manager_id(intent)
    if assigned_manager:
        fields["ASSIGNED_BY_ID"] = assigned_manager
        logger.info(f"Assigning lead to manager ID: {assigned_manager} (intent: {intent})")

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
        user.first_name
    )
    
    # Get AI greeting
    greeting = (
        "Здравствуйте! 👋\n\n"
        "Я консультант MAXCAPITAL. Помогу вам с:\n"
        "• Инвестиционными продуктами\n"
        "• Документами и презентациями\n"
        "• Консультациями\n"
        "• Поддержкой\n\n"
        "Расскажите, пожалуйста, чем могу помочь?"
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
            user.first_name
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
        # Detect intent
        detected_intent = detect_intent(message_text)
        
        # Update conversation state
        conversation_state.conversation_state.update_state(
            user.id,
            message=message_text,
            intent=detected_intent if detected_intent else conv_state.get("detected_intent")
        )
        
        # Update statistics
        statistics.stats.add_message(session_id, message_text, detected_intent)
        
        # Get conversation history for AI
        history = conversation_state.conversation_state.get_conversation_history(user.id)
        
        # Prepare context for AI
        ai_context = {
            "detected_intent": detected_intent or conv_state.get("detected_intent"),
            "current_state": current_state,
            "confirmed_intent": conv_state.get("confirmed_intent", False)
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
        
        if intent_to_confirm:
            # Check confirmation if we're in consulting phase or if intent just detected
            if current_state in ["consulting", "confirming", "greeting"]:
                confirmed = ai_consultant.ai_consultant.check_confirmation(message_text, history)
                if confirmed:
                    conversation_state.conversation_state.update_state(
                        user.id,
                        state="confirming",
                        confirmed=True
                    )
        
        # Check if ready to create lead (after confirmation)
        should_create_lead = conversation_state.conversation_state.is_ready_for_lead(user.id)
        
        # Create contact and lead if confirmed
        contact_id = None
        lead_id = None
        if should_create_lead:
            try:
                config = app.config["BITRIX"]
                name = f"{user.first_name or ''} {user.last_name or ''}".strip() or user.username or f"User_{user.id}"
                
                # Create contact
                try:
                    contact_id, status = upsert_contact(
                        config,
                        name=name,
                        phone=None,
                        email=None,
                        comment=f"Консультация через бота. Intent: {conv_state.get('detected_intent')}"
                    )
                except Exception as e:
                    logger.error(f"Failed to create contact: {e}")
                
                # Create lead
                try:
                    if config.inbound_webhook:
                        lead_id = create_lead(
                            config,
                            name=name,
                            phone=None,
                            email=None,
                            comment=f"Консультация через бота.\nIntent: {conv_state.get('detected_intent')}.\n\nПоследние сообщения:\n{message_text[:500]}",
                            intent=conv_state.get("detected_intent")
                        )
                        
                        # Mark as lead in statistics
                        statistics.stats.convert_to_lead(session_id, lead_id, contact_id)
                        
                        # Update conversation state
                        conversation_state.conversation_state.update_state(
                            user.id,
                            state="completed"
                        )
                        
                        # Add confirmation message
                        ai_response += f"\n\n✅ Отлично! Я создал заявку для вас. Наш менеджер свяжется с вами в ближайшее время."
                        if lead_id:
                            ai_response += f"\n\n📋 Номер заявки: {lead_id}"
                        
                        log_event("lead_created_after_confirmation", {
                            "user_id": user.id,
                            "lead_id": lead_id,
                            "contact_id": contact_id,
                            "intent": conv_state.get("detected_intent"),
                            "session_id": session_id
                        })
                except Exception as e:
                    logger.error(f"Failed to create lead: {e}")
                    ai_response += "\n\n⚠️ Произошла ошибка при создании заявки. Попробуйте позже."
            except Exception as e:
                logger.exception("Error creating contact/lead")
        
        # Update conversation state based on response
        if detected_intent and not conv_state.get("confirmed_intent"):
            if current_state == "greeting":
                # Move to consulting when intent detected
                conversation_state.conversation_state.update_state(user.id, state="consulting")
        elif confirmed and current_state != "completed":
            # Move to confirming when user confirms
            conversation_state.conversation_state.update_state(user.id, state="confirming")
        
        # Add materials to response if available
        if drive_files and detected_intent:
            files_text = knowledge_base.format_files_for_telegram(drive_files)
            ai_response += f"\n\n{files_text}"
        
        # Save assistant response to conversation history
        conversation_state.conversation_state.add_assistant_message(user.id, ai_response)
        
        # Send response to user
        await update.message.reply_text(ai_response, parse_mode="Markdown")
        
        log_event("telegram_message_sent", {
            "user_id": user.id,
            "response": ai_response,
            "session_id": session_id,
            "detected_intent": detected_intent,
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
    token = os.environ.get("TELEGRAM_TOKEN")
    if not token:
        logger.warning("TELEGRAM_TOKEN not set, Telegram bot will not start")
        return

    async def post_init(app: Application) -> None:
        logger.info("Telegram bot started successfully")

    application = Application.builder().token(token).post_init(post_init).build()

    # Add handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Run bot
    logger.info("Starting Telegram bot...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


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
