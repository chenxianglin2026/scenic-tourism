"""
景区智慧管理系统 - 周边推荐 API
餐饮/购物/娱乐推荐
"""
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db, NearbyPoint

router = APIRouter(prefix="/api/recommendations", tags=["周边推荐"])


# ── Schemas ──────────────────────────────────────────
class RecommendationOut(BaseModel):
    id: int
    spot_id: int
    name: str
    category: str
    description: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    rating: float
    images: Optional[str] = None
    distance: Optional[float] = None
    price_range: Optional[str] = None
    open_time: Optional[str] = None
    sort_order: int
    is_active: bool

    model_config = {"from_attributes": True}


class RecommendationListResponse(BaseModel):
    code: int = 0
    msg: str = "ok"
    total: int = 0
    items: List[RecommendationOut] = []


# ── API ─────────────────────────────────────────────
@router.get("", response_model=RecommendationListResponse, summary="周边推荐列表")
async def list_recommendations(
    spot_id: Optional[int] = Query(None, description="景区ID"),
    category: Optional[str] = Query(None, description="dining/shopping/entertainment"),
    keyword: Optional[str] = Query(None, description="搜索关键词"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """查询景区周边餐饮/购物/娱乐推荐"""
    base_q = select(NearbyPoint).where(NearbyPoint.is_active == True)
    count_q = select(func.count(NearbyPoint.id)).where(NearbyPoint.is_active == True)

    if spot_id:
        base_q = base_q.where(NearbyPoint.spot_id == spot_id)
        count_q = count_q.where(NearbyPoint.spot_id == spot_id)
    if category:
        base_q = base_q.where(NearbyPoint.category == category)
        count_q = count_q.where(NearbyPoint.category == category)
    if keyword:
        kw_filter = or_(
            NearbyPoint.name.like(f"%{keyword}%"),
            NearbyPoint.description.like(f"%{keyword}%"),
            NearbyPoint.address.like(f"%{keyword}%"),
        )
        base_q = base_q.where(kw_filter)
        count_q = count_q.where(kw_filter)

    total_result = await db.execute(count_q)
    total = total_result.scalar() or 0

    offset = (page - 1) * page_size
    items_result = await db.execute(
        base_q.order_by(NearbyPoint.sort_order, NearbyPoint.distance.asc().nulls_last(), NearbyPoint.rating.desc())
        .offset(offset).limit(page_size)
    )
    items = items_result.scalars().all()

    return RecommendationListResponse(
        total=total,
        items=list(items),
    )
