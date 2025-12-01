"""
Generate one-time password for admin panel access
"""

import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database import init_db, close_db
from src.web.auth import OneTimePassword
from sqlalchemy.ext.asyncio import AsyncSession
from src.database import get_session


async def generate_otp(expires_hours: int = 24):
    """Generate a new one-time password"""
    await init_db()
    
    async for session in get_session():
        password = await OneTimePassword.create_password(session, expires_hours)
        print(f"\n{'='*50}")
        print(f"Одноразовый пароль для админ-панели:")
        print(f"{password}")
        print(f"{'='*50}")
        print(f"Пароль действителен {expires_hours} часов")
        print(f"После использования пароль будет удален")
        print(f"{'='*50}\n")
        break
    
    await close_db()


if __name__ == "__main__":
    expires = int(sys.argv[1]) if len(sys.argv) > 1 else 24
    asyncio.run(generate_otp(expires))




