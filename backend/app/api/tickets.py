"""
景区智慧管理系统 - 票务 API
票种管理 / 购票 / 我的票 / 核销验票 / 退款
"""
import uuid
from datetime import date, datetime, timedelta
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import (
    get_db, User, ScenicSpot, TicketType, TicketOrder, TicketInventory,
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
    cancelled_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class TicketOrderListResponse(BaseModel):
    total: int
    items: List[TicketOrderOut]


class VerifyRequest(BaseModel):
    qr_token: Optional[str] = Field(None, description="二维码token")
    ticket_no: Optional[str] = Field(None, description="票号/订单号")
    qr_code: Optional[str] = Field(None, description="二维码内容（与qr_token等价）")


class VerifyResponse(BaseModel):
    result: str  # success / already_verified / invalid_token / expired / cancelled
    message: str
    order: Optional[TicketOrderOut] = None


class RefundResponse(BaseModel):
    success: bool
    message: str
    order: Optional[TicketOrderOut] = None
    refund_amount: float = 0.0


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
    """购票下单：扣减库存（原子操作防超卖）、生成二维码token"""
    # 校验时间段
    _validate_time_slot(req.time_slot)

    # 校验游览日期不能是过去
    if req.visit_date < date.today():
        raise HTTPException(status_code=400, detail="游览日期不能早于今天")

    # 查询票种（行锁防超卖）
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

    # 原子库存扣减：使用 TicketInventory 表 + 乐观锁保证并发安全
    # 首次访问该时段时自动创建库存记录
    inv_result = await db.execute(
        select(TicketInventory).where(
            TicketInventory.ticket_type_id == req.ticket_type_id,
            TicketInventory.visit_date == req.visit_date,
            TicketInventory.time_slot == req.time_slot,
        )
    )
    inventory = inv_result.scalar_one_or_none()

    if not inventory:
        # 初始化库存记录（total_stock 取自票种配置）
        inventory = TicketInventory(
            ticket_type_id=req.ticket_type_id,
            visit_date=req.visit_date,
            time_slot=req.time_slot,
            total_stock=ticket_type.daily_stock,
            sold_count=0,
            version=0,
        )
        db.add(inventory)
        await db.flush()
        await db.refresh(inventory)

    # 原子扣减：UPDATE + version 乐观锁
    from sqlalchemy import update as sa_update
    old_version = inventory.version
    deduct_result = await db.execute(
        sa_update(TicketInventory)
        .where(
            TicketInventory.id == inventory.id,
            TicketInventory.version == old_version,
            TicketInventory.sold_count + req.quantity <= TicketInventory.total_stock,
        )
        .values(
            sold_count=TicketInventory.sold_count + req.quantity,
            version=TicketInventory.version + 1,
        )
    )
    if deduct_result.rowcount == 0:
        # 版本冲突或库存不足 — 重新读取确认原因
        await db.refresh(inventory)
        remaining = inventory.total_stock - inventory.sold_count
        if remaining < req.quantity:
            raise HTTPException(
                status_code=400,
                detail=f"该时段仅剩 {remaining} 张票，无法购买 {req.quantity} 张"
            )
        else:
            raise HTTPException(
                status_code=409,
                detail="系统繁忙，请稍后重试（库存并发冲突）"
            )

    # 刷新 inventory 以获取最新 sold_count
    await db.refresh(inventory)

    # 生成订单（状态为 PENDING，支付后变为 PAID）
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
        status=TicketOrderStatus.PENDING,
        visitor_name=req.visitor_name,
        visitor_phone=req.visitor_phone,
        visitor_id_card=req.visitor_id_card,
    )
    db.add(order)
    await db.flush()
    await db.refresh(order)

    return await _enrich_order(order, db)


