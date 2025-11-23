"""
MAXCAPITAL Bot - Handlers Package
"""

from src.handlers.start import router as start_router
from src.handlers.services import router as services_router
from src.handlers.lead import router as lead_router
from src.handlers.chat import router as chat_router

__all__ = [
    "start_router",
    "services_router",
    "lead_router",
    "chat_router"
]


