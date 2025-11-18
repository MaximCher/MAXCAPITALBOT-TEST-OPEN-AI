"""
Knowledge Base module for MAXCAPITAL Bot.

This module handles:
- Materials folder: documents, projects, presentations for sending to clients
- Info folder: information for client communication (scripts, FAQs, product info)
- Smart file search and retrieval based on intent and context
"""

import os
from typing import List, Dict, Optional, Any
import gdrive_service


# Folder structure in Google Drive
MATERIALS_FOLDER_ID = os.environ.get("DRIVE_MATERIALS_FOLDER_ID")  # Documents for sending
INFO_FOLDER_ID = os.environ.get("DRIVE_INFO_FOLDER_ID")  # Information for communication


def get_materials_by_intent(intent: Optional[str], query: str = "") -> List[Dict[str, Any]]:
    """
    Get materials from Materials folder based on intent and query.
    
    Args:
        intent: Detected intent (invest, documents, consult, support)
        query: Additional search query from user message
    
    Returns:
        List of file dictionaries with metadata
    """
    if not MATERIALS_FOLDER_ID:
        return []
    
    # Build search query based on intent
    search_terms = []
    
    if intent == "invest":
        search_terms = ["инвестиц", "investment", "продукт", "product", "проект", "project"]
    elif intent == "documents":
        search_terms = ["документ", "document", "презентация", "presentation", "брошюра", "brochure"]
    elif intent == "consult":
        search_terms = ["консультация", "consultation", "информация", "info", "руководство", "guide"]
    elif intent == "support":
        search_terms = ["поддержка", "support", "помощь", "help", "faq", "часто"]
    
    # Combine with user query
    if query:
        search_terms.append(query)
    
    # Search in materials folder
    all_files = []
    for term in search_terms[:3]:  # Limit to 3 most relevant terms
        try:
            files = gdrive_service.find_files_by_name(term, MATERIALS_FOLDER_ID)
            all_files.extend(files)
        except Exception:
            continue
    
    # Remove duplicates by file ID
    seen_ids = set()
    unique_files = []
    for file in all_files:
        file_id = file.get("id")
        if file_id and file_id not in seen_ids:
            seen_ids.add(file_id)
            unique_files.append(file)
    
    return unique_files[:10]  # Limit to 10 files


def get_info_for_communication(intent: Optional[str], topic: str = "") -> Optional[Dict[str, Any]]:
    """
    Get information from Info folder for client communication.
    
    This folder contains scripts, FAQs, product descriptions for bot responses.
    
    Args:
        intent: Detected intent
        topic: Specific topic or keyword
    
    Returns:
        File dictionary with information, or None if not found
    """
    if not INFO_FOLDER_ID:
        return None
    
    # Build search query
    search_query = topic or intent or ""
    
    if not search_query:
        return None
    
    try:
        files = gdrive_service.find_files_by_name(search_query, INFO_FOLDER_ID)
        if files:
            # Return the first (most relevant) file
            return files[0]
    except Exception:
        pass
    
    return None


def get_product_materials(product_name: str) -> List[Dict[str, Any]]:
    """
    Get materials for a specific product.
    
    Args:
        product_name: Name of the product
    
    Returns:
        List of file dictionaries related to the product
    """
    if not MATERIALS_FOLDER_ID:
        return []
    
    try:
        files = gdrive_service.find_files_by_name(product_name, MATERIALS_FOLDER_ID)
        return files[:5]  # Limit to 5 files per product
    except Exception:
        return []


def format_files_for_telegram(files: List[Dict[str, Any]], max_files: int = 5) -> str:
    """
    Format file list for Telegram message.
    
    Args:
        files: List of file dictionaries
        max_files: Maximum number of files to show
    
    Returns:
        Formatted string for Telegram
    """
    if not files:
        return "📁 Документы не найдены"
    
    lines = ["📁 Найденные материалы:"]
    
    for file in files[:max_files]:
        name = file.get("name", "Без названия")
        link = file.get("webViewLink", "")
        
        if link:
            lines.append(f"  • [{name}]({link})")
        else:
            lines.append(f"  • {name}")
    
    if len(files) > max_files:
        lines.append(f"\n_... и еще {len(files) - max_files} файлов_")
    
    return "\n".join(lines)

