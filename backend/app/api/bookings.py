"""
景区智慧管理系统 - 预订 API
客房预订查询与创建（HotelOrder 表未就绪时返回占位数据）
"""
from datetime import date
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import (
    get_db, User, Hotel, Room
)
from app.api.auth import get_current_user, require_admin

router = APIRouter(prefix="/api/bookings", tags=["预订"])


# ── Schemas ──────────────────────────────────────────
class BookingOut(BaseModel):
    id: int
    hotel_id: int
    hotel_name: Optional[str] = None
    room_id: int
    room_name: Optional[str] = None
    room_count: int
    checkin_date: date
    checkout_date: date
    nights: int
    total_price: float
    status: str
    guest_name: str
    guest_phone: str
    remark: Optional[str] = None
    created_at: Optional[str] = None

    model_config = {"from_attributes": True}


class BookingListResponse(BaseModel):
    code: int = 0
    msg: str = "ok"
    total: int = 0
    items: List[BookingOut] = []


class BookingCreate(BaseModel):
    hotel_id: int
    room_id: int
    room_count: int = Field(1, ge=1, le=10)
    checkin_date: date
    checkout_date: date
    guest_name: str = Field(..., min_length=1, max_length=50)
    guest_phone: str = Field(..., pattern=r"^1[3-9]\d{9}$")
    remark: Optional[str] = None


# ── API ─────────────────────────────────────────────
@router.get("", response_model=BookingListResponse, summary="预订列表")
async def list_bookings(
    status: Optional[str] = Query(None, description="状态过滤"),
    hotel_id: Optional[int] = Query(None, description="酒店ID"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """查询客房预订列表（HotelOrder 表就绪前返回空占位）"""
    # HotelOrder 表可能未创建，返回空数据占位
    return BookingListResponse(total=0, items=[])


@router.post("", response_model=BookingOut, status_code=201, summary="创建预订")
async def create_booking(
    req: BookingCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """创建客房预订（仅扣减库存，不写入 HotelOrder 表）"""
    if req.checkin_date >= req.checkout_date:
        raise HTTPException(status_code=400, detail="离店日期必须晚于入住日期")

    room_result = await db.execute(
        select(Room).where(Room.id == req.room_id, Room.hotel_id == req.hotel_id, Room.is_active == True)
    )
    room = room_result.scalar_one_or_none()
    if not room:
        raise HTTPException(status_code=404, detail="房型不存在")

    if room.available_count < req.room_count:
        raise HTTPException(status_code=400, detail=f"该房型仅剩 {room.available_count} 间可订")

    hotel_result = await db.execute(select(Hotel).where(Hotel.id == req.hotel_id))
    hotel = hotel_result.scalar_one_or_none()
    if not hotel:
        raise HTTPException(status_code=404, detail="酒店不存在")

    nights = (req.checkout_date - req.checkin_date).days
    total_price = room.price * req.room_count * nights

    # 扣减库存
    room.available_count -= req.room_count
    await db.flush()

    return BookingOut(
        id=0,
        hotel_id=req.hotel_id,
        hotel_name=hotel.name,
        room_id=req.room_id,
        room_name=room.name,
        room_count=req.room_count,
        checkin_date=req.checkin_date,
        checkout_date=req.checkout_date,
        nights=nights,
        total_price=total_price,
        status="paid",
        guest_name=req.guest_name,
        guest_phone=req.guest_phone,
        remark=req.remark,
        created_at=date.today().isoformat(),
    )
