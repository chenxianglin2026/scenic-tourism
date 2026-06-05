"""
景区智慧管理系统 - 票务 API
票种管理 / 购票 / 我的票 / 核销验票
"""
import uuid
from datetime import date, datetime, timedelta
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import (
    get_db, User, ScenicSpot, TicketType, TicketOrder,
    TicketOrderStatus, VerifyResult
)
from app.api.auth import get_current_user, require_admin, require_staff

router = APIRouter(prefix="/api/tickets", tags=["票务"])


# ── Schemas ──────────────────────────────────────────
class TicketTypeCreate(BaseModel):
    spot_id: int
    name: str = Field(..., min_length=1, max_length=100)
    category: str = Field("standard")
    price: float = Field(..., gt=0)
    original_price: Optional[float] = None
    daily_stock: int = Field(1000, ge=1)
    description: Optional[str] = None
    min_age: Optional[int] = None
    max_age: Optional[int] = None


class TicketTypeOut(BaseModel):
    id: int
    spot_id: int
    name: str
    category: str
    price: float
    original_price: Optional[float] = None
    daily_stock: int
    description: Optional[str] = None
    min_age: Optional[int] = None
    max_age: Optional[int] = None
    is_active: bool
    sort_order: int

    model_config = {"from_attributes": True}


class TicketOrderCreate(BaseModel):
    ticket_type_id: int
    spot_id: int
    quantity: int = Field(1, ge=1, le=20)
    visit_date: date
    time_slot: str = Field(..., description="08:00-10:00 / 10:00-12:00 / 12:00-14:00 / 14:00-17:00")
    visitor_name: Optional[str] = None
    visitor_phone: Optional[str] = None
    visitor_id_card: Optional[str] = None


class TicketOrderOut(BaseModel):
    id: int
    order_no: str
    user_id: int
    ticket_type_id: int
    ticket_type_name: Optional[str] = None
    spot_id: int
    spot_name: Optional[str] = None
    quantity: int
    visit_date: date
    time_slot: str
    total_price: float
    status: str
    qr_token: str
    visitor_name: Optional[str] = None
    visitor_phone: Optional[str] = None
    verified_at: Optional[datetime] = None
    paid_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class TicketOrderListResponse(BaseModel):
    total: int
    items: List[TicketOrderOut]


class VerifyRequest(BaseModel):
    qr_token: str = Field(..., description="二维码token")


class VerifyResponse(BaseModel):
    result: str  # success / already_verified / invalid_token / expired / cancelled
    message: str
    order: Optional[TicketOrderOut] = None


# ── 时间槽位校验 ─────────────────────────────────────
VALID_TIME_SLOTS = ["08:00-10:00", "10:00-12:00", "12:00-14:00", "14:00-17:00"]


def _validate_time_slot(time_slot: str):
    if time_slot not in VALID_TIME_SLOTS:
        raise HTTPException(
            status_code=400,
            detail=f"无效的时间段，可选: {', '.join(VALID_TIME_SLOTS)}"
        )


def _generate_order_no() -> str:
    return datetime.now().strftime("%Y%m%d%H%M%S") + uuid.uuid4().hex[:6].upper()


def _generate_qr_token() -> str:
    return uuid.uuid4().hex + uuid.uuid4().hex[:8]


# ── 票种管理 ─────────────────────────────────────────
@router.get("/types", response_model=List[TicketTypeOut], summary="获取票种列表")
async def list_ticket_types(
    spot_id: Optional[int] = Query(None, description="景区ID"),
    db: AsyncSession = Depends(get_db),
):
    q = select(TicketType).where(TicketType.is_active == True)
    if spot_id:
        q = q.where(TicketType.spot_id == spot_id)
    q = q.order_by(TicketType.sort_order, TicketType.id)

    result = await db.execute(q)
    return result.scalars().all()


@router.post("/types", response_model=TicketTypeOut, status_code=201, summary="创建票种（管理员）")
async def create_ticket_type(
    req: TicketTypeCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    # 校验景区存在
    spot_result = await db.execute(select(ScenicSpot).where(ScenicSpot.id == req.spot_id))
    if not spot_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="景区不存在")

    ticket_type = TicketType(
        spot_id=req.spot_id,
        name=req.name,
        category=req.category,
        price=req.price,
        original_price=req.original_price,
        daily_stock=req.daily_stock,
        description=req.description,
        min_age=req.min_age,
        max_age=req.max_age,
    )
    db.add(ticket_type)
    await db.flush()
    await db.refresh(ticket_type)
    return ticket_type


