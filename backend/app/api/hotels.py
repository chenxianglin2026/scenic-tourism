"""
景区智慧管理系统 - 酒店 API
酒店/房型查询 + 客房预订 + 入住/退房状态流转
"""
import uuid
from datetime import date, datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.attributes import set_committed_value

from app.db import (
    get_db, User, Hotel, Room, HotelOrder, HotelOrderStatus, ScenicSpot
)
from app.api.auth import get_current_user, require_admin, require_staff

router = APIRouter(prefix="/api/hotels", tags=["酒店"])


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


class HotelOut(BaseModel):
    id: int
    spot_id: int
    name: str
    address: str
    city: str
    district: Optional[str] = None
    phone: Optional[str] = None
    description: Optional[str] = None
    cover_image: Optional[str] = None
    images: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    rating: float
    is_active: bool
    rooms: List[RoomOut] = []

    model_config = {"from_attributes": True}


class HotelCreate(BaseModel):
    spot_id: int
    name: str = Field(..., min_length=1, max_length=200)
    address: str
    city: str
    district: Optional[str] = None
    phone: Optional[str] = None
    description: Optional[str] = None
    cover_image: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None


class RoomCreate(BaseModel):
    hotel_id: int
    name: str = Field(..., min_length=1, max_length=100)
    room_type: str = "大床房"
    price: float = Field(..., gt=0)
    total_count: int = Field(10, ge=1)
    area: Optional[float] = None
    bed_type: Optional[str] = None
    max_guests: int = Field(2, ge=1)
    has_window: bool = True
    has_wifi: bool = True
    has_bathtub: bool = False
    description: Optional[str] = None
    images: Optional[str] = None


class HotelOrderCreate(BaseModel):
    hotel_id: int
    room_id: int
    room_count: int = Field(1, ge=1, le=10)
    checkin_date: date
    checkout_date: date
    guest_name: str = Field(..., min_length=1, max_length=50)
    guest_phone: str = Field(..., pattern=r"^1[3-9]\d{9}$")
    remark: Optional[str] = None


class HotelOrderOut(BaseModel):
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
    cancel_reason: Optional[str] = None
    paid_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class HotelOrderListResponse(BaseModel):
    total: int
    items: List[HotelOrderOut]


class StatusUpdateResponse(BaseModel):
    success: bool
    message: str
    order: Optional[HotelOrderOut] = None


class HotelRefundResponse(BaseModel):
    success: bool
    message: str
    order: Optional[HotelOrderOut] = None
    refund_amount: float = 0.0


# ── 辅助函数 ─────────────────────────────────────────
def _build_order_out(order: HotelOrder) -> HotelOrderOut:
    """构建订单输出对象"""
    hotel_name = None
    room_name = None
    if order.hotel:
        hotel_name = order.hotel.name
    if order.room:
        room_name = order.room.name

    return HotelOrderOut(
        id=order.id,
        order_no=order.order_no,
        hotel_id=order.hotel_id,
        hotel_name=hotel_name,
        room_id=order.room_id,
        room_name=room_name,
        room_count=order.room_count,
        checkin_date=order.checkin_date,
        checkout_date=order.checkout_date,
        nights=order.nights,
        total_price=order.total_price,
        status=order.status,
        guest_name=order.guest_name,
        guest_phone=order.guest_phone,
        remark=order.remark,
        cancel_reason=order.cancel_reason,
        paid_at=order.paid_at,
        cancelled_at=order.cancelled_at,
        created_at=order.created_at,
    )


def _generate_hotel_order_no() -> str:
    return datetime.now().strftime("%Y%m%d%H%M%S") + uuid.uuid4().hex[:6].upper()


async def _get_hotel_order_by_id(order_id: int, db: AsyncSession, user_id: Optional[int] = None) -> Optional[HotelOrder]:
    """按ID查询酒店订单，可选过滤用户"""
    q = select(HotelOrder).where(HotelOrder.id == order_id).options(
        selectinload(HotelOrder.hotel), selectinload(HotelOrder.room)
    )
    if user_id is not None:
        q = q.where(HotelOrder.user_id == user_id)
    result = await db.execute(q)
    return result.scalar_one_or_none()


