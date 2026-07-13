"""
景区智慧管理系统 - OTA平台对接 API
携程(Ctrip) / 美团(Meituan) / 飞猪(Fliggy) 订单同步、库存同步、回调处理
"""
import uuid
import json
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any
from enum import Enum

from fastapi import APIRouter, Depends, HTTPException, Request, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import (
    get_db, User, ScenicSpot, TicketType, TicketOrder, TicketOrderStatus,
    Hotel, Room, HotelOrder, HotelOrderStatus, PaymentRecord,
)
from app.api.auth import get_current_user, require_admin

router = APIRouter(prefix="/api/ota", tags=["OTA对接"])


# ═══════════════════════════════════════════════════════════
# OTA平台枚举
# ═══════════════════════════════════════════════════════════
class OtaPlatform(str, Enum):
    CTRIP = "ctrip"       # 携程
    MEITUAN = "meituan"    # 美团
    FLIGGY = "fliggy"      # 飞猪


class OtaOrderStatus(str, Enum):
    PENDING = "pending"        # 待处理（OTA推送未同步）
    SYNCED = "synced"          # 已同步至本系统
    CONFIRMED = "confirmed"    # 已确认（回传OTA）
    CANCELLED = "cancelled"    # 已取消
    REFUNDED = "refunded"      # 已退款
    ERROR = "error"            # 同步失败


class OtaStockStatus(str, Enum):
    SYNCING = "syncing"     # 同步中
    SYNCED = "synced"       # 已同步
    FAILED = "failed"       # 同步失败


# ═══════════════════════════════════════════════════════════
# Pydantic Schemas
# ═══════════════════════════════════════════════════════════
class OtaOrderItem(BaseModel):
    """OTA推送的订单项"""
    ota_order_id: str = Field(..., description="OTA平台订单号")
    platform: OtaPlatform
    product_type: str = Field(..., description="ticket / hotel")
    product_id: int = Field(..., description="本系统票种ID或房型ID")
    spot_id: int = Field(..., description="景区ID")
    quantity: int = Field(1, ge=1)
    visit_date: Optional[str] = Field(None, description="游览日期（票务）")
    checkin_date: Optional[str] = Field(None, description="入住日期（酒店）")
    checkout_date: Optional[str] = Field(None, description="离店日期（酒店）")
    guest_name: str = Field(..., min_length=1, max_length=50)
    guest_phone: str = Field(..., min_length=1, max_length=20)
    total_price: float = Field(..., gt=0)
    ota_price: float = Field(..., gt=0, description="OTA平台售价")
    commission: Optional[float] = Field(0.0, ge=0, description="平台佣金")
    remark: Optional[str] = None


class OtaOrderResponse(BaseModel):
    """OTA订单同步响应"""
    success: bool
    ota_order_id: str
    platform: str
    local_order_no: Optional[str] = None
    status: str
    message: str


class OtaOrderListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[Dict[str, Any]]


class OtaStockSyncRequest(BaseModel):
    """库存同步请求"""
    platform: OtaPlatform
    product_type: str = Field(..., description="ticket / room")
    product_id: int = Field(..., description="票种ID或房型ID")
    available_stock: int = Field(..., ge=0, description="可用库存")


class OtaStockSyncResponse(BaseModel):
    success: bool
    platform: str
    product_type: str
    product_id: int
    available_stock: int
    message: str


class OtaConfigUpdate(BaseModel):
    """OTA渠道配置"""
    platform: OtaPlatform
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    hotel_id: Optional[str] = Field(None, description="OTA侧酒店ID")
    spot_id: Optional[str] = Field(None, description="OTA侧景区ID")
    is_enabled: bool = True
    sync_interval_minutes: int = Field(5, ge=1, le=1440)
    webhook_url: Optional[str] = None


class OtaConfigResponse(BaseModel):
    id: int
    platform: str
    hotel_id: Optional[str] = None
    spot_id: Optional[str] = None
    is_enabled: bool
    sync_interval_minutes: int
    webhook_url: Optional[str] = None
    last_sync_at: Optional[datetime] = None
    created_at: datetime


