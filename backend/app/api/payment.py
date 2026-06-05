"""
景区智慧管理系统 - 支付 API
微信JSAPI支付 + 回调（DEV_MODE下mock实现）
"""
import uuid
import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_db, User, TicketOrder, TicketOrderStatus, HotelOrder, HotelOrderStatus, PaymentRecord
from app.api.auth import get_current_user

router = APIRouter(prefix="/api/payment", tags=["支付"])


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
    status: str  # pending / success / failed / refund
    amount: float
    pay_time: Optional[datetime] = None


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
            raise HTTPException(status_code=400, detail=f"订单状态 {biz_order.status} 不支持支付")
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
            raise HTTPException(status_code=400, detail=f"订单状态 {biz_order.status} 不支持支付")
        pay_amount = biz_order.total_price

    # 检查是否已有支付记录
    exist_result = await db.execute(
        select(PaymentRecord).where(PaymentRecord.order_no == req.order_no)
    )
    if exist_result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="该订单已有支付记录，请勿重复支付")

    # 生成微信支付交易号
    transaction_id = "WX" + datetime.now().strftime("%Y%m%d%H%M%S") + uuid.uuid4().hex[:10].upper()

    # DEV_MODE: 直接模拟支付成功
    if settings.DEV_MODE:
        # 创建支付记录
        payment = PaymentRecord(
            order_no=req.order_no,
            order_type=req.order_type,
            transaction_id=transaction_id,
            amount=pay_amount,
            status="success",
            pay_method="wechat_jsapi",
            prepay_id="prepay_" + uuid.uuid4().hex[:16],
            pay_time=datetime.utcnow(),
        )
        db.add(payment)

        # 更新业务订单状态为已支付
        if req.order_type == "ticket":
            biz_order.status = TicketOrderStatus.PAID
            biz_order.paid_at = datetime.utcnow()
        else:
            biz_order.status = HotelOrderStatus.PAID
            biz_order.paid_at = datetime.utcnow()

        await db.flush()

        return PaymentCreateResponse(
            success=True,
            message=f"[DEV_MODE] 支付模拟成功，¥{pay_amount}",
            transaction_id=transaction_id,
            payment_params={
                "appId": "wx_dev_mock_appid",
                "timeStamp": str(int(datetime.utcnow().timestamp())),
                "nonceStr": uuid.uuid4().hex[:16],
                "package": f"prepay_id=prepay_{uuid.uuid4().hex[:16]}",
                "signType": "MD5",
                "paySign": "MOCK_SIGNATURE",
            },
        )

    # 生产模式：创建待支付记录，返回JSAPI参数（需要对接真实微信支付）
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

    return PaymentCreateResponse(
        success=True,
        message="支付订单已创建，请调起微信支付",
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

    return PaymentStatusResponse(
        order_no=payment.order_no,
        order_type=payment.order_type,
        transaction_id=payment.transaction_id,
        status=payment.status,
        amount=payment.amount,
        pay_time=payment.pay_time,
    )