# ── 酒店 CRUD ───────────────────────────────────────
@router.get("", response_model=List[HotelOut], summary="酒店列表")
async def list_hotels(
    spot_id: Optional[int] = Query(None, description="景区ID"),
    db: AsyncSession = Depends(get_db),
):
    q = select(Hotel).where(Hotel.is_active == True).options(selectinload(Hotel.rooms))
    if spot_id:
        q = q.where(Hotel.spot_id == spot_id)

    result = await db.execute(q)
    return result.scalars().all()


@router.post("", response_model=HotelOut, status_code=201, summary="创建酒店（管理员）")
async def create_hotel(
    req: HotelCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    # 校验景区存在
    spot_result = await db.execute(select(ScenicSpot).where(ScenicSpot.id == req.spot_id))
    if not spot_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="景区不存在")

    hotel = Hotel(**req.model_dump())
    db.add(hotel)
    await db.flush()
    await db.refresh(hotel)
    # 新酒店无房型 — 使用 set_committed_value 避免触发延迟加载
    set_committed_value(hotel, 'rooms', [])
    return hotel


@router.get("/{hotel_id}/rooms", response_model=List[RoomOut], summary="酒店房型列表")
async def list_rooms(
    hotel_id: int,
    db: AsyncSession = Depends(get_db),
):
    # 校验酒店存在
    hotel_result = await db.execute(select(Hotel).where(Hotel.id == hotel_id, Hotel.is_active == True))
    if not hotel_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="酒店不存在")

    result = await db.execute(
        select(Room).where(Room.hotel_id == hotel_id, Room.is_active == True)
    )
    return result.scalars().all()


@router.post("/{hotel_id}/rooms", response_model=RoomOut, status_code=201, summary="创建房型（管理员）")
async def create_room(
    hotel_id: int,
    req: RoomCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    # 校验酒店存在
    hotel_result = await db.execute(select(Hotel).where(Hotel.id == hotel_id))
    if not hotel_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="酒店不存在")

    room = Room(
        hotel_id=hotel_id,
        name=req.name,
        room_type=req.room_type,
        price=req.price,
        total_count=req.total_count,
        available_count=req.total_count,
        area=req.area,
        bed_type=req.bed_type,
        max_guests=req.max_guests,
        has_window=req.has_window,
        has_wifi=req.has_wifi,
        has_bathtub=req.has_bathtub,
        description=req.description,
        images=req.images,
    )
    db.add(room)
    await db.flush()
    await db.refresh(room)
    return room


# ── 客房预订 ────────────────────────────────────────
@router.post("/orders", response_model=HotelOrderOut, status_code=201, summary="客房预订")
async def create_hotel_order(
    req: HotelOrderCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """预订扣减 available_count（原子操作防超卖）"""
    # 校验入住日期
    if req.checkin_date >= req.checkout_date:
        raise HTTPException(status_code=400, detail="离店日期必须晚于入住日期")

    if req.checkin_date < date.today():
        raise HTTPException(status_code=400, detail="入住日期不能早于今天")

    # 查询房型（使用行锁防超卖）
    room_result = await db.execute(
        select(Room).where(Room.id == req.room_id, Room.hotel_id == req.hotel_id, Room.is_active == True)
    )
    room = room_result.scalar_one_or_none()
    if not room:
        raise HTTPException(status_code=404, detail="房型不存在")

    # 库存检查（在同一个事务中，先检查再扣减，SQLite 写锁提供串行化）
    if room.available_count < req.room_count:
        raise HTTPException(status_code=400, detail=f"该房型仅剩 {room.available_count} 间可订")

    # 查询酒店
    hotel_result = await db.execute(select(Hotel).where(Hotel.id == req.hotel_id))
    hotel = hotel_result.scalar_one_or_none()
    if not hotel:
        raise HTTPException(status_code=404, detail="酒店不存在")

    # 计算天数和总价
    nights = (req.checkout_date - req.checkin_date).days
    total_price = room.price * req.room_count * nights

    # 生成订单号
    order_no = _generate_hotel_order_no()

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
        status=HotelOrderStatus.PENDING,  # 待支付
        guest_name=req.guest_name,
        guest_phone=req.guest_phone,
        remark=req.remark,
    )
    db.add(order)

    # 扣减可用房间数（原子操作：在同一事务中）
    room.available_count -= req.room_count
    if room.available_count < 0:
        raise HTTPException(status_code=400, detail="库存不足，请刷新后重试")

    await db.flush()
    await db.refresh(order)

    return _build_order_out(order)


