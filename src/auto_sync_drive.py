"""
MAXCAPITAL Bot - Auto Sync Google Drive
Automatically syncs documents from Google Drive folder
"""

import asyncio
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import hashlib
import structlog

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.config import settings
from src.database import get_session
from src.models.documents import Document
from src.vector_store import VectorStore

logger = structlog.get_logger()


class DriveAutoSync:
    """Automatically sync documents from Google Drive"""
    
    def __init__(self):
        self.folder_id = settings.google_drive_folder_id
        self.credentials_file = settings.google_credentials_file
        self.sync_interval_minutes = 60  # Check every hour
        self.last_sync: Optional[datetime] = None
        
    async def should_sync(self) -> bool:
        """Check if we should run sync"""
        if not self.folder_id:
            logger.warning("drive_sync_disabled", reason="no_folder_id")
            return False
        
        if not self.last_sync:
            return True
        
        time_since_sync = datetime.utcnow() - self.last_sync
        return time_since_sync > timedelta(minutes=self.sync_interval_minutes)
    
    def get_drive_service(self):
        """Get Google Drive API service"""
        try:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build
            
            credentials = service_account.Credentials.from_service_account_file(
                self.credentials_file,
                scopes=['https://www.googleapis.com/auth/drive.readonly']
            )
            
            service = build('drive', 'v3', credentials=credentials)
            return service
        except Exception as e:
            logger.error("drive_service_init_failed", error=str(e))
            return None
    
    async def list_drive_files(self, folder_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all files in the folder recursively (including subfolders)"""
        try:
            service = self.get_drive_service()
            if not service:
                return []
            
            target_folder = folder_id or self.folder_id
            all_files = []
            
            results = service.files().list(
                q=f"'{target_folder}' in parents and trashed=false",
                fields="files(id, name, mimeType, size, modifiedTime, md5Checksum)",
                pageSize=100
            ).execute()
            
            items = results.get('files', [])
            
            for item in items:
                if item['mimeType'] == 'application/vnd.google-apps.folder':
                    # Recursively list files in subfolder
                    logger.info("scanning_subfolder", folder_name=item['name'])
                    subfolder_files = await self.list_drive_files(item['id'])
                    all_files.extend(subfolder_files)
                else:
                    # It's a file, add it
                    all_files.append(item)
            
            if folder_id is None:  # Only log for root folder
                logger.info(
                    "drive_files_listed",
                    count=len(all_files),
                    folder_id=self.folder_id
                )
            
            return all_files
        except Exception as e:
            logger.error("drive_list_failed", error=str(e))
            return []
    
    async def get_existing_documents(self, session: AsyncSession) -> Dict[str, Document]:
        """Get existing documents from database"""
        result = await session.execute(
            select(Document).where(Document.drive_file_id.isnot(None))
        )
        docs = result.scalars().all()
        
        # Map by drive_file_id
        return {doc.drive_file_id: doc for doc in docs}
    
    def download_file_content(self, service, file_id: str, mime_type: str) -> Optional[str]:
        """Download and extract text from file"""
        try:
            from googleapiclient.http import MediaIoBaseDownload
            import io
            
            # Handle Google Workspace files (Docs, Sheets, etc.) - MUST use export
            google_workspace_types = {
                'application/vnd.google-apps.document': 'text/plain',
                'application/vnd.google-apps.spreadsheet': 'text/csv',
                'application/vnd.google-apps.presentation': 'text/plain',
                'application/vnd.google-apps.folder': None,  # Skip folders
            }
            
            if mime_type in google_workspace_types:
                export_mime = google_workspace_types[mime_type]
                if export_mime is None:
                    logger.debug("skipping_folder", file_id=file_id)
                    return None
                
                # Export Google Workspace file
                logger.debug("exporting_google_doc", file_id=file_id, export_mime=export_mime)
                request = service.files().export_media(
                    fileId=file_id,
                    mimeType=export_mime
                )
                file_data = io.BytesIO()
                downloader = MediaIoBaseDownload(file_data, request)
                done = False
                while not done:
                    status, done = downloader.next_chunk()
                file_data.seek(0)
                content = file_data.read().decode('utf-8', errors='ignore')
                logger.info("google_doc_exported", file_id=file_id, content_length=len(content))
                return content
            
            # Handle regular binary files
            request = service.files().get_media(fileId=file_id)
            file_data = io.BytesIO()
            downloader = MediaIoBaseDownload(file_data, request)
            
            done = False
            while not done:
                status, done = downloader.next_chunk()
            
            file_data.seek(0)
            content_bytes = file_data.read()
            
            # Extract text based on mime type
            if 'text/plain' in mime_type or 'text/csv' in mime_type:
                return content_bytes.decode('utf-8', errors='ignore')
            
            elif 'application/pdf' in mime_type:
                import PyPDF2
                pdf_reader = PyPDF2.PdfReader(io.BytesIO(content_bytes))
                text = ""
                for page in pdf_reader.pages:
                    text += page.extract_text() + "\n"
                return text
            
            elif 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' in mime_type:
                from docx import Document as DocxDocument
                doc = DocxDocument(io.BytesIO(content_bytes))
                text = "\n".join([para.text for para in doc.paragraphs])
                return text
            
            else:
                logger.warning("unsupported_mime_type", mime_type=mime_type)
                return None
            
        except Exception as e:
            logger.error("file_download_failed", file_id=file_id, error=str(e))
            return None
    
    async def sync_file(
        self,
        service,
        file: Dict[str, Any],
        existing_docs: Dict[str, Document]
    ) -> bool:
        """Sync a single file - uses separate session per file for isolation"""
        try:
            file_id = file['id']
            filename = file['name']
            mime_type = file['mimeType']
            
            # Check if file already exists and hasn't changed
            existing_doc = existing_docs.get(file_id)
            if existing_doc:
                logger.debug("file_already_synced", filename=filename)
                return False
            
            # Download and extract text
            content = self.download_file_content(service, file_id, mime_type)
            
            if not content or len(content) < 50:
                logger.warning("file_content_too_short", filename=filename)
                return False
            
            # Use separate session for each file to isolate errors
            async for session in get_session():
                try:
                    vector_store = VectorStore(session)
                    
                    # Get file_size as int
                    file_size = file.get('size')
                    if file_size:
                        file_size = int(file_size)
                    
                    # Add new document
                    await vector_store.add_document(
                        filename=filename,
                        content=content,
                        file_type=mime_type,
                        file_size=file_size,
                        drive_file_id=file_id
                    )
                    
                    logger.info(
                        "file_synced",
                        filename=filename,
                        file_id=file_id,
                        content_length=len(content)
                    )
                    
                    return True
                except Exception as e:
                    logger.error("file_sync_session_error", filename=filename, error=str(e))
                    return False
            
            return False
            
        except Exception as e:
            logger.error(
                "file_sync_failed",
                filename=file.get('name'),
                error=str(e)
            )
            return False
    
    async def run_sync(self) -> Dict[str, Any]:
        """Run full sync process"""
        if not await self.should_sync():
            logger.debug("sync_skipped", reason="too_soon")
            return {"synced": 0, "skipped": 0, "errors": 0}
        
        logger.info("drive_sync_starting")
        
        stats = {
            "synced": 0,
            "skipped": 0,
            "errors": 0,
            "start_time": datetime.utcnow()
        }
        
        try:
            # Get Drive service
            service = self.get_drive_service()
            if not service:
                logger.error("drive_sync_failed", reason="no_service")
                return stats
            
            # List files from Drive
            drive_files = await self.list_drive_files()
            
            if not drive_files:
                logger.info("drive_sync_no_files")
                return stats
            
            # Get existing documents first
            existing_docs = {}
            async for session in get_session():
                existing_docs = await self.get_existing_documents(session)
                break
            
            # Sync each file (each file uses its own session)
            for file in drive_files:
                success = await self.sync_file(
                    service=service,
                    file=file,
                    existing_docs=existing_docs
                )
                
                if success:
                    stats["synced"] += 1
                else:
                    stats["skipped"] += 1
            
            self.last_sync = datetime.utcnow()
            stats["end_time"] = datetime.utcnow()
            stats["duration_seconds"] = (stats["end_time"] - stats["start_time"]).total_seconds()
            
            logger.info(
                "drive_sync_completed",
                synced=stats["synced"],
                skipped=stats["skipped"],
                duration=stats["duration_seconds"]
            )
            
            return stats
            
        except Exception as e:
            logger.error("drive_sync_error", error=str(e))
            stats["errors"] += 1
            return stats
    
    async def start_background_sync(self):
        """Start background sync loop"""
        logger.info("drive_auto_sync_started", interval_minutes=self.sync_interval_minutes)
        
        while True:
            try:
                await self.run_sync()
            except Exception as e:
                logger.error("background_sync_error", error=str(e))
            
            # Wait before next sync
            await asyncio.sleep(self.sync_interval_minutes * 60)


# Global instance
drive_sync = DriveAutoSync()

