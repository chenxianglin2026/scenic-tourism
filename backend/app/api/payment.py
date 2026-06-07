"""
景区智慧管理系统 - 支付 API
微信JSAPI支付 + 回调 + 退款审核 + 超时自动取消
"""
import uuid
import json
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import (
    get_db, User, TicketOrder, TicketOrderStatus,
    HotelOrder, HotelOrderStatus, PaymentRecord, Room, ScenicSpot
)
from app.api.auth import get_current_user, require_admin

router = APIRouter(prefix="/api/payment", tags=["支付"])

# ── 超时配置 ─────────────────────────────────────────
PAYMENT_TIMEOUT_MINUTES = 30  # 支付超时分钟数


# ── Schemas ──────────────────────────────────────────
class PaymentCreateRequest(BaseModel):
    order_no: str = Field(..., description="订单号（票务或酒店订单号）")
    order_type: str = Field(..., description="ticket / hotel")


class PaymentCreateResponse(BaseModel):
    success: bool
    message: str
    # 微信JSAPI支付参数（DEV_MODE为mock数据）
    payment_params: Optional[dict] = None
    transaction_id: Optional[str] = None


class PaymentConfirmRequest(BaseModel):
    """DEV_MODE下确认支付"""
    transaction_id: str = Field(..., description="支付交易号")
    order_no: str = Field(..., description="商户订单号")


class PaymentConfirmResponse(BaseModel):
    success: bool
    message: str
    status: str  # success / failed


class PaymentCancelRequest(BaseModel):
    """用户主动取消未支付订单"""
    order_no: str = Field(..., description="订单号")
    order_type: str = Field(..., description="ticket / hotel")


class PaymentCancelResponse(BaseModel):
    success: bool
    message: str


class PaymentNotifyRequest(BaseModel):
    """微信支付回调请求（商户侧封装）"""
    transaction_id: str = Field(..., description="微信支付交易号")
    order_no: str = Field(..., description="商户订单号")
    order_type: str = Field("ticket", description="ticket / hotel")
    amount: float = Field(..., gt=0, description="支付金额（元）")
    result_code: str = Field("SUCCESS", description="SUCCESS / FAIL")
    raw_data: Optional[str] = Field(None, description="回调原始数据")


class PaymentNotifyResponse(BaseModel):
    return_code: str = "SUCCESS"
    return_msg: str = "OK"


class PaymentStatusResponse(BaseModel):
    order_no: str
    order_type: str
    transaction_id: Optional[str] = None
    status: str  # pending / success / failed / refund / refunding
    amount: float
    pay_time: Optional[datetime] = None
    expires_at: Optional[datetime] = None


class RefundApproveRequest(BaseModel):
    """管理员审核退款"""
    transaction_id: str = Field(..., description="支付交易号")
    approved: bool = Field(True, description="是否批准退款")
    reason: Optional[str] = Field(None, description="审核备注")


class RefundApproveResponse(BaseModel):
    success: bool
    message: str
    order_no: Optional[str] = None
    refund_amount: float = 0.0


# ── 内部辅助：释放库存 ─────────────────────────────────
async def _release_ticket_stock(order: TicketOrder, db: AsyncSession):
    """取消/退款票务订单时释放库存（不直接操作，标记取消即可，
       库存统计用 status 过滤，取消后不计入已售）"""
    pass  # 库存通过 status 过滤自动释放


async def _release_hotel_stock(order: HotelOrder, db: AsyncSession):
    """取消/退款酒店订单时恢复房型库存"""
    room_result = await db.execute(select(Room).where(Room.id == order.room_id))
    room = room_result.scalar_one_or_none()
    if room:
        room.available_count += order.room_count


