"""
景区智慧管理系统 - 内容管理 API
酒店介绍 / 房型实景 / 周边推荐 / 精选评价 聚合接口
"""
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import (
    get_db, Hotel, Room, NearbyPoint, Review
)

router = APIRouter(prefix="/api/content", tags=["内容管理"])


# ── Schemas ──────────────────────────────────────────
class HotelContentOut(BaseModel):
    id: int
    name: str
    address: str
    city: str
    phone: Optional[str] = None
    description: Optional[str] = None
    cover_image: Optional[str] = None
    rating: float
    checkin_time: str = "14:00"
    checkout_time: str = "12:00"
    features: List[str] = []

    model_config = {"from_attributes": True}


class GalleryOut(BaseModel):
    room_id: int
    room_name: str
    images: List[str] = []
    video: Optional[str] = None
    vr_url: Optional[str] = None
    desc: Optional[str] = None


class ReviewContentOut(BaseModel):
    user_name: str
    rating: int
    content: str
    images: List[str] = []
    date: Optional[str] = None


class ContentResponse(BaseModel):
    code: int = 0
    msg: str = "ok"
    hotels: List[HotelContentOut] = []
    galleries: List[GalleryOut] = []
    surrounds: List[dict] = []
    reviews: List[ReviewContentOut] = []


# ── API ─────────────────────────────────────────────
@router.get("", response_model=ContentResponse, summary="内容聚合")
async def get_content(
    spot_id: Optional[int] = Query(None, description="景区ID"),
    db: AsyncSession = Depends(get_db),
):
    """聚合返回酒店介绍、房型实景、周边推荐、精选评价"""
    hotels_out = []
    galleries_out = []
    surrounds_out = []
    reviews_out = []

    # 酒店
    try:
        hotel_q = select(Hotel).where(Hotel.is_active == True)
        if spot_id:
            hotel_q = hotel_q.where(Hotel.spot_id == spot_id)
        hotel_result = await db.execute(hotel_q)
        hotels = hotel_result.scalars().all()
    except OperationalError:
        hotels = []

    for h in hotels:
        features = []
        if h.description:
            # 简单从描述中提取特色关键词
            for kw in ["WiFi", "停车场", "健身房", "泳池", "餐厅", "SPA"]:
                if kw in h.description:
                    features.append(kw)
        hotels_out.append(HotelContentOut(
            id=h.id,
            name=h.name,
            address=h.address,
            city=h.city,
            phone=h.phone,
            description=h.description,
            cover_image=h.cover_image,
            rating=h.rating,
            features=features,
        ))

        # 房型实景
        try:
            room_result = await db.execute(
                select(Room).where(Room.hotel_id == h.id, Room.is_active == True)
            )
            rooms = room_result.scalars().all()
        except OperationalError:
            rooms = []
        for r in rooms:
            imgs = []
            if r.images:
                try:
                    import json
                    imgs = json.loads(r.images)
                except Exception:
                    pass
            galleries_out.append(GalleryOut(
                room_id=r.id,
                room_name=r.name,
                images=imgs,
                desc=r.description,
            ))

    # 周边推荐
    try:
        nearby_q = select(NearbyPoint).where(NearbyPoint.is_active == True)
        if spot_id:
            nearby_q = nearby_q.where(NearbyPoint.spot_id == spot_id)
        nearby_result = await db.execute(nearby_q.order_by(NearbyPoint.sort_order).limit(20))
        nearby_items = nearby_result.scalars().all()
    except OperationalError:
        nearby_items = []

    for n in nearby_items:
        surrounds_out.append({
            "name": n.name,
            "type": n.category,
            "distance": n.distance,
            "rating": n.rating,
            "desc": n.description,
            "phone": n.phone,
        })

    # 精选评价
    try:
        review_q = select(Review).where(Review.is_approved == True)
        if spot_id:
            review_q = review_q.where(Review.spot_id == spot_id)
        review_result = await db.execute(review_q.order_by(Review.created_at.desc()).limit(10))
        reviews = review_result.scalars().all()
    except OperationalError:
        reviews = []

    for r in reviews:
        imgs = []
        if r.images:
            try:
                import json
                imgs = json.loads(r.images)
            except Exception:
                pass
        reviews_out.append(ReviewContentOut(
            user_name=f"用户{r.user_id}",
            rating=r.rating,
            content=r.content,
            images=imgs,
            date=r.created_at.strftime("%Y-%m-%d") if r.created_at else None,
        ))

    return ContentResponse(
        hotels=hotels_out,
        galleries=galleries_out,
        surrounds=surrounds_out,
        reviews=reviews_out,
    )