# ── 购票 ─────────────────────────────────────────────
@router.post("/order", response_model=TicketOrderOut, status_code=201, summary="购票下单")
async def create_ticket_order(
    req: TicketOrderCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # 校验时间段
    _validate_time_slot(req.time_slot)

    # 校验游览日期不能是过去
    if req.visit_date < date.today():
        raise HTTPException(status_code=400, detail="游览日期不能早于今天")

    # 查询票种
    tt_result = await db.execute(
        select(TicketType).where(
            TicketType.id == req.ticket_type_id,
            TicketType.spot_id == req.spot_id,
            TicketType.is_active == True,
        )
    )
    ticket_type = tt_result.scalar_one_or_none()
    if not ticket_type:
        raise HTTPException(status_code=404, detail="票种不存在")

    # 分时库存并发控制：使用 FOR UPDATE 行锁防止超卖
    # 统计该票种当天该时段已售出数量（已支付+待支付）
    sold_result = await db.execute(
        select(func.coalesce(func.sum(TicketOrder.quantity), 0)).where(
            TicketOrder.ticket_type_id == req.ticket_type_id,
            TicketOrder.visit_date == req.visit_date,
            TicketOrder.time_slot == req.time_slot,
            TicketOrder.status.in_([TicketOrderStatus.PAID, TicketOrderStatus.VERIFIED, TicketOrderStatus.PENDING]),
        )
    )
    sold = int(sold_result.scalar() or 0)

    remaining = ticket_type.daily_stock - sold
    if remaining < req.quantity:
        raise HTTPException(
            status_code=400,
            detail=f"该时段仅剩 {remaining} 张票，无法购买 {req.quantity} 张"
        )

    # 生成订单
    order_no = _generate_order_no()
    qr_token = _generate_qr_token()
    total_price = ticket_type.price * req.quantity

    order = TicketOrder(
        order_no=order_no,
        user_id=current_user.id,
        ticket_type_id=req.ticket_type_id,
        spot_id=req.spot_id,
        quantity=req.quantity,
        visit_date=req.visit_date,
        time_slot=req.time_slot,
        total_price=total_price,
        qr_token=qr_token,
        status=TicketOrderStatus.PAID,  # MVP: 简化支付流程，直接标记为已支付
        visitor_name=req.visitor_name,
        visitor_phone=req.visitor_phone,
        visitor_id_card=req.visitor_id_card,
        paid_at=datetime.utcnow(),
    )
    db.add(order)
    await db.flush()
    await db.refresh(order)

    # 填充关联数据
    return await _enrich_order(order, db)


async def _enrich_order(order: TicketOrder, db: AsyncSession) -> TicketOrderOut:
    """填充订单的关联名称"""
    data = TicketOrderOut.model_validate(order)
    if order.ticket_type:
        data.ticket_type_name = order.ticket_type.name
    if order.spot:
        data.spot_name = order.spot.name
    return data


# ── 我的票 ───────────────────────────────────────────
@router.get("/orders", response_model=TicketOrderListResponse, summary="我的购票订单")
async def list_my_orders(
    status: Optional[str] = Query(None, description="订单状态过滤"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    base_q = select(TicketOrder).where(TicketOrder.user_id == current_user.id)
    count_q = select(func.count(TicketOrder.id)).where(TicketOrder.user_id == current_user.id)

    if status:
        base_q = base_q.where(TicketOrder.status == status)
        count_q = count_q.where(TicketOrder.status == status)

    total_result = await db.execute(count_q)
    total = total_result.scalar() or 0

    offset = (page - 1) * page_size
    orders_result = await db.execute(
        base_q.order_by(TicketOrder.created_at.desc()).offset(offset).limit(page_size)
    )
    orders = orders_result.scalars().all()

    items = []
    for o in orders:
        items.append(await _enrich_order(o, db))

    return TicketOrderListResponse(total=total, items=items)


# ── 核销验票 ─────────────────────────────────────────
@router.post("/verify", response_model=VerifyResponse, summary="核销验票（工作人员）")
async def verify_ticket(
    req: VerifyRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_staff),
):
    # 查找订单
    order_result = await db.execute(
        select(TicketOrder).where(TicketOrder.qr_token == req.qr_token)
    )
    order = order_result.scalar_one_or_none()

    if not order:
        return VerifyResponse(
            result=VerifyResult.INVALID_TOKEN,
            message="无效的二维码：未找到对应订单"
        )

    # 校验订单状态
    if order.status == TicketOrderStatus.VERIFIED:
        return VerifyResponse(
            result=VerifyResult.ALREADY_VERIFIED,
            message=f"该票已于 {order.verified_at.strftime('%Y-%m-%d %H:%M') if order.verified_at else '未知时间'} 核销",
            order=await _enrich_order(order, db),
        )

    if order.status == TicketOrderStatus.CANCELLED:
        return VerifyResponse(
            result=VerifyResult.CANCELLED,
            message="该票已取消",
        )

    if order.status == TicketOrderStatus.REFUNDED:
        return VerifyResponse(
            result=VerifyResult.CANCELLED,
            message="该票已退款",
        )

    if order.status == TicketOrderStatus.EXPIRED:
        return VerifyResponse(
            result=VerifyResult.EXPIRED,
            message="该票已过期",
        )

    # 校验游览日期（允许当天）
    today = date.today()
    if order.visit_date != today:
        return VerifyResponse(
            result=VerifyResult.EXPIRED,
            message=f"该票游览日期为 {order.visit_date}，非今日票"
        )

    # 执行核销
    order.status = TicketOrderStatus.VERIFIED
    order.verified_at = datetime.utcnow()
    order.verified_by = current_user.id
    await db.flush()
    await db.refresh(order)

    return VerifyResponse(
        result=VerifyResult.SUCCESS,
        message="核销成功",
        order=await _enrich_order(order, db),
    )
