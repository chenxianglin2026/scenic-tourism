"""
景区智慧管理系统 - 预订 API
客房预订查询与创建
"""
from datetime import date
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import (
    get_db, User, Hotel, Room, HotelOrder, HotelOrderStatus
)
from app.api.auth import get_current_user, require_admin

router = APIRouter(prefix="/api/bookings", tags=["预订"])


# ── Schemas ──────────────────────────────────────────
class BookingOut(BaseModel):
    id: int
    order_no: str
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
    created_at: Optional[date] = None

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


# ── 辅助函数 ─────────────────────────────────────────
def _build_booking_out(order: HotelOrder) -> BookingOut:
    return BookingOut(
        id=order.id,
        order_no=order.order_no,
        hotel_id=order.hotel_id,
        hotel_name=order.hotel.name if order.hotel else None,
        room_id=order.room_id,
        room_name=order.room.name if order.room else None,
        room_count=order.room_count,
        checkin_date=order.checkin_date,
        checkout_date=order.checkout_date,
        nights=order.nights,
        total_price=order.total_price,
        status=order.status,
        guest_name=order.guest_name,
        guest_phone=order.guest_phone,
        remark=order.remark,
        created_at=order.created_at.date() if order.created_at else None,
    )


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
    """查询所有客房预订列表（管理员）"""
    base_q = select(HotelOrder).options(
        selectinload(HotelOrder.hotel), selectinload(HotelOrder.room)
    )
    count_q = select(func.count(HotelOrder.id))

    if status:
        base_q = base_q.where(HotelOrder.status == status)
        count_q = count_q.where(HotelOrder.status == status)
    if hotel_id:
        base_q = base_q.where(HotelOrder.hotel_id == hotel_id)
        count_q = count_q.where(HotelOrder.hotel_id == hotel_id)

    total_result = await db.execute(count_q)
    total = total_result.scalar() or 0

    offset = (page - 1) * page_size
    orders_result = await db.execute(
        base_q.order_by(HotelOrder.created_at.desc()).offset(offset).limit(page_size)
    )
    orders = orders_result.scalars().all()

    return BookingListResponse(
        total=total,
        items=[_build_booking_out(o) for o in orders],
    )


@router.post("", response_model=BookingOut, status_code=201, summary="创建预订")
async def create_booking(
    req: BookingCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """管理员创建客房预订"""
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

    import uuid
    from datetime import datetime
    order_no = datetime.now().strftime("%Y%m%d%H%M%S") + uuid.uuid4().hex[:6].upper()

    order = HotelOrder(
        order_no=order_no,
        user_id=current_user.id,
        hotel_id=req.hotel_id,
        room_id=req.room_id,
        room_count=req.room_count,
        checkin_date=req.checkin_date,
        checkout_date=req.checkout_date,
        nights=nights,
        total_price=total_price,
        status=HotelOrderStatus.PAID,
        guest_name=req.guest_name,
        guest_phone=req.guest_phone,
        remark=req.remark,
    )
    db.add(order)
    room.available_count -= req.room_count
    await db.flush()
    await db.refresh(order)

    return _build_booking_out(order)
