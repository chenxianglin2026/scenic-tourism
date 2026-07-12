"""
景区智慧管理系统 - 房间 API
房间列表查询
"""
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
    db: AsyncSession = Depends(get_db),
):
    """查询房间列表，支持按酒店或景区筛选"""
    q = select(Room).where(Room.is_active == True)

    if hotel_id:
        q = q.where(Room.hotel_id == hotel_id)

    if spot_id:
        q = q.where(Room.hotel_id.in_(
            select(Hotel.id).where(Hotel.spot_id == spot_id, Hotel.is_active == True)
        ))

    result = await db.execute(q)
    rooms = result.scalars().all()

    return RoomListResponse(
        items=list(rooms),
        total=len(rooms),
    )
