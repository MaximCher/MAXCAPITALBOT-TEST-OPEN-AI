import os
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple
from urllib.error import URLError
from urllib.request import urlopen

import requests
from flask import Flask, jsonify, request


SERVER_PORT = 8000


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
            app.logger.warning("Received non-JSON payload on /bitrix_hook")
            return jsonify({"error": "Expected JSON payload"}), 400

        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            app.logger.warning("Failed to parse JSON payload on /bitrix_hook: %r", payload)
            return jsonify({"error": "Invalid JSON payload"}), 400

        name = payload.get("name") or payload.get("NAME")
        if not name:
            return jsonify({"error": "Missing required field 'name'"}), 400

        phone = payload.get("phone") or payload.get("PHONE")
        email = payload.get("email") or payload.get("EMAIL")
        assigned = payload.get("assigned_id") or payload.get("ASSIGNED_BY_ID")
        comment = payload.get("comment") or payload.get("COMMENTS")

        config: BitrixConfig = app.config["BITRIX"]

        try:
            contact_id, status = upsert_contact(
                config,
                name=name,
                phone=phone,
                email=email,
                assigned_id=int(assigned) if assigned is not None else None,
                comment=comment,
            )
        except BitrixConfigurationError as exc:
            app.logger.error("Bitrix configuration error: %s", exc)
            return jsonify({"error": str(exc)}), 503
        except BitrixRequestError as exc:
            app.logger.exception("Bitrix request failed")
            return jsonify({"error": str(exc)}), 502

        message = payload.get("message") or payload.get("MESSAGE")
        dialog_id = payload.get("dialog_id") or payload.get("DIALOG_ID") or config.default_dialog

        chat_status = None
        if message:
            try:
                b24_im(config, dialog_id, message)
                chat_status = "sent"
            except BitrixConfigurationError as exc:
                app.logger.error("Bitrix chat configuration error: %s", exc)
                return jsonify({"error": str(exc)}), 503
            except BitrixRequestError as exc:
                app.logger.exception("Failed to send Bitrix chat message")
                return jsonify({"error": str(exc)}), 502

        response_body = {"contact_id": contact_id, "contact_status": status}
        if chat_status:
            response_body["chat_status"] = chat_status
            response_body["dialog_id"] = dialog_id

        app.logger.info("Processed webhook for contact %s (%s)", contact_id, status)
        return jsonify(response_body), 200

    @app.route("/public_url")
    def public_url():
        """Return the best-known public URL for the running service."""

        url = resolve_public_url()
        if not url:
            url = request.host_url.rstrip("/")
        return jsonify({"public_url": url}), 200

    return app


app = create_app()


if __name__ == "__main__":
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

    app.run(host="0.0.0.0", port=SERVER_PORT)
