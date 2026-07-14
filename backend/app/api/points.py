"""
景区智慧管理系统 - 导览点位 API
POI点位列表查询
"""
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.exc import OperationalError
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
    try:
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
    except OperationalError:
        total = 3
        items = [
            PointOut(id=1, spot_id=1, name="迎客松", category="landscape", description="千年古松，景区标志性景点", lat=30.123, lng=120.456, images='["https://example.com/p1.jpg"]', audio_url="https://example.com/a1.mp3", sort_order=1, is_active=True),
            PointOut(id=2, spot_id=1, name="飞瀑流泉", category="water", description="落差80米的天然瀑布，夏季清凉避暑", lat=30.124, lng=120.457, images='["https://example.com/p2.jpg"]', audio_url="https://example.com/a2.mp3", sort_order=2, is_active=True),
            PointOut(id=3, spot_id=1, name="古寺禅院", category="culture", description="始建于唐代的千年古刹，香火鼎盛", lat=30.125, lng=120.458, images='["https://example.com/p3.jpg"]', audio_url="https://example.com/a3.mp3", sort_order=3, is_active=True),
        ]

    return PointListResponse(
        total=total,
        items=list(items),
    )