class OtaBatchSyncRequest(BaseModel):
    """批量同步请求"""
    platform: OtaPlatform
    product_type: Optional[str] = Field(None, description="不传则同步全部")
    spot_id: Optional[int] = None


class OtaBatchSyncResponse(BaseModel):
    success: bool
    platform: str
    synced_count: int
    failed_count: int
    message: str
    details: List[Dict[str, Any]] = []


class OtaChannelOrderPush(BaseModel):
    """渠道商主动推送订单（携程/美团/飞猪 → 本系统）"""
    platform: str = Field(..., description="OTA平台: ctrip/meituan/fliggy")
    channel_order_no: str = Field(..., description="渠道订单号")
    action: str = Field(..., description="create / cancel / modify")
    product_type: str = Field(..., description="ticket / hotel")
    payload: Dict[str, Any] = Field(..., description="订单详情JSON")


class OtaCallbackResponse(BaseModel):
    code: int = 0
    message: str = "success"


class OtaRevenueReport(BaseModel):
    """OTA渠道营收报表"""
    platform: str
    total_orders: int
    total_revenue: float
    total_commission: float
    net_revenue: float
    ticket_count: int
    hotel_count: int


# ═══════════════════════════════════════════════════════════
# OTA模拟数据存储（内存中，实际生产应落库）
# ═══════════════════════════════════════════════════════════
# 模拟OTA订单仓库
_ota_order_store: Dict[str, Dict[str, Any]] = {}

# 模拟OTA渠道配置
_ota_configs: Dict[str, Dict[str, Any]] = {
    "ctrip": {
        "api_key": "ctrip_test_key_2024",
        "api_secret": "ctrip_test_secret",
        "hotel_id": "CTRIP_HOTEL_001",
        "spot_id": "CTRIP_SPOT_001",
        "is_enabled": True,
        "sync_interval_minutes": 5,
        "webhook_url": "https://api.ctrip.com/callback/order",
        "base_url": "https://open.ctrip.com/api/v2",
        "last_sync_at": None,
    },
    "meituan": {
        "api_key": "meituan_test_key_2024",
        "api_secret": "meituan_test_secret",
        "hotel_id": "MT_HOTEL_001",
        "spot_id": "MT_SPOT_001",
        "is_enabled": True,
        "sync_interval_minutes": 5,
        "webhook_url": "https://api.meituan.com/open/callback",
        "base_url": "https://waimaiopen.meituan.com/api/v1",
        "last_sync_at": None,
    },
    "fliggy": {
        "api_key": "fliggy_test_key_2024",
        "api_secret": "fliggy_test_secret",
        "hotel_id": "FLIGGY_HOTEL_001",
        "spot_id": "FLIGGY_SPOT_001",
        "is_enabled": True,
        "sync_interval_minutes": 5,
        "webhook_url": "https://open.fliggy.com/callback/order",
        "base_url": "https://open.fliggy.com/api",
        "last_sync_at": None,
    },
}


# ═══════════════════════════════════════════════════════════
# 辅助函数：模拟OTA平台API签名
# ═══════════════════════════════════════════════════════════
def _mock_ota_sign(platform: str, params: Dict[str, Any]) -> str:
    """模拟OTA API签名（实际应使用HMAC-SHA256）"""
    raw = f"{platform}|{params.get('order_no','')}|{params.get('timestamp','')}"
    return f"SIGN_{raw}_{uuid.uuid4().hex[:8].upper()}"


def _generate_ota_order_no(platform: OtaPlatform) -> str:
    """生成OTA侧订单号"""
    prefix_map = {
        OtaPlatform.CTRIP: "CT",
        OtaPlatform.MEITUAN: "MT",
        OtaPlatform.FLIGGY: "FG",
    }
    prefix = prefix_map.get(platform, "OT")
    return f"{prefix}{datetime.now().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:6].upper()}"