async def _enrich_order(order: TicketOrder, db: AsyncSession) -> TicketOrderOut:
    """填充订单的关联名称（避免SQLAlchemy async lazy-loading）"""
    data = TicketOrderOut.model_validate(order)
    # Query ticket_type name from identity map instead of lazy-loading
    if order.ticket_type_id:
        tt_result = await db.execute(
            select(TicketType.name).where(TicketType.id == order.ticket_type_id)
        )
        tt_name = tt_result.scalar_one_or_none()
        if tt_name:
            data.ticket_type_name = tt_name
    # Query spot name explicitly
    if order.spot_id:
        spot_result = await db.execute(
            select(ScenicSpot.name).where(ScenicSpot.id == order.spot_id)
        )
        spot_name = spot_result.scalar_one_or_none()
        if spot_name:
            data.spot_name = spot_name
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
    """核销接口：验证qr_token/ticket_no/qr_code、检查状态（已核销/过期）、标记verified"""
    # 确定查询值
    lookup_value = req.qr_token or req.qr_code or req.ticket_no
    if not lookup_value:
        return VerifyResponse(
            result=VerifyResult.INVALID_TOKEN,
            message="请提供 qr_token、qr_code 或 ticket_no"
        )

    # 查找订单：先按 qr_token/qr_code 查，再按 ticket_no 查
    order_result = await db.execute(
        select(TicketOrder).where(TicketOrder.qr_token == lookup_value)
    )
    order = order_result.scalar_one_or_none()

    if not order and req.ticket_no:
        order_result = await db.execute(
            select(TicketOrder).where(TicketOrder.order_no == req.ticket_no)
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

    # 未支付的订单不能核销
    if order.status == TicketOrderStatus.PENDING:
        return VerifyResponse(
            result=VerifyResult.INVALID_TOKEN,
            message="该票尚未支付，无法核销",
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


async def _release_inventory(order: TicketOrder, db: AsyncSession):
    """原子释放 TicketInventory 库存（取消/退款时调用）"""
    from sqlalchemy import update as sa_update
    inv_result = await db.execute(
        select(TicketInventory).where(
            TicketInventory.ticket_type_id == order.ticket_type_id,
            TicketInventory.visit_date == order.visit_date,
            TicketInventory.time_slot == order.time_slot,
        )
    )
    inventory = inv_result.scalar_one_or_none()
    if inventory and inventory.sold_count >= order.quantity:
        await db.execute(
            sa_update(TicketInventory)
            .where(
                TicketInventory.id == inventory.id,
                TicketInventory.sold_count >= order.quantity,
            )
            .values(
                sold_count=TicketInventory.sold_count - order.quantity,
                version=TicketInventory.version + 1,
            )
        )


# ── 退款 ─────────────────────────────────────────────
@router.post("/order/{order_id}/refund", response_model=RefundResponse, summary="申请退款")
async def refund_ticket_order(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """退款接口：未使用可退（已支付且游览日期未过）、过期自动退"""
    # 查询订单
    order_result = await db.execute(
        select(TicketOrder).where(
            TicketOrder.id == order_id,
            TicketOrder.user_id == current_user.id,
        )
    )
    order = order_result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")

    # 检查订单状态是否允许退款
    if order.status == TicketOrderStatus.REFUNDED:
        raise HTTPException(status_code=400, detail="该订单已退款")

    if order.status == TicketOrderStatus.CANCELLED:
        raise HTTPException(status_code=400, detail="该订单已取消")

    if order.status == TicketOrderStatus.VERIFIED:
        raise HTTPException(status_code=400, detail="已核销的票不可退款")

    if order.status == TicketOrderStatus.EXPIRED:
        raise HTTPException(status_code=400, detail="该票已过期，系统将自动退款")

    if order.status == TicketOrderStatus.PENDING:
        # 未支付订单直接取消 — 释放库存
        order.status = TicketOrderStatus.CANCELLED
        order.cancelled_at = datetime.utcnow()
        # 释放 TicketInventory 库存
        await _release_inventory(order, db)
        await db.flush()
        await db.refresh(order)
        return RefundResponse(
            success=True,
            message="未支付订单已取消",
            order=await _enrich_order(order, db),
            refund_amount=0.0,
        )

    # 已支付但游览日期已过：过期自动退
    today = date.today()
    if order.status == TicketOrderStatus.PAID and order.visit_date <= today:
        order.status = TicketOrderStatus.EXPIRED
        order.cancelled_at = datetime.utcnow()
        # 自动退款（全款）
        refund_amount = order.total_price
        order.status = TicketOrderStatus.REFUNDED
        # 释放库存
        await _release_inventory(order, db)
        await db.flush()
        await db.refresh(order)

        # 同步更新支付记录
        from app.db import PaymentRecord
        pay_result = await db.execute(
            select(PaymentRecord).where(PaymentRecord.order_no == order.order_no)
        )
        pay_record = pay_result.scalar_one_or_none()
        if pay_record:
            pay_record.status = "refund"
            pay_record.refund_time = datetime.utcnow()

        await db.flush()
        return RefundResponse(
            success=True,
            message=f"游览日期 {order.visit_date} 已过，系统自动退款 ¥{refund_amount}",
            order=await _enrich_order(order, db),
            refund_amount=refund_amount,
        )

    # 已支付但未到游览日期：正常退款 — 进入审核流程
    if order.status == TicketOrderStatus.PAID:
        refund_amount = order.total_price
        order.status = TicketOrderStatus.REFUNDING
        order.cancelled_at = datetime.utcnow()

        # 同步更新支付记录为 refunding（待管理员审核）
        from app.db import PaymentRecord
        pay_result = await db.execute(
            select(PaymentRecord).where(PaymentRecord.order_no == order.order_no)
        )
        pay_record = pay_result.scalar_one_or_none()
        if pay_record and pay_record.status == "success":
            pay_record.status = "refunding"

        await db.flush()
        await db.refresh(order)
        return RefundResponse(
            success=True,
            message=f"退款申请已提交，¥{refund_amount}，等待管理员审核",
            order=await _enrich_order(order, db),
            refund_amount=refund_amount,
        )

    raise HTTPException(status_code=400, detail=f"当前订单状态 '{order.status}' 不支持退款")


# ── 获取单张票详情（供支付回调使用） ──────────────────
@router.get("/order/{order_no}", response_model=TicketOrderOut, summary="按订单号查询")
async def get_ticket_order_by_no(
    order_no: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """根据订单号查询订单详情"""
    result = await db.execute(
        select(TicketOrder).where(TicketOrder.order_no == order_no)
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    return await _enrich_order(order, db)


# ── 批量过期处理（管理端/定时任务调用） ──────────────
@router.post("/batch-expire", summary="批量过期处理（管理员）")
async def batch_expire_orders(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """将已过游览日期但状态仍为 PAID 的订单标记为 EXPIRED 并自动退款"""
    today = date.today()

    result = await db.execute(
        select(TicketOrder).where(
            TicketOrder.status == TicketOrderStatus.PAID,
            TicketOrder.visit_date < today,
        )
    )
    expired_orders = result.scalars().all()

    count = 0
    for order in expired_orders:
        order.status = TicketOrderStatus.EXPIRED
        order.cancelled_at = datetime.utcnow()
        # 再转为已退款
        order.status = TicketOrderStatus.REFUNDED
        # 释放库存
        await _release_inventory(order, db)

        # 更新支付记录
        from app.db import PaymentRecord
        pay_result = await db.execute(
            select(PaymentRecord).where(PaymentRecord.order_no == order.order_no)
        )
        pay_record = pay_result.scalar_one_or_none()
        if pay_record:
            pay_record.status = "refund"
            pay_record.refund_time = datetime.utcnow()
        count += 1

    await db.flush()

    return {
        "success": True,
        "message": f"已处理 {count} 张过期票",
        "expired_count": count,
    }