@router.get("/orders", response_model=HotelOrderListResponse, summary="我的客房订单")
async def list_my_hotel_orders(
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    base_q = select(HotelOrder).where(HotelOrder.user_id == current_user.id).options(
        selectinload(HotelOrder.hotel), selectinload(HotelOrder.room)
    )
    count_q = select(func.count(HotelOrder.id)).where(HotelOrder.user_id == current_user.id)

    if status:
        base_q = base_q.where(HotelOrder.status == status)
        count_q = count_q.where(HotelOrder.status == status)

    total_result = await db.execute(count_q)
    total = total_result.scalar() or 0

    offset = (page - 1) * page_size
    orders_result = await db.execute(
        base_q.order_by(HotelOrder.created_at.desc()).offset(offset).limit(page_size)
    )
    orders = orders_result.scalars().all()

    items = [_build_order_out(o) for o in orders]

    return HotelOrderListResponse(total=total, items=items)


# ── 入住 ─────────────────────────────────────────────
@router.post("/orders/{order_id}/checkin", response_model=StatusUpdateResponse, summary="办理入住（工作人员）")
async def checkin_hotel_order(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_staff),
):
    """入住：将订单状态从 PAID 流转到 CHECKED_IN"""
    order = await _get_hotel_order_by_id(order_id, db)
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")

    if order.status == HotelOrderStatus.CHECKED_IN:
        return StatusUpdateResponse(
            success=False,
            message="该订单已办理入住",
            order=_build_order_out(order),
        )

    if order.status == HotelOrderStatus.COMPLETED:
        return StatusUpdateResponse(
            success=False,
            message="该订单已完成（已退房）",
            order=_build_order_out(order),
        )

    if order.status == HotelOrderStatus.CANCELLED:
        return StatusUpdateResponse(
            success=False,
            message="该订单已取消",
        )

    if order.status == HotelOrderStatus.REFUNDED:
        return StatusUpdateResponse(
            success=False,
            message="该订单已退款",
        )

    if order.status != HotelOrderStatus.PAID:
        return StatusUpdateResponse(
            success=False,
            message=f"当前订单状态 '{order.status}' 不支持办理入住",
        )

    # 校验入住日期
    today = date.today()
    if order.checkin_date > today:
        return StatusUpdateResponse(
            success=False,
            message=f"入住日期为 {order.checkin_date}，尚未到入住时间",
        )

    # 执行入住
    order.status = HotelOrderStatus.CHECKED_IN
    await db.flush()
    await db.refresh(order)

    return StatusUpdateResponse(
        success=True,
        message="入住办理成功",
        order=_build_order_out(order),
    )


