# MAXCAPITALBOT-TEST-OPEN-AI

A minimal Flask application that exposes a health endpoint and a Bitrix webhook receiver that can upsert Bitrix24 contacts and optionally post chat messages.

## Requirements

- Python 3.8+
- Flask (install with `pip install flask`)
- requests

## Running the server

```bash
python main.py
```

The server listens on `0.0.0.0:8000` and provides the following endpoints:

- `GET /` returns a simple status message.
- `POST /bitrix_hook` accepts JSON payloads, upserts Bitrix contacts via the REST API, and can send chat messages via the outgoing webhook. Requests without valid JSON receive a `400` response explaining the issue.
- `GET /public_url` returns the best-known public URL for the currently running process.

### Bitrix configuration

The application reads the following environment variables at startup:

- `BITRIX_WEBHOOK` – required for CRM operations (e.g., `https://<domain>/rest/<user>/<token>`).
- `BITRIX_OUT_HOOK` – required to send chat messages with `im.message.add`. If absent, chat messages are disabled.
- `B24_DEFAULT_DIALOG` – default chat ID used when the webhook payload does not include `dialog_id` (defaults to `chat1`).

The `/bitrix_hook` endpoint expects JSON objects with the following fields:

- `name` *(required)* – contact name.
- `phone`, `email` *(optional)* – used to look up existing contacts.
- `assigned_id` *(optional)* – Bitrix user ID that will own the contact.
- `comment` *(optional)* – stored in the contact comments field (truncated to 2000 characters).
- `message` *(optional)* – if present, sends a chat message using the configured outgoing webhook.
- `dialog_id` *(optional)* – chat ID to use when sending a message; falls back to `B24_DEFAULT_DIALOG`.

The endpoint responds with the contact ID and whether the record was created or updated. If a chat message is sent, the response also includes the dialog ID and message status.

### Public URL detection

On startup the application attempts to detect a publicly reachable URL. You can override this behaviour by setting one of the following environment variables before launching the server:

- `PUBLIC_URL` – the full URL (including scheme) that should be displayed.
- `PUBLIC_HOSTNAME` – a hostname that will be combined with the `PUBLIC_SCHEME` (defaults to `https`).

If automatic detection fails—common in restricted network environments—the server logs a warning and `/public_url` falls back to the host seen by the incoming request.