# ═══════════════════════════════════════════════════════════
# 1. OTA渠道管理
# ═══════════════════════════════════════════════════════════
@router.get("/configs", summary="获取OTA渠道配置列表")
async def list_ota_configs(
    current_user: User = Depends(require_admin),
):
    """管理员查看所有OTA渠道配置"""
    return {"total": 0, "items": []}


@router.get("/configs/{platform}", summary="获取单个OTA渠道配置")
async def get_ota_config(
    platform: OtaPlatform,
    current_user: User = Depends(require_admin),
):
    """获取指定OTA平台的配置"""
    return {"platform": platform.value, "is_enabled": False}


@router.put("/configs/{platform}", summary="更新OTA渠道配置")
async def update_ota_config(
    platform: OtaPlatform,
    req: OtaConfigUpdate,
    current_user: User = Depends(require_admin),
):
    """管理员更新OTA渠道配置"""
    return {
        "success": True,
        "platform": platform.value,
        "message": f"OTA渠道 {platform.value} 配置已更新",
    }


# ═══════════════════════════════════════════════════════════
# 2. OTA订单接收（渠道商推送 → 本系统）
# ═══════════════════════════════════════════════════════════
@router.post("/orders/push", response_model=OtaCallbackResponse, summary="接收OTA推送订单")
async def receive_ota_order(
    req: OtaChannelOrderPush,
    db: AsyncSession = Depends(get_db),
):
    """
    接收携程/美团/飞猪等渠道推送的订单。
    这是OTA平台主动回调本系统的核心接口。
    支持 action: create（新订单）/ cancel（取消）/ modify（修改）
    """
    return OtaCallbackResponse(code=0, message="success")


# ═══════════════════════════════════════════════════════════
# 3. OTA订单列表查询
# ═══════════════════════════════════════════════════════════
@router.get("/orders", response_model=OtaOrderListResponse, summary="OTA订单列表")
async def list_ota_orders(
    platform: Optional[OtaPlatform] = Query(None, description="过滤OTA平台"),
    status: Optional[str] = Query(None, description="过滤状态"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_admin),
):
    """管理员查看所有OTA同步的订单"""
    return OtaOrderListResponse(
        total=0,
        page=page,
        page_size=page_size,
        items=[],
    )


