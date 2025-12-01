"""
MAXCAPITAL Bot - Web API Endpoints
FastAPI endpoints for admin panel
"""

from datetime import datetime, timezone
from typing import Optional, List
from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, field_serializer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
import structlog

from src.database import get_session
from src.models.dialog_message import DialogMessage
from src.models.bitrix_lead import BitrixLead
from src.config import settings

logger = structlog.get_logger()

app = FastAPI(title="MAXCAPITAL Bot Admin Panel", version="1.0.0")

# Templates and static files
import os
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TEMPLATES_DIR = os.path.join(BASE_DIR, "src", "web", "templates")
STATIC_DIR = os.path.join(BASE_DIR, "src", "web", "static")

templates = Jinja2Templates(directory=TEMPLATES_DIR)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# Pydantic models for API
class LoginRequest(BaseModel):
    password: str


class DialogMessageResponse(BaseModel):
    id: int
    user_id: int
    username: Optional[str]
    full_name: Optional[str]
    phone: Optional[str]
    message_text: str
    role: str
    chat_id: int
    message_id: Optional[int]
    created_at: datetime
    
    @field_serializer('created_at')
    def serialize_created_at(self, dt: datetime, _info) -> str:
        """Serialize datetime as ISO 8601 with UTC timezone"""
        # If datetime is naive (no timezone), assume it's UTC
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        # Return ISO format with timezone
        return dt.isoformat()
    
    class Config:
        from_attributes = True


class UserSummaryResponse(BaseModel):
    user_id: int
    full_name: Optional[str]
    phone: Optional[str]
    username: Optional[str]
    message_count: int
    last_message_at: datetime
    
    @field_serializer('last_message_at')
    def serialize_last_message_at(self, dt: datetime, _info) -> str:
        """Serialize datetime as ISO 8601 with UTC timezone"""
        # If datetime is naive (no timezone), assume it's UTC
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        # Return ISO format with timezone
        return dt.isoformat()


class DialogListResponse(BaseModel):
    messages: List[DialogMessageResponse]
    total: int
    limit: int
    offset: int


class UserListResponse(BaseModel):
    users: List[UserSummaryResponse]
    total: int


class StatisticsResponse(BaseModel):
    dialogs_today: int
    dialogs_total: int
    leads_today: int
    leads_total: int


# Session management (simple in-memory for now)
active_sessions = set()


async def get_db_session() -> AsyncSession:
    """Dependency to get database session"""
    async for session in get_session():
        yield session


async def verify_session(request: Request) -> bool:
    """Verify if user has active session"""
    session_id = request.cookies.get("admin_session")
    return session_id in active_sessions if session_id else False


async def require_auth(request: Request):
    """Dependency to require authentication"""
    if not await verify_session(request):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )


@app.post("/api/login")
async def login(
    login_data: LoginRequest,
    request: Request
):
    """Login with password from environment"""
    # Verify password against environment variable
    if login_data.password != settings.chat_history_password:
        logger.warning("admin_login_failed", provided_password_length=len(login_data.password))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid password"
        )
    
    # Create session
    import secrets
    session_id = secrets.token_urlsafe(32)
    active_sessions.add(session_id)
    
    response = JSONResponse({"success": True, "message": "Login successful"})
    response.set_cookie(
        key="admin_session",
        value=session_id,
        httponly=True,
        secure=False,  # Set to True if using HTTPS
        samesite="lax",
        max_age=86400  # 24 hours
    )
    
    logger.info("admin_login_successful", session_id=session_id[:8])
    
    return response


@app.post("/api/logout")
async def logout(request: Request):
    """Logout and clear session"""
    session_id = request.cookies.get("admin_session")
    if session_id:
        active_sessions.discard(session_id)
    
    response = JSONResponse({"success": True, "message": "Logged out"})
    response.delete_cookie("admin_session")
    
    return response


