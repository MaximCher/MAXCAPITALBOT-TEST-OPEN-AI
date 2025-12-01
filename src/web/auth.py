"""
MAXCAPITAL Bot - Authentication for Admin Panel
One-time password system
"""

import secrets
import hashlib
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy import String, DateTime, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
import structlog

from src.database import Base

logger = structlog.get_logger()


class OneTimePassword(Base):
    """One-time passwords for admin panel access"""
    
    __tablename__ = "one_time_passwords"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    password_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    @staticmethod
    def hash_password(password: str) -> str:
        """Hash password using SHA256"""
        return hashlib.sha256(password.encode()).hexdigest()
    
    @classmethod
    async def create_password(cls, session: AsyncSession, expires_hours: int = 24) -> str:
        """Create a new one-time password"""
        # Generate random password (8 characters, alphanumeric)
        password = ''.join(secrets.choice('ABCDEFGHJKLMNPQRSTUVWXYZ23456789') for _ in range(8))
        password_hash = cls.hash_password(password)
        
        otp = cls(
            password_hash=password_hash,
            expires_at=datetime.utcnow() + timedelta(hours=expires_hours)
        )
        session.add(otp)
        await session.commit()
        
        logger.info("otp_created", otp_id=otp.id, expires_at=otp.expires_at)
        
        return password
    
    @classmethod
    async def verify_password(cls, session: AsyncSession, password: str) -> bool:
        """Verify and consume one-time password"""
        password_hash = cls.hash_password(password)
        
        result = await session.execute(
            select(cls).where(
                cls.password_hash == password_hash,
                cls.used == False,
                cls.expires_at > datetime.utcnow()
            )
        )
        otp = result.scalar_one_or_none()
        
        if not otp:
            logger.warning("otp_verification_failed", password_provided=bool(password))
            return False
        
        # Mark as used
        otp.used = True
        otp.used_at = datetime.utcnow()
        await session.commit()
        
        logger.info("otp_verified_and_consumed", otp_id=otp.id)
        
        # Clean up old used passwords (older than 7 days)
        cutoff_date = datetime.utcnow() - timedelta(days=7)
        await session.execute(
            delete(cls).where(
                cls.used == True,
                cls.used_at < cutoff_date
            )
        )
        await session.commit()
        
        return True