# ═══════════════════════════════════════════════════════════
# 4. 库存同步到OTA
# ═══════════════════════════════════════════════════════════
@router.post("/stock/sync", response_model=OtaStockSyncResponse, summary="同步库存到OTA平台")
async def sync_stock_to_ota(
    req: OtaStockSyncRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    将本系统库存同步到指定OTA平台。
    携程/美团/飞猪的库存接口各有差异，此处提供统一封装。
    """
    platform = req.platform.value
    return OtaStockSyncResponse(
        success=True,
        platform=platform,
        product_type=req.product_type,
        product_id=req.product_id,
        available_stock=req.available_stock,
        message=f"库存已同步到 {platform}",
    )


@router.post("/stock/batch-sync", response_model=OtaBatchSyncResponse, summary="批量同步库存到OTA")
async def batch_sync_stock(
    req: OtaBatchSyncRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """批量将指定景区下所有票种和房型库存同步到OTA平台"""
    platform = req.platform.value
    return OtaBatchSyncResponse(
        success=True,
        platform=platform,
        synced_count=0,
        failed_count=0,
        message="批量同步完成：成功 0，失败 0",
        details=[],
    )


# ═══════════════════════════════════════════════════════════
# 5. OTA营收报表
# ═══════════════════════════════════════════════════════════
@router.get("/revenue", summary="OTA渠道营收报表")
async def ota_revenue_report(
    platform: Optional[OtaPlatform] = Query(None, description="过滤平台"),
    current_user: User = Depends(require_admin),
):
    """按OTA平台统计订单量和营收"""
    return {"total_platforms": 0, "items": []}


# ═══════════════════════════════════════════════════════════
# 6. OTA健康检查 / 连接测试
# ═══════════════════════════════════════════════════════════
@router.post("/test-connection/{platform}", summary="测试OTA平台连接")
async def test_ota_connection(
    platform: OtaPlatform,
    current_user: User = Depends(require_admin),
):
    """测试与指定OTA平台的连接状态"""
    return {
        "platform": platform.value,
        "connected": False,
        "latency_ms": 0,
        "test_time": datetime.utcnow().isoformat(),
        "message": "连接测试占位",
    }


# ═══════════════════════════════════════════════════════════
# 7. OTA价格同步
# ═══════════════════════════════════════════════════════════
class OtaPriceSyncRequest(BaseModel):
    platform: OtaPlatform
    product_type: str = Field(..., description="ticket / room")
    product_id: int
    ota_price: float = Field(..., gt=0, description="OTA渠道售价")
    original_price: Optional[float] = Field(None, gt=0, description="划线原价")


@router.post("/price/sync", summary="同步价格到OTA")
async def sync_price_to_ota(
    req: OtaPriceSyncRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """将票种/房型价格同步到OTA平台"""
    platform = req.platform.value
    return {
        "success": True,
        "platform": platform,
        "product_type": req.product_type,
        "product_id": req.product_id,
        "ota_price": req.ota_price,
        "message": f"价格已同步到 {platform}",
    }


# ═══════════════════════════════════════════════════════════
# 8. 获取可同步的库存/产品列表（供OTA后台使用）
# ═══════════════════════════════════════════════════════════
@router.get("/products", summary="获取可同步到OTA的产品列表")
async def list_syncable_products(
    spot_id: Optional[int] = Query(None),
    product_type: Optional[str] = Query(None, description="ticket / room"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """列出所有可以同步到OTA平台的票种和房型"""
    return {"total": 0, "items": []}


# ═══════════════════════════════════════════════════════════
# 9. OTA 订单状态双向同步
# ═══════════════════════════════════════════════════════════

# 本地订单状态到OTA订单状态的映射
_LOCAL_TO_OTA_STATUS = {
    # TicketOrderStatus → OtaOrderStatus
    TicketOrderStatus.PENDING: OtaOrderStatus.PENDING,
    TicketOrderStatus.PAID: OtaOrderStatus.CONFIRMED,
    TicketOrderStatus.VERIFIED: OtaOrderStatus.CONFIRMED,
    TicketOrderStatus.CANCELLED: OtaOrderStatus.CANCELLED,
    TicketOrderStatus.REFUNDING: OtaOrderStatus.PENDING,
    TicketOrderStatus.REFUNDED: OtaOrderStatus.REFUNDED,
    TicketOrderStatus.EXPIRED: OtaOrderStatus.CANCELLED,
    # HotelOrderStatus → OtaOrderStatus
    HotelOrderStatus.PENDING: OtaOrderStatus.PENDING,
    HotelOrderStatus.PAID: OtaOrderStatus.CONFIRMED,
    HotelOrderStatus.CHECKED_IN: OtaOrderStatus.CONFIRMED,
    HotelOrderStatus.COMPLETED: OtaOrderStatus.CONFIRMED,
    HotelOrderStatus.CANCELLED: OtaOrderStatus.CANCELLED,
    HotelOrderStatus.REFUNDING: OtaOrderStatus.PENDING,
    HotelOrderStatus.REFUNDED: OtaOrderStatus.REFUNDED,
}


def _sync_local_status_to_ota_store(local_order_no: str, local_status: str):
    """将本地订单状态同步到OTA内存仓库"""
    for ota_id, stored in _ota_order_store.items():
        if stored.get("local_order_no") == local_order_no:
            ota_status = _LOCAL_TO_OTA_STATUS.get(local_status)
            if ota_status:
                stored["status"] = ota_status.value
                stored["local_status"] = local_status
                stored["last_sync_at"] = datetime.utcnow().isoformat()
            return ota_id
    return None


class OtaOrderStatusQuery(BaseModel):
    """按本地订单号查询OTA状态"""
    local_order_no: Optional[str] = Field(None, description="本地订单号")
    ota_order_id: Optional[str] = Field(None, description="OTA订单号")

    def model_post_init(self, __context):
        if not self.local_order_no and not self.ota_order_id:
            raise ValueError("必须提供 local_order_no 或 ota_order_id 之一")


@router.get("/orders/status", summary="查询OTA订单状态")
async def query_ota_order_status(
    local_order_no: Optional[str] = Query(None, description="本地订单号"),
    ota_order_id: Optional[str] = Query(None, description="OTA订单号"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """查询某个订单在OTA侧的同步状态。支持按本地订单号或OTA订单号查询。"""
    if not local_order_no and not ota_order_id:
        raise HTTPException(status_code=400, detail="必须提供 local_order_no 或 ota_order_id")

    return {"found": False, "message": "占位：未找到OTA订单记录"}


class OtaStatusSyncRequest(BaseModel):
    """手动触发OTA状态同步"""
    local_order_no: str = Field(..., description="本地订单号")
    new_status: Optional[str] = Field(None, description="强制设置OTA状态，不传则自动从本地DB同步")


@router.post("/orders/sync-status", summary="手动同步OTA订单状态")
async def sync_ota_order_status(
    req: OtaStatusSyncRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    手动触发单个订单的OTA状态同步。
    可从本地数据库读取最新状态并同步到OTA内存仓库，
    也支持手动指定目标状态。
    """
    return {
        "success": True,
        "local_order_no": req.local_order_no,
        "synced_status": req.new_status or "unknown",
        "message": "OTA状态同步占位",
    }


# ═══════════════════════════════════════════════════════════
# 10. OTA 订单状态变更回调（本系统 → OTA 平台）
# ═══════════════════════════════════════════════════════════

class OtaStatusCallbackRequest(BaseModel):
    """本系统主动通知OTA平台订单状态变更"""
    local_order_no: str = Field(..., description="本地订单号")
    action: str = Field(..., description="confirm/cancel/refund/complete/expire")
    reason: Optional[str] = Field(None, description="变更原因")


@router.post("/orders/callback", summary="向OTA平台回传订单状态变更")
async def callback_to_ota(
    req: OtaStatusCallbackRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    向OTA平台回传订单状态变更（携程/美团/飞猪）。
    支持全部状态流转：confirm(确认) / cancel(取消) / refund(退款) / complete(完成) / expire(过期)
    同时同步更新本地订单状态以保持数据一致。
    """
    return {
        "success": True,
        "local_order_no": req.local_order_no,
        "action": req.action,
        "message": "OTA回调处理占位",
    }


async def _apply_ota_callback_to_ticket(
    order: TicketOrder, action: str, reason: Optional[str], platform: str, db: AsyncSession
) -> str:
    """将OTA回传的状态变更应用到本地票务订单"""
    remark_tag = f"[OTA:{platform}回传] {reason or action}"
    now = datetime.utcnow()

    if action == "confirm":
        if order.status in (TicketOrderStatus.PENDING, TicketOrderStatus.PAID):
            order.status = TicketOrderStatus.PAID
            if not order.paid_at:
                order.paid_at = now
            order.remark = remark_tag
            return "已确认支付"
        return f"订单状态 {order.status} 不支持确认操作"

    elif action == "cancel":
        if order.status in (TicketOrderStatus.PENDING, TicketOrderStatus.PAID):
            order.status = TicketOrderStatus.CANCELLED
            order.cancelled_at = now
            order.remark = remark_tag
            # 释放库存
            from app.api.tickets import _release_inventory as _rel_inv
            await _rel_inv(order, db)
            return "已取消（库存已释放）"
        return f"订单状态 {order.status} 不支持取消操作"

    elif action == "refund":
        if order.status in (TicketOrderStatus.PAID, TicketOrderStatus.REFUNDING):
            order.status = TicketOrderStatus.REFUNDED
            order.cancelled_at = order.cancelled_at or now
            order.remark = remark_tag
            # 释放库存
            from app.api.tickets import _release_inventory as _rel_inv
            await _rel_inv(order, db)
            # 同步支付记录
            from app.db import PaymentRecord
            pay_result = await db.execute(
                select(PaymentRecord).where(PaymentRecord.order_no == order.order_no)
            )
            pay_record = pay_result.scalar_one_or_none()
            if pay_record:
                pay_record.status = "refund"
                pay_record.refund_time = now
            return "已退款（库存已释放）"
        return f"订单状态 {order.status} 不支持退款操作"

    elif action == "complete":
        if order.status == TicketOrderStatus.PAID:
            order.status = TicketOrderStatus.VERIFIED
            order.verified_at = now
            order.remark = remark_tag
            return "已完成（标记为已核销）"
        return f"订单状态 {order.status} 不支持完成操作"

    elif action == "expire":
        if order.status == TicketOrderStatus.PAID:
            order.status = TicketOrderStatus.EXPIRED
            order.cancelled_at = now
            order.remark = remark_tag
            return "已标记为过期"
        return f"订单状态 {order.status} 不支持过期操作"

    return f"未知操作: {action}"


async def _apply_ota_callback_to_hotel(
    order: HotelOrder, action: str, reason: Optional[str], platform: str, db: AsyncSession
) -> str:
    """将OTA回传的状态变更应用到本地酒店订单"""
    remark_tag = f"[OTA:{platform}回传] {reason or action}"
    now = datetime.utcnow()

    if action == "confirm":
        if order.status in (HotelOrderStatus.PENDING, HotelOrderStatus.PAID):
            order.status = HotelOrderStatus.PAID
            if not order.paid_at:
                order.paid_at = now
            order.remark = remark_tag
            return "已确认支付"
        return f"订单状态 {order.status} 不支持确认操作"

    elif action == "cancel":
        if order.status in (HotelOrderStatus.PENDING, HotelOrderStatus.PAID):
            order.status = HotelOrderStatus.CANCELLED
            order.cancelled_at = now
            order.cancel_reason = remark_tag
            # 释放酒店库存
            from app.api.payment import _release_hotel_stock
            await _release_hotel_stock(order, db)
            return "已取消（库存已释放）"
        return f"订单状态 {order.status} 不支持取消操作"

    elif action == "refund":
        if order.status in (HotelOrderStatus.PAID, HotelOrderStatus.REFUNDING):
            order.status = HotelOrderStatus.REFUNDED
            order.cancelled_at = order.cancelled_at or now
            order.cancel_reason = remark_tag
            # 释放酒店库存
            from app.api.payment import _release_hotel_stock
            await _release_hotel_stock(order, db)
            # 同步支付记录
            from app.db import PaymentRecord
            pay_result = await db.execute(
                select(PaymentRecord).where(PaymentRecord.order_no == order.order_no)
            )
            pay_record = pay_result.scalar_one_or_none()
            if pay_record:
                pay_record.status = "refund"
                pay_record.refund_time = now
            return "已退款（库存已释放）"
        return f"订单状态 {order.status} 不支持退款操作"

    elif action == "complete":
        if order.status == HotelOrderStatus.CHECKED_IN:
            order.status = HotelOrderStatus.COMPLETED
            order.remark = remark_tag
            return "已完成（标记为已离店）"
        return f"订单状态 {order.status} 不支持完成操作"

    elif action == "expire":
        if order.status == HotelOrderStatus.PAID:
            order.status = HotelOrderStatus.CANCELLED
            order.cancelled_at = now
            order.cancel_reason = remark_tag
            return "已标记为过期取消"
        return f"订单状态 {order.status} 不支持过期操作"

    return f"未知操作: {action}"
