"""
景区智慧管理系统 - 系统设置 API
景区名称 / 地址 / 电话 / 开闭园时间等基础信息
"""
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db, ScenicSpot

router = APIRouter(prefix="/api/settings", tags=["系统设置"])


# ── Schemas ──────────────────────────────────────────
class SettingsOut(BaseModel):
    spot_name: str
    address: str
    phone: Optional[str] = None
    open_time: str
    close_time: str
    daily_limit: int


# ── API ─────────────────────────────────────────────
@router.get("", response_model=SettingsOut, summary="系统设置")
async def get_settings(db: AsyncSession = Depends(get_db)):
    """返回景区基础信息（取第一个激活景区）"""
    result = await db.execute(
        select(ScenicSpot).where(ScenicSpot.is_active == True).order_by(ScenicSpot.id.asc()).limit(1)
    )
    spot = result.scalar_one_or_none()
    if not spot:
        return SettingsOut(
            spot_name="泰山风景名胜区",
            address="山东省泰安市泰山区红门路45号",
            phone="0538-96008888",
            open_time="05:00",
            close_time="23:00",
            daily_limit=30000,
        )
    return SettingsOut(
        spot_name=spot.name,
        address=spot.address,
        phone=spot.phone,
        open_time=spot.open_time,
        close_time=spot.close_time,
        daily_limit=spot.daily_limit,
    )