async def _auto_cancel_single(payment: PaymentRecord, db: AsyncSession) -> dict:
    """自动取消单个超时支付记录，释放库存"""
    if payment.order_type == "ticket":
        order_result = await db.execute(
            select(TicketOrder).where(TicketOrder.order_no == payment.order_no)
        )
        biz_order = order_result.scalar_one_or_none()
        if biz_order and biz_order.status == TicketOrderStatus.PENDING:
            biz_order.status = TicketOrderStatus.CANCELLED
            biz_order.cancelled_at = datetime.utcnow()
            biz_order.remark = f"支付超时自动取消（{PAYMENT_TIMEOUT_MINUTES}分钟未支付）"
            await _release_ticket_stock(biz_order, db)
    else:
        order_result = await db.execute(
            select(HotelOrder).where(HotelOrder.order_no == payment.order_no)
        )
        biz_order = order_result.scalar_one_or_none()
        if biz_order and biz_order.status == HotelOrderStatus.PENDING:
            biz_order.status = HotelOrderStatus.CANCELLED
            biz_order.cancelled_at = datetime.utcnow()
            biz_order.cancel_reason = f"支付超时自动取消（{PAYMENT_TIMEOUT_MINUTES}分钟未支付）"
            await _release_hotel_stock(biz_order, db)

    payment.status = "cancelled"
    return {
        "order_no": payment.order_no,
        "order_type": payment.order_type,
        "transaction_id": payment.transaction_id,
    }


