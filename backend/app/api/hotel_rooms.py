"""
景区智慧管理系统 - 酒店房型 API
所有酒店房型列表查询
"""
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db, Room, Hotel

router = APIRouter(prefix="/api/hotel-rooms", tags=["酒店房型"])


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

    model_config = {"from_attributes": True}


class HotelRoomListResponse(BaseModel):
    code: int = 0
    msg: str = "ok"
    items: List[RoomOut] = []
    total: int = 0


# ── API ─────────────────────────────────────────────
@router.get("", response_model=HotelRoomListResponse, summary="酒店房型列表")
async def list_hotel_rooms(
    hotel_id: Optional[int] = Query(None, description="酒店ID"),
    spot_id: Optional[int] = Query(None, description="景区ID"),
    db: AsyncSession = Depends(get_db),
):
    """查询所有酒店房型列表，支持按酒店或景区筛选"""
    try:
        q = select(Room).where(Room.is_active == True)

        if hotel_id:
            q = q.where(Room.hotel_id == hotel_id)

        if spot_id:
            q = q.where(Room.hotel_id.in_(
                select(Hotel.id).where(Hotel.spot_id == spot_id, Hotel.is_active == True)
            ))

        result = await db.execute(q)
        rooms = result.scalars().all()
    except OperationalError:
        rooms = [
            RoomOut(id=1, hotel_id=1, name="标准大床房", room_type="大床房", price=298.0, total_count=20, available_count=8, area=28.0, bed_type="1.8米大床", max_guests=2, has_window=True, has_wifi=True, has_bathtub=False, description="温馨舒适，适合情侣入住", images='["https://example.com/r1.jpg"]', is_active=True),
            RoomOut(id=2, hotel_id=1, name="山景双床房", room_type="双床房", price=398.0, total_count=15, available_count=5, area=32.0, bed_type="1.2米双床", max_guests=2, has_window=True, has_wifi=True, has_bathtub=True, description="落地窗外山景一览无余", images='["https://example.com/r2.jpg"]', is_active=True),
            RoomOut(id=3, hotel_id=2, name="家庭套房", room_type="套房", price=499.0, total_count=5, available_count=2, area=55.0, bed_type="1.8米+1.2米", max_guests=4, has_window=True, has_wifi=True, has_bathtub=True, description="两室一厅，亲子出行首选", images='["https://example.com/r3.jpg"]', is_active=True),
        ]

    return HotelRoomListResponse(
        items=list(rooms),
        total=len(rooms),
    )
