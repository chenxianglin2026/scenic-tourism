"""
景区智慧管理系统 - 导览点位 API
POI点位列表查询
"""
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db, Poi

router = APIRouter(prefix="/api/points", tags=["导览点位"])


# ── Schemas ──────────────────────────────────────────
class PointOut(BaseModel):
    id: int
    spot_id: int
    name: str
    category: str
    description: Optional[str] = None
    lat: float
    lng: float
    images: Optional[str] = None
    audio_url: Optional[str] = None
    sort_order: int
    is_active: bool

    model_config = {"from_attributes": True}


class PointListResponse(BaseModel):
    code: int = 0
    msg: str = "ok"
    total: int = 0
    items: List[PointOut] = []


# ── API ─────────────────────────────────────────────
@router.get("", response_model=PointListResponse, summary="导览点位列表")
async def list_points(
    spot_id: Optional[int] = Query(None, description="景区ID"),
    category: Optional[str] = Query(None, description="点位分类"),
    page: int = Query(1, ge=1),
    page_size: int = Query(200, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    """查询景区导览点位(POI)列表"""
    q = select(Poi).where(Poi.is_active == True)
    count_q = select(func.count(Poi.id)).where(Poi.is_active == True)

    if spot_id:
        q = q.where(Poi.spot_id == spot_id)
        count_q = count_q.where(Poi.spot_id == spot_id)
    if category:
        q = q.where(Poi.category == category)
        count_q = count_q.where(Poi.category == category)

    total_result = await db.execute(count_q)
    total = total_result.scalar() or 0

    q = q.order_by(Poi.sort_order, Poi.id)
    offset = (page - 1) * page_size
    q = q.offset(offset).limit(page_size)

    result = await db.execute(q)
    items = result.scalars().all()

    return PointListResponse(
        total=total,
        items=list(items),
    )
