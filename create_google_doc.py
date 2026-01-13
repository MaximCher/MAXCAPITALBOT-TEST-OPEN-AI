"""Create a Google Doc in a target Drive folder using a service account."""

import json
import os
import sys
from typing import Optional

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build


DOC_NAME = "TEST DOC FROM CODEX"
FOLDER_NAME = "ИИ ТЕСТЫ"
SCOPES = ["https://www.googleapis.com/auth/drive"]


def load_service_account_info() -> dict:
    raw = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not raw:
        raise RuntimeError("GOOGLE_SERVICE_ACCOUNT_JSON is not set.")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError("GOOGLE_SERVICE_ACCOUNT_JSON is not valid JSON.") from exc


def find_folder_id(service, folder_name: str) -> Optional[str]:
    query = (
        "mimeType = 'application/vnd.google-apps.folder' "
        "and trashed = false "
        f"and name = '{folder_name.replace("'", "\\'")}'"
    )
    response = (
        service.files()
        .list(q=query, fields="files(id, name)")
        .execute()
    )
    folders = response.get("files", [])
    if not folders:
        return None
    return folders[0]["id"]


def create_document(service, name: str, folder_id: str) -> str:
    metadata = {
        "name": name,
        "mimeType": "application/vnd.google-apps.document",
        "parents": [folder_id],
    }
    file = service.files().create(body=metadata, fields="id").execute()
    return file["id"]


def main() -> None:
    info = load_service_account_info()
    credentials = Credentials.from_service_account_info(info, scopes=SCOPES)
    service = build("drive", "v3", credentials=credentials, cache_discovery=False)

    folder_id = find_folder_id(service, FOLDER_NAME)
    if not folder_id:
        raise RuntimeError(f"Folder '{FOLDER_NAME}' not found in Drive.")

    doc_id = create_document(service, DOC_NAME, folder_id)
    print(f"https://docs.google.com/document/d/{doc_id}/edit")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001 - provide a clean error for scripts
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
