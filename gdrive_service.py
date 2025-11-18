"""
Google Drive service module for working with Google Drive API via service account.

This module provides functions to interact with Google Drive using service account credentials.
"""

import os
from typing import List, Dict, Optional, Any

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from googleapiclient.errors import HttpError


def get_drive_service():
    """
    Create and return a Google Drive service object using service account credentials.

    Returns:
        googleapiclient.discovery.Resource: Google Drive service object.

    Raises:
        FileNotFoundError: If GOOGLE_APPLICATION_CREDENTIALS is not set or file doesn't exist.
        ValueError: If credentials file is invalid.
    """
    credentials_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    
    if not credentials_path:
        raise FileNotFoundError(
            "GOOGLE_APPLICATION_CREDENTIALS environment variable is not set"
        )
    
    if not os.path.exists(credentials_path):
        raise FileNotFoundError(
            f"Credentials file not found: {credentials_path}"
        )
    
    # Scopes required for Google Drive API
    SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
    
    try:
        credentials = service_account.Credentials.from_service_account_file(
            credentials_path,
            scopes=SCOPES
        )
        service = build('drive', 'v3', credentials=credentials)
        return service
    except Exception as e:
        raise ValueError(f"Failed to create Google Drive service: {e}")


def find_files_by_name(q_name: str, parent_folder_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Search for files in Google Drive by name.

    Args:
        q_name: Search query (file name or part of it).
        parent_folder_id: Optional. ID of the parent folder to search in.
                         If None, uses DRIVE_ROOT_FOLDER_ID from environment or searches in the entire Drive.

    Returns:
        List of dictionaries containing file information. Each dictionary contains:
        - 'id': File ID
        - 'name': File name
        - 'mimeType': MIME type
        - 'webViewLink': Web view link (if available)
        - 'size': File size in bytes (if available)
        - Other file metadata

    Raises:
        HttpError: If the API request fails.
        ValueError: If service cannot be created.
    """
    try:
        service = get_drive_service()
    except (FileNotFoundError, ValueError) as e:
        raise ValueError(f"Cannot search files: {e}")
    
    # Use DRIVE_ROOT_FOLDER_ID from environment if parent_folder_id is not provided
    if parent_folder_id is None:
        parent_folder_id = os.environ.get("DRIVE_ROOT_FOLDER_ID")
    
    # Build query string
    query = f"name contains '{q_name}' and trashed=false"
    
    if parent_folder_id:
        query += f" and '{parent_folder_id}' in parents"
    
    try:
        results = service.files().list(
            q=query,
            pageSize=100,
            fields="nextPageToken, files(id, name, mimeType, webViewLink, size, createdTime, modifiedTime)"
        ).execute()
        
        files = results.get('files', [])
        return files
    except HttpError as error:
        raise HttpError(f"An error occurred while searching files: {error}")


def download_file(file_id: str, dest_path: str) -> None:
    """
    Download a file from Google Drive by file ID.

    Args:
        file_id: The ID of the file to download.
        dest_path: Local file path where the file should be saved.

    Raises:
        HttpError: If the API request fails.
        ValueError: If service cannot be created or file cannot be downloaded.
        IOError: If file cannot be written to disk.
    """
    try:
        service = get_drive_service()
    except (FileNotFoundError, ValueError) as e:
        raise ValueError(f"Cannot download file: {e}")
    
    try:
        # Get file metadata
        file_metadata = service.files().get(fileId=file_id).execute()
        
        # Check if file is a Google Workspace file (Docs, Sheets, Slides)
        mime_type = file_metadata.get('mimeType', '')
        if mime_type.startswith('application/vnd.google-apps'):
            # Export Google Workspace files
            export_mime_type = 'application/pdf'  # Default export format
            if 'document' in mime_type:
                export_mime_type = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
            elif 'spreadsheet' in mime_type:
                export_mime_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            elif 'presentation' in mime_type:
                export_mime_type = 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
            
            request = service.files().export_media(fileId=file_id, mimeType=export_mime_type)
        else:
            # Download regular files
            request = service.files().get_media(fileId=file_id)
        
        # Download file
        with open(dest_path, 'wb') as f:
            downloader = MediaIoBaseDownload(f, request)
            done = False
            while done is False:
                status, done = downloader.next_chunk()
        
    except HttpError as error:
        raise HttpError(f"An error occurred while downloading file: {error}")
    except IOError as error:
        raise IOError(f"Failed to write file to {dest_path}: {error}")