@app.get("/api/dialogs", response_model=DialogListResponse)
async def get_dialogs(
    request: Request,
    user_id: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    session: AsyncSession = Depends(get_db_session),
    _: None = Depends(require_auth)
):
    """Get dialog messages with filters"""
    start_dt = None
    end_dt = None
    
    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid start_date format")
    
    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid end_date format")
    
    messages = await DialogMessage.get_user_dialogs(
        session=session,
        user_id=user_id,
        start_date=start_dt,
        end_date=end_dt,
        limit=limit,
        offset=offset
    )
    
    # Get total count (simplified - in production you'd want a proper count query)
    total = len(messages)  # This is approximate, proper implementation would use COUNT
    
    return DialogListResponse(
        messages=[DialogMessageResponse.model_validate(msg) for msg in messages],
        total=total,
        limit=limit,
        offset=offset
    )


@app.get("/api/users", response_model=UserListResponse)
async def get_users(
    request: Request,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    session: AsyncSession = Depends(get_db_session),
    _: None = Depends(require_auth)
):
    """Get list of unique users"""
    start_dt = None
    end_dt = None
    
    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid start_date format")
    
    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid end_date format")
    
    users = await DialogMessage.get_unique_users(
        session=session,
        start_date=start_dt,
        end_date=end_dt
    )
    
    return UserListResponse(
        users=[UserSummaryResponse(**user) for user in users],
        total=len(users)
    )


@app.get("/api/conversation/{user_id}", response_model=DialogListResponse)
async def get_conversation(
    user_id: int,
    request: Request,
    limit: int = 50,
    session: AsyncSession = Depends(get_db_session),
    _: None = Depends(require_auth)
):
    """Get conversation history for a specific user"""
    messages = await DialogMessage.get_conversation(
        session=session,
        user_id=user_id,
        limit=limit
    )
    
    return DialogListResponse(
        messages=[DialogMessageResponse.model_validate(msg) for msg in messages],
        total=len(messages),
        limit=limit,
        offset=0
    )


@app.get("/api/statistics", response_model=StatisticsResponse)
async def get_statistics(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    _: None = Depends(require_auth)
):
    """Get statistics: dialogs and leads counts"""
    from datetime import date, timedelta, timezone
    
    try:
        # Today's date range (UTC, naive datetime to match DB storage)
        today = date.today()
        today_start = datetime.combine(today, datetime.min.time())
        today_end = datetime.combine(today + timedelta(days=1), datetime.min.time())
        
        # Count dialogs (unique users, not messages)
        # Total unique users who sent messages
        dialogs_total_query = select(func.count(func.distinct(DialogMessage.user_id)))
        
        # Unique users who sent messages today
        dialogs_today_query = select(func.count(func.distinct(DialogMessage.user_id))).where(
            DialogMessage.created_at >= today_start,
            DialogMessage.created_at < today_end
        )
        
        dialogs_today_result = await session.execute(dialogs_today_query)
        dialogs_total_result = await session.execute(dialogs_total_query)
        
        dialogs_today = dialogs_today_result.scalar() or 0
        dialogs_total = dialogs_total_result.scalar() or 0
        
        # Count leads
        leads_today = await BitrixLead.get_today_count(session)
        leads_total = await BitrixLead.get_count(session)
        
        logger.info(
            "statistics_calculated",
            dialogs_today=dialogs_today,
            dialogs_total=dialogs_total,
            leads_today=leads_today,
            leads_total=leads_total,
            today_start=str(today_start)
        )
        
        return StatisticsResponse(
            dialogs_today=dialogs_today,
            dialogs_total=dialogs_total,
            leads_today=leads_today,
            leads_total=leads_total
        )
    except Exception as e:
        logger.error("statistics_error", error=str(e), exc_info=True)
        # Return zeros on error
        return StatisticsResponse(
            dialogs_today=0,
            dialogs_total=0,
            leads_today=0,
            leads_total=0
        )


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Serve admin panel frontend"""
    return templates.TemplateResponse("index.html", {"request": request})