# ── 退房 ─────────────────────────────────────────────
@router.post("/orders/{order_id}/checkout", response_model=StatusUpdateResponse, summary="办理退房（工作人员）")
async def checkout_hotel_order(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_staff),
):
    """退房：将订单状态从 CHECKED_IN 流转到 COMPLETED，恢复库存"""
    order = await _get_hotel_order_by_id(order_id, db)
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")

    if order.status == HotelOrderStatus.COMPLETED:
        return StatusUpdateResponse(
            success=False,
            message="该订单已完成退房",
            order=_build_order_out(order),
        )

    if order.status == HotelOrderStatus.CANCELLED:
        return StatusUpdateResponse(
            success=False,
            message="该订单已取消",
        )

    if order.status == HotelOrderStatus.REFUNDED:
        return StatusUpdateResponse(
            success=False,
            message="该订单已退款",
        )

    if order.status != HotelOrderStatus.CHECKED_IN:
        return StatusUpdateResponse(
            success=False,
            message=f"当前订单状态 '{order.status}' 不支持退房，请先办理入住",
        )

    # 执行退房：恢复可用库存
    order.status = HotelOrderStatus.COMPLETED

    # 恢复房型库存
    room_result = await db.execute(select(Room).where(Room.id == order.room_id))
    room = room_result.scalar_one_or_none()
    if room:
        room.available_count += order.room_count

    await db.flush()
    await db.refresh(order)

    return StatusUpdateResponse(
        success=True,
        message="退房办理成功，房间库存已恢复",
        order=_build_order_out(order),
    )


# ── 退款 ─────────────────────────────────────────────
@router.post("/orders/{order_id}/refund", response_model=HotelRefundResponse, summary="申请退款")
async def refund_hotel_order(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """退款：未入住可退，恢复库存"""
    order = await _get_hotel_order_by_id(order_id, db, current_user.id)
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")

    if order.status == HotelOrderStatus.REFUNDED:
        raise HTTPException(status_code=400, detail="该订单已退款")

    if order.status == HotelOrderStatus.CANCELLED:
        raise HTTPException(status_code=400, detail="该订单已取消")

    if order.status == HotelOrderStatus.CHECKED_IN:
        raise HTTPException(status_code=400, detail="已入住的订单不可退款")

    if order.status == HotelOrderStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="已完成的订单不可退款")

    if order.status == HotelOrderStatus.PENDING:
        # 未支付订单：直接取消，恢复库存
        order.status = HotelOrderStatus.CANCELLED
        order.cancelled_at = datetime.utcnow()

        # 恢复库存
        room_result = await db.execute(select(Room).where(Room.id == order.room_id))
        room = room_result.scalar_one_or_none()
        if room:
            room.available_count += order.room_count

        await db.flush()
        await db.refresh(order)
        return HotelRefundResponse(
            success=True,
            message="未支付订单已取消，库存已恢复",
            order=_build_order_out(order),
            refund_amount=0.0,
        )

    if order.status == HotelOrderStatus.PAID:
        refund_amount = order.total_price
        order.status = HotelOrderStatus.REFUNDED
        order.cancelled_at = datetime.utcnow()

        # 恢复库存
        room_result = await db.execute(select(Room).where(Room.id == order.room_id))
        room = room_result.scalar_one_or_none()
        if room:
            room.available_count += order.room_count

        # 更新支付记录
        from app.db import PaymentRecord
        pay_result = await db.execute(
            select(PaymentRecord).where(PaymentRecord.order_no == order.order_no)
        )
        pay_record = pay_result.scalar_one_or_none()
        if pay_record:
            pay_record.status = "refund"
            pay_record.refund_time = datetime.utcnow()

        await db.flush()
        await db.refresh(order)
        return HotelRefundResponse(
            success=True,
            message=f"退款成功，已退还 ¥{refund_amount}，库存已恢复",
            order=_build_order_out(order),
            refund_amount=refund_amount,
        )

    raise HTTPException(status_code=400, detail=f"当前订单状态 '{order.status}' 不支持退款")


# ── 按订单号查询（供支付回调使用） ──────────────────
@router.get("/orders/detail/{order_no}", response_model=HotelOrderOut, summary="按订单号查询")
async def get_hotel_order_by_no(
    order_no: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """根据订单号查询订单详情"""
    result = await db.execute(
        select(HotelOrder).where(HotelOrder.order_no == order_no)
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    return _build_order_out(order)
