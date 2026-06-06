"""Container startup: ensure admin user exists"""
import asyncio
from app.config import settings
from app.db import get_async_session_factory, User
from app.api.auth import hash_password
from sqlalchemy import select


async def ensure_admin():
    factory = get_async_session_factory()
    async with factory() as db:
        result = await db.execute(select(User).where(User.username == "admin"))
        user = result.scalar_one_or_none()
        if not user:
            user = User(
                username="admin",
                phone="13800000001",
                hashed_password=hash_password("admin123"),
                role="admin",
                nickname="管理员",
            )
            db.add(user)
            await db.commit()
            print("✅ Admin user created: admin / admin123")
        else:
            print("✅ Admin user exists")


if __name__ == "__main__":
    asyncio.run(ensure_admin())