# ── 支付下单 ─────────────────────────────────────────
@router.post("/create", response_model=PaymentCreateResponse, summary="创建支付（微信JSAPI下单）")
async def create_payment(
    req: PaymentCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建支付订单，返回JSAPI调起参数"""
    # 校验 order_type
    if req.order_type not in ("ticket", "hotel"):
        raise HTTPException(status_code=400, detail="order_type 必须是 ticket 或 hotel")

    # 查询对应的业务订单
    if req.order_type == "ticket":
        result = await db.execute(
            select(TicketOrder).where(
                TicketOrder.order_no == req.order_no,
                TicketOrder.user_id == current_user.id,
            )
        )
        biz_order = result.scalar_one_or_none()
        if not biz_order:
            raise HTTPException(status_code=404, detail="票务订单不存在")
        if biz_order.status != TicketOrderStatus.PENDING:
            raise HTTPException(status_code=400, detail=f"订单状态 '{biz_order.status}' 不支持支付")
        pay_amount = biz_order.total_price
    else:  # hotel
        result = await db.execute(
            select(HotelOrder).where(
                HotelOrder.order_no == req.order_no,
                HotelOrder.user_id == current_user.id,
            )
        )
        biz_order = result.scalar_one_or_none()
        if not biz_order:
            raise HTTPException(status_code=404, detail="酒店订单不存在")
        if biz_order.status != HotelOrderStatus.PENDING:
            raise HTTPException(status_code=400, detail=f"订单状态 '{biz_order.status}' 不支持支付")
        pay_amount = biz_order.total_price

    # 检查是否已有支付记录
    exist_result = await db.execute(
        select(PaymentRecord).where(PaymentRecord.order_no == req.order_no)
    )
    existing = exist_result.scalar_one_or_none()
    if existing:
        if existing.status == "success":
            raise HTTPException(status_code=400, detail="该订单已支付成功")
        if existing.status == "pending":
            # 已有待支付记录，检查是否超时
            elapsed = datetime.utcnow() - existing.created_at
            if elapsed < timedelta(minutes=PAYMENT_TIMEOUT_MINUTES):
                raise HTTPException(status_code=400, detail="该订单已有待支付记录，请勿重复支付")
            # 超时了，取消旧记录
            existing.status = "cancelled"

    # 生成微信支付交易号
    transaction_id = "WX" + datetime.now().strftime("%Y%m%d%H%M%S") + uuid.uuid4().hex[:10].upper()

    # 创建待支付记录（DEV_MODE和生产模式统一为pending，由后续确认/回调完成支付）
    payment = PaymentRecord(
        order_no=req.order_no,
        order_type=req.order_type,
        transaction_id=transaction_id,
        amount=pay_amount,
        status="pending",
        pay_method="wechat_jsapi",
        prepay_id="prepay_" + uuid.uuid4().hex[:16],
    )
    db.add(payment)
    await db.flush()

    if settings.DEV_MODE:
        return PaymentCreateResponse(
            success=True,
            message=f"[DEV_MODE] 支付订单已创建，请调用 /api/payment/confirm 完成支付（模拟）。¥{pay_amount}，"
                      f"超时 {PAYMENT_TIMEOUT_MINUTES} 分钟未支付将自动取消。",
            transaction_id=transaction_id,
            payment_params={
                "appId": "wx_dev_mock_appid",
                "timeStamp": str(int(datetime.utcnow().timestamp())),
                "nonceStr": uuid.uuid4().hex[:16],
                "package": f"prepay_id={payment.prepay_id}",
                "signType": "MD5",
                "paySign": f"MOCK_SIGN_{uuid.uuid4().hex[:8]}",
                "_dev_note": "请使用 /api/payment/confirm 模拟支付确认",
            },
        )

    # 生产模式：返回JSAPI参数
    return PaymentCreateResponse(
        success=True,
        message=f"支付订单已创建，请调起微信支付（{PAYMENT_TIMEOUT_MINUTES}分钟内完成）",
        transaction_id=transaction_id,
        payment_params={
            "appId": settings.WX_APPID or "wx_dev_mock_appid",
            "timeStamp": str(int(datetime.utcnow().timestamp())),
            "nonceStr": uuid.uuid4().hex[:16],
            "package": f"prepay_id={payment.prepay_id}",
            "signType": "MD5",
            "paySign": "PROD_SIGNATURE_PLACEHOLDER",
        },
    )


# ── DEV_MODE 支付确认 ──────────────────────────────
@router.post("/confirm", response_model=PaymentConfirmResponse, summary="[DEV_MODE] 确认支付")
async def confirm_payment(
    req: PaymentConfirmRequest,
    db: AsyncSession = Depends(get_db),
):
    """DEV_MODE下模拟用户确认支付，完成完整的状态流转"""
    if not settings.DEV_MODE:
        raise HTTPException(status_code=400, detail="此接口仅在 DEV_MODE 下可用")

    # 查找支付记录
    pay_result = await db.execute(
        select(PaymentRecord).where(
            PaymentRecord.transaction_id == req.transaction_id,
            PaymentRecord.order_no == req.order_no,
        )
    )
    payment = pay_result.scalar_one_or_none()

    if not payment:
        raise HTTPException(status_code=404, detail="支付记录不存在")

    if payment.status == "success":
        return PaymentConfirmResponse(
            success=True,
            message="该支付已完成（幂等）",
            status="success",
        )

    if payment.status == "cancelled":
        raise HTTPException(status_code=400, detail="该支付已取消（可能已超时）")

    if payment.status != "pending":
        raise HTTPException(status_code=400, detail=f"支付状态 '{payment.status}' 不支持确认")

    # 检查是否超时
    elapsed = datetime.utcnow() - payment.created_at
    if elapsed > timedelta(minutes=PAYMENT_TIMEOUT_MINUTES):
        # 超时自动取消
        await _auto_cancel_single(payment, db)
        await db.flush()
        raise HTTPException(
            status_code=400,
            detail=f"支付已超时（{PAYMENT_TIMEOUT_MINUTES}分钟），订单已自动取消",
        )

    # 完成支付
    payment.status = "success"
    payment.pay_time = datetime.utcnow()

    # 更新业务订单状态
    if payment.order_type == "ticket":
        order_result = await db.execute(
            select(TicketOrder).where(TicketOrder.order_no == payment.order_no)
        )
        biz_order = order_result.scalar_one_or_none()
        if biz_order and biz_order.status == TicketOrderStatus.PENDING:
            biz_order.status = TicketOrderStatus.PAID
            biz_order.paid_at = datetime.utcnow()
    else:
        order_result = await db.execute(
            select(HotelOrder).where(HotelOrder.order_no == payment.order_no)
        )
        biz_order = order_result.scalar_one_or_none()
        if biz_order and biz_order.status == HotelOrderStatus.PENDING:
            biz_order.status = HotelOrderStatus.PAID
            biz_order.paid_at = datetime.utcnow()

    await db.flush()

    return PaymentConfirmResponse(
        success=True,
        message=f"[DEV_MODE] 支付确认成功，¥{payment.amount}",
        status="success",
    )


# ── 用户主动取消 ─────────────────────────────────────
@router.post("/cancel", response_model=PaymentCancelResponse, summary="取消未支付订单")
async def cancel_payment(
    req: PaymentCancelRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """用户主动取消未支付的订单，释放库存"""
    if req.order_type not in ("ticket", "hotel"):
        raise HTTPException(status_code=400, detail="order_type 必须是 ticket 或 hotel")

    # 查找支付记录
    pay_result = await db.execute(
        select(PaymentRecord).where(PaymentRecord.order_no == req.order_no)
    )
    payment = pay_result.scalar_one_or_none()

    if not payment:
        # 没有支付记录，可能未创建支付
        raise HTTPException(status_code=404, detail="未找到支付记录")

    if payment.status != "pending":
        raise HTTPException(status_code=400, detail=f"支付状态 '{payment.status}' 不支持取消")

    # 校验业务订单属于当前用户且状态为待支付
    if req.order_type == "ticket":
        order_result = await db.execute(
            select(TicketOrder).where(
                TicketOrder.order_no == req.order_no,
                TicketOrder.user_id == current_user.id,
            )
        )
        biz_order = order_result.scalar_one_or_none()
        if not biz_order:
            raise HTTPException(status_code=404, detail="票务订单不存在")
        if biz_order.status != TicketOrderStatus.PENDING:
            raise HTTPException(status_code=400, detail=f"订单状态 '{biz_order.status}' 不支持取消")
        biz_order.status = TicketOrderStatus.CANCELLED
        biz_order.cancelled_at = datetime.utcnow()
        biz_order.remark = "用户主动取消"
        await _release_ticket_stock(biz_order, db)
    else:
        order_result = await db.execute(
            select(HotelOrder).where(
                HotelOrder.order_no == req.order_no,
                HotelOrder.user_id == current_user.id,
            )
        )
        biz_order = order_result.scalar_one_or_none()
        if not biz_order:
            raise HTTPException(status_code=404, detail="酒店订单不存在")
        if biz_order.status != HotelOrderStatus.PENDING:
            raise HTTPException(status_code=400, detail=f"订单状态 '{biz_order.status}' 不支持取消")
        biz_order.status = HotelOrderStatus.CANCELLED
        biz_order.cancelled_at = datetime.utcnow()
        biz_order.cancel_reason = "用户主动取消"
        await _release_hotel_stock(biz_order, db)

    payment.status = "cancelled"
    await db.flush()

    return PaymentCancelResponse(
        success=True,
        message="订单已取消，库存已释放",
    )


# ── 支付回调 ─────────────────────────────────────────
@router.post("/notify", response_model=PaymentNotifyResponse, summary="微信支付回调通知")
async def payment_notify(
    req: PaymentNotifyRequest,
    db: AsyncSession = Depends(get_db),
):
    """接收微信支付回调，更新订单状态"""
    # 查找支付记录
    pay_result = await db.execute(
        select(PaymentRecord).where(PaymentRecord.order_no == req.order_no)
    )
    payment = pay_result.scalar_one_or_none()

    if payment and payment.status == "success":
        # 已经处理过
        return PaymentNotifyResponse(return_msg="订单已支付")

    if req.result_code != "SUCCESS":
        # 支付失败
        if not payment:
            payment = PaymentRecord(
                order_no=req.order_no,
                order_type=req.order_type,
                transaction_id=req.transaction_id,
                amount=req.amount,
                status="failed",
                pay_method="wechat_jsapi",
                raw_data=req.raw_data,
            )
            db.add(payment)
        else:
            payment.status = "failed"
            payment.raw_data = req.raw_data
        await db.flush()
        return PaymentNotifyResponse(return_code="FAIL", return_msg="支付失败")

    # 支付成功：创建/更新支付记录
    if not payment:
        payment = PaymentRecord(
            order_no=req.order_no,
            order_type=req.order_type,
            transaction_id=req.transaction_id,
            amount=req.amount,
            status="success",
            pay_method="wechat_jsapi",
            pay_time=datetime.utcnow(),
            raw_data=req.raw_data,
        )
        db.add(payment)
    else:
        payment.transaction_id = req.transaction_id
        payment.amount = req.amount
        payment.status = "success"
        payment.pay_time = datetime.utcnow()
        payment.raw_data = req.raw_data

    # 更新业务订单状态
    try:
        if req.order_type == "ticket":
            result = await db.execute(
                select(TicketOrder).where(TicketOrder.order_no == req.order_no)
            )
            biz_order = result.scalar_one_or_none()
            if biz_order and biz_order.status == TicketOrderStatus.PENDING:
                biz_order.status = TicketOrderStatus.PAID
                biz_order.paid_at = datetime.utcnow()
        else:  # hotel
            result = await db.execute(
                select(HotelOrder).where(HotelOrder.order_no == req.order_no)
            )
            biz_order = result.scalar_one_or_none()
            if biz_order and biz_order.status == HotelOrderStatus.PENDING:
                biz_order.status = HotelOrderStatus.PAID
                biz_order.paid_at = datetime.utcnow()
    except Exception as e:
        await db.rollback()
        return PaymentNotifyResponse(return_code="FAIL", return_msg=f"订单状态更新失败: {str(e)}")

    await db.flush()
    return PaymentNotifyResponse()


# ── 查询支付状态 ─────────────────────────────────────
@router.get("/status/{order_no}", response_model=PaymentStatusResponse, summary="查询支付状态")
async def get_payment_status(
    order_no: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """查询指定订单的支付状态"""
    result = await db.execute(
        select(PaymentRecord).where(PaymentRecord.order_no == order_no)
    )
    payment = result.scalar_one_or_none()

    if not payment:
        return PaymentStatusResponse(
            order_no=order_no,
            order_type="",
            status="pending",
            amount=0.0,
        )

    # 计算过期时间
    expires_at = payment.created_at + timedelta(minutes=PAYMENT_TIMEOUT_MINUTES) if payment.status == "pending" else None

    return PaymentStatusResponse(
        order_no=payment.order_no,
        order_type=payment.order_type,
        transaction_id=payment.transaction_id,
        status=payment.status,
        amount=payment.amount,
        pay_time=payment.pay_time,
        expires_at=expires_at,
    )


# ── 管理员退款审核 ───────────────────────────────────
@router.post("/refund/approve", response_model=RefundApproveResponse, summary="退款审核（管理员）")
async def approve_refund(
    req: RefundApproveRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """管理员审核退款申请：批准退款或拒绝退款"""
    # 查找支付记录
    pay_result = await db.execute(
        select(PaymentRecord).where(PaymentRecord.transaction_id == req.transaction_id)
    )
    payment = pay_result.scalar_one_or_none()

    if not payment:
        raise HTTPException(status_code=404, detail="支付记录不存在")

    if payment.status != "refunding":
        raise HTTPException(
            status_code=400,
            detail=f"支付状态 '{payment.status}' 不支持审核（需要 refunding 状态）",
        )

    if req.approved:
        # 批准退款
        payment.status = "refund"
        payment.refund_time = datetime.utcnow()

        # 更新业务订单状态
        if payment.order_type == "ticket":
            order_result = await db.execute(
                select(TicketOrder).where(TicketOrder.order_no == payment.order_no)
            )
            biz_order = order_result.scalar_one_or_none()
            if biz_order and biz_order.status == TicketOrderStatus.REFUNDING:
                biz_order.status = TicketOrderStatus.REFUNDED
                biz_order.cancelled_at = datetime.utcnow()
                await _release_ticket_stock(biz_order, db)
        else:
            order_result = await db.execute(
                select(HotelOrder).where(HotelOrder.order_no == payment.order_no)
            )
            biz_order = order_result.scalar_one_or_none()
            if biz_order and biz_order.status == HotelOrderStatus.REFUNDING:
                biz_order.status = HotelOrderStatus.REFUNDED
                biz_order.cancelled_at = datetime.utcnow()
                await _release_hotel_stock(biz_order, db)

        await db.flush()

        return RefundApproveResponse(
            success=True,
            message=f"退款已批准，¥{payment.amount} 已退还",
            order_no=payment.order_no,
            refund_amount=payment.amount,
        )
    else:
        # 拒绝退款：恢复为原来的已支付状态
        payment.status = "success"

        if payment.order_type == "ticket":
            order_result = await db.execute(
                select(TicketOrder).where(TicketOrder.order_no == payment.order_no)
            )
            biz_order = order_result.scalar_one_or_none()
            if biz_order and biz_order.status == TicketOrderStatus.REFUNDING:
                biz_order.status = TicketOrderStatus.PAID
        else:
            order_result = await db.execute(
                select(HotelOrder).where(HotelOrder.order_no == payment.order_no)
            )
            biz_order = order_result.scalar_one_or_none()
            if biz_order and biz_order.status == HotelOrderStatus.REFUNDING:
                biz_order.status = HotelOrderStatus.PAID

        await db.flush()

        return RefundApproveResponse(
            success=True,
            message=f"退款已拒绝: {req.reason or '管理员拒绝'}",
            order_no=payment.order_no,
            refund_amount=0.0,
        )


# ── 查询待审核退款列表（管理员） ──────────────────────
@router.get("/refund/pending", summary="待审核退款列表（管理员）")
async def list_pending_refunds(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """管理员查看所有待审核的退款申请"""
    count_q = select(PaymentRecord).where(PaymentRecord.status == "refunding")
    count_result = await db.execute(count_q)
    all_records = count_result.scalars().all()
    total = len(all_records)

    offset = (page - 1) * page_size
    q = select(PaymentRecord).where(PaymentRecord.status == "refunding").order_by(
        PaymentRecord.created_at.desc()
    ).offset(offset).limit(page_size)
    result = await db.execute(q)
    records = result.scalars().all()

    items = []
    for r in records:
        item = {
            "id": r.id,
            "order_no": r.order_no,
            "order_type": r.order_type,
            "transaction_id": r.transaction_id,
            "amount": r.amount,
            "status": r.status,
            "pay_method": r.pay_method,
            "pay_time": r.pay_time.isoformat() if r.pay_time else None,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        items.append(item)

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": items,
    }


# ── 自动取消（管理员触发 / 定时任务调用） ────────────
@router.post("/auto-cancel", summary="扫描并自动取消超时未支付订单")
async def auto_cancel_expired(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """扫描所有超时的待支付订单，自动取消并释放库存"""
    cutoff = datetime.utcnow() - timedelta(minutes=PAYMENT_TIMEOUT_MINUTES)

    result = await db.execute(
        select(PaymentRecord).where(
            PaymentRecord.status == "pending",
            PaymentRecord.created_at < cutoff,
        )
    )
    expired_payments = result.scalars().all()

    cancelled = []
    for payment in expired_payments:
        info = await _auto_cancel_single(payment, db)
        cancelled.append(info)

    await db.flush()

    return {
        "success": True,
        "message": f"已自动取消 {len(cancelled)} 个超时订单",
        "cancelled_count": len(cancelled),
        "items": cancelled,
    }
