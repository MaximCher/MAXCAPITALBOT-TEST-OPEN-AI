"""
MAXCAPITAL Bot - Google Drive Loader
Downloads and processes documents from Google Drive
"""

import io
import os
from typing import List, Optional
from pathlib import Path

import PyPDF2
import pdfplumber
from docx import Document as DocxDocument
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import structlog

from src.config import settings

logger = structlog.get_logger()


class GoogleDriveLoader:
    """Loads documents from Google Drive and extracts text"""
    
    SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
    
    def __init__(self):
        self.service = None
        self.folder_id = settings.google_drive_folder_id
        self.credentials_file = settings.google_credentials_file
    
    def authenticate(self) -> None:
        """Authenticate with Google Drive API"""
        try:
            if not os.path.exists(self.credentials_file):
                logger.warning(
                    "google_credentials_not_found",
                    file=self.credentials_file
                )
                return
            
            credentials = service_account.Credentials.from_service_account_file(
                self.credentials_file,
                scopes=self.SCOPES
            )
            
            self.service = build('drive', 'v3', credentials=credentials)
            logger.info("google_drive_authenticated")
            
        except Exception as e:
            logger.error("google_drive_auth_failed", error=str(e))
            raise
    
    def list_files(self, folder_id: Optional[str] = None) -> List[dict]:
        """List files in Google Drive folder"""
        if not self.service:
            self.authenticate()
        
        if not self.service:
            return []
        
        folder_id = folder_id or self.folder_id
        
        if not folder_id:
            logger.warning("no_folder_id_specified")
            return []
        
        try:
            query = f"'{folder_id}' in parents and trashed=false"
            query += " and (mimeType='application/pdf' or "
            query += "mimeType='application/vnd.openxmlformats-officedocument.wordprocessingml.document' or "
            query += "mimeType='text/plain')"
            
            results = self.service.files().list(
                q=query,
                fields="files(id, name, mimeType, size)",
                pageSize=100
            ).execute()
            
            files = results.get('files', [])
            logger.info("google_drive_files_listed", count=len(files))
            
            return files
            
        except Exception as e:
            logger.error("list_files_failed", error=str(e))
            return []
    
    def download_file(self, file_id: str, file_name: str) -> Optional[bytes]:
        """Download file from Google Drive"""
        if not self.service:
            self.authenticate()
        
        if not self.service:
            return None
        
        try:
            request = self.service.files().get_media(fileId=file_id)
            file_buffer = io.BytesIO()
            downloader = MediaIoBaseDownload(file_buffer, request)
            
            done = False
            while not done:
                status, done = downloader.next_chunk()
            
            file_buffer.seek(0)
            content = file_buffer.read()
            
            logger.info(
                "file_downloaded",
                file_name=file_name,
                size=len(content)
            )
            
            return content
            
        except Exception as e:
            logger.error("download_failed", file_name=file_name, error=str(e))
            return None
    
    @staticmethod
    def extract_text_from_pdf(file_content: bytes) -> str:
        """Extract text from PDF file"""
        try:
            # Try with pdfplumber first (better for complex PDFs)
            pdf_buffer = io.BytesIO(file_content)
            with pdfplumber.open(pdf_buffer) as pdf:
                text_parts = []
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        text_parts.append(text)
                
                if text_parts:
                    return "\n\n".join(text_parts)
            
            # Fallback to PyPDF2
            pdf_buffer = io.BytesIO(file_content)
            pdf_reader = PyPDF2.PdfReader(pdf_buffer)
            text_parts = []
            
            for page in pdf_reader.pages:
                text = page.extract_text()
                if text:
                    text_parts.append(text)
            
            return "\n\n".join(text_parts)
            
        except Exception as e:
            logger.error("pdf_extraction_failed", error=str(e))
            return ""
    
    @staticmethod
    def extract_text_from_docx(file_content: bytes) -> str:
        """Extract text from DOCX file"""
        try:
            docx_buffer = io.BytesIO(file_content)
            doc = DocxDocument(docx_buffer)
            
            paragraphs = [para.text for para in doc.paragraphs if para.text.strip()]
            return "\n\n".join(paragraphs)
            
        except Exception as e:
            logger.error("docx_extraction_failed", error=str(e))
            return ""
    
    @staticmethod
    def extract_text_from_txt(file_content: bytes) -> str:
        """Extract text from TXT file"""
        try:
            # Try different encodings
            for encoding in ['utf-8', 'cp1251', 'iso-8859-1']:
                try:
                    return file_content.decode(encoding)
                except UnicodeDecodeError:
                    continue
            
            # Fallback: ignore errors
            return file_content.decode('utf-8', errors='ignore')
            
        except Exception as e:
            logger.error("txt_extraction_failed", error=str(e))
            return ""
    
    def extract_text(self, file_content: bytes, mime_type: str) -> str:
        """Extract text based on file type"""
        if mime_type == 'application/pdf':
            return self.extract_text_from_pdf(file_content)
        elif mime_type == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document':
            return self.extract_text_from_docx(file_content)
        elif mime_type == 'text/plain':
            return self.extract_text_from_txt(file_content)
        else:
            logger.warning("unsupported_mime_type", mime_type=mime_type)
            return ""
    
    async def load_all_documents(self) -> List[dict]:
        """
        Load all documents from Google Drive
        Returns list of dicts with file info and extracted text
        """
        files = self.list_files()
        documents = []
        
        for file_info in files:
            file_id = file_info['id']
            file_name = file_info['name']
            mime_type = file_info['mimeType']
            file_size = file_info.get('size', 0)
            
            # Download file
            file_content = self.download_file(file_id, file_name)
            
            if not file_content:
                continue
            
            # Extract text
            text = self.extract_text(file_content, mime_type)
            
            if not text or len(text.strip()) < 50:
                logger.warning("insufficient_text", file_name=file_name)
                continue
            
            documents.append({
                'filename': file_name,
                'content': text,
                'file_type': Path(file_name).suffix.lstrip('.'),
                'file_size': int(file_size) if file_size else len(file_content),
                'drive_file_id': file_id,
                'mime_type': mime_type
            })
            
            logger.info(
                "document_processed",
                filename=file_name,
                text_length=len(text)
            )
        
        return documents


