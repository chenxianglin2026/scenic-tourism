"""
景区智慧管理系统 - 房间 API
房间列表查询
"""
from datetime import date
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db, Room, Hotel

router = APIRouter(prefix="/api/rooms", tags=["房间"])


# ── Schemas ──────────────────────────────────────────
class RoomOut(BaseModel):
    id: int
    hotel_id: int
    name: str
    room_type: str
    price: float
    total_count: int
    available_count: int
    area: Optional[float] = None
    bed_type: Optional[str] = None
    max_guests: int
    has_window: bool
    has_wifi: bool
    has_bathtub: bool
    description: Optional[str] = None
    images: Optional[str] = None
    is_active: bool
    original_price: Optional[float] = None
    current_price: Optional[float] = None
    has_discount: Optional[bool] = None

    model_config = {"from_attributes": True}


class RoomListResponse(BaseModel):
    code: int = 0
    msg: str = "ok"
    items: List[RoomOut] = []
    total: int = 0


# ── API ─────────────────────────────────────────────
@router.get("", response_model=RoomListResponse, summary="房间列表")
async def list_rooms(
    hotel_id: Optional[int] = Query(None, description="酒店ID"),
    spot_id: Optional[int] = Query(None, description="景区ID"),
    query_date: Optional[date] = Query(None, description="查询日期（用于计算动态价格）"),
    nights: int = Query(1, ge=1, description="入住晚数"),
    db: AsyncSession = Depends(get_db),
):
    """查询房间列表，支持按酒店或景区筛选，可传 date/nights 获取动态价格"""
    from app.api.pricing import calculate_price
    q = select(Room).where(Room.is_active == True)

    if hotel_id:
        q = q.where(Room.hotel_id == hotel_id)

    if spot_id:
        q = q.where(Room.hotel_id.in_(
            select(Hotel.id).where(Hotel.spot_id == spot_id, Hotel.is_active == True)
        ))

    result = await db.execute(q)
    rooms = result.scalars().all()

    items = []
    for room in rooms:
        data = RoomOut.model_validate(room)
        data.original_price = room.price
        if query_date:
            try:
                pricing = await calculate_price(
                    db, target_type="hotel", target_id=room.id,
                    query_date=query_date, nights=nights
                )
                data.current_price = round(pricing["final_price"] / nights, 2)
                data.has_discount = pricing["final_price"] < pricing["base_price"]
            except Exception:
                data.current_price = room.price
                data.has_discount = False
        else:
            data.current_price = room.price
            data.has_discount = False
        items.append(data)

    return RoomListResponse(
        items=items,
        total=len(items),
    )
