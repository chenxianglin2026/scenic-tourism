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
    configs = []
    for platform, cfg in _ota_configs.items():
        configs.append({
            "platform": platform,
            "hotel_id": cfg.get("hotel_id"),
            "spot_id": cfg.get("spot_id"),
            "is_enabled": cfg.get("is_enabled"),
            "sync_interval_minutes": cfg.get("sync_interval_minutes"),
            "webhook_url": cfg.get("webhook_url"),
            "base_url": cfg.get("base_url"),
            "last_sync_at": cfg.get("last_sync_at"),
        })
    return {"total": len(configs), "items": configs}


@router.get("/configs/{platform}", summary="获取单个OTA渠道配置")
async def get_ota_config(
    platform: OtaPlatform,
    current_user: User = Depends(require_admin),
):
    """获取指定OTA平台的配置"""
    if platform.value not in _ota_configs:
        raise HTTPException(status_code=404, detail=f"OTA平台 {platform.value} 未配置")
    cfg = _ota_configs[platform.value]
    return {
        "platform": platform.value,
        **{k: v for k, v in cfg.items() if k != "api_secret"},
    }


@router.put("/configs/{platform}", summary="更新OTA渠道配置")
async def update_ota_config(
    platform: OtaPlatform,
    req: OtaConfigUpdate,
    current_user: User = Depends(require_admin),
):
    """管理员更新OTA渠道配置"""
    if platform.value not in _ota_configs:
        _ota_configs[platform.value] = {}
    cfg = _ota_configs[platform.value]

    update_data = req.model_dump(exclude_unset=True, exclude={"platform"})
    for k, v in update_data.items():
        if v is not None:
            cfg[k] = v

    return {
        "success": True,
        "platform": platform.value,
        "message": f"OTA渠道 {platform.value} 配置已更新",
        "config": {k: v for k, v in cfg.items() if k != "api_secret"},
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
    platform = req.platform
    payload = req.payload
    ota_order_id = req.channel_order_no

    if platform not in _ota_configs:
        return OtaCallbackResponse(code=1, message=f"未配置的OTA平台: {platform}")

    cfg = _ota_configs[platform]
    if not cfg.get("is_enabled"):
        return OtaCallbackResponse(code=1, message=f"OTA平台 {platform} 已禁用")

    if req.action == "create":
        # 创建OTA订单记录
        local_order_no = None
        try:
            if req.product_type == "ticket":
                ticket_type_id = payload.get("ticket_type_id")
                spot_id = payload.get("spot_id")
                quantity = payload.get("quantity", 1)
                visit_date_str = payload.get("visit_date", date.today().isoformat())
                guest_name = payload.get("guest_name", "OTA游客")
                guest_phone = payload.get("guest_phone", "")
                total_price = payload.get("total_price", 0)

                # 创建本地票务订单
                from datetime import date as date_type
                visit_date = date_type.fromisoformat(visit_date_str)
                local_order_no = f"OTA_{platform.upper()}_{uuid.uuid4().hex[:12].upper()}"

                # 检查票种是否存在
                tt_result = await db.execute(
                    select(TicketType).where(TicketType.id == ticket_type_id)
                )
                ticket_type = tt_result.scalar_one_or_none()
                if not ticket_type:
                    return OtaCallbackResponse(code=1, message=f"票种不存在: {ticket_type_id}")

                order = TicketOrder(
                    order_no=local_order_no,
                    user_id=1,  # OTA系统用户
                    ticket_type_id=ticket_type_id,
                    spot_id=spot_id,
                    quantity=quantity,
                    visit_date=visit_date,
                    time_slot=payload.get("time_slot", "08:00-10:00"),
                    total_price=total_price,
                    status=TicketOrderStatus.PAID,
                    visitor_name=guest_name,
                    visitor_phone=guest_phone,
                    qr_token=f"OTA_QR_{uuid.uuid4().hex[:16]}",
                    paid_at=datetime.utcnow(),
                    remark=f"[OTA:{platform}] 订单号:{ota_order_id}",
                )
                db.add(order)

            elif req.product_type == "hotel":
                hotel_id = payload.get("hotel_id")
                room_id = payload.get("room_id")
                checkin_str = payload.get("checkin_date")
                checkout_str = payload.get("checkout_date")
                guest_name = payload.get("guest_name", "OTA游客")
                guest_phone = payload.get("guest_phone", "")
                total_price = payload.get("total_price", 0)

                if not checkin_str or not checkout_str:
                    return OtaCallbackResponse(code=1, message="缺少入住/离店日期")
                checkin = date.fromisoformat(checkin_str)
                checkout = date.fromisoformat(checkout_str)
                nights = (checkout - checkin).days
                local_order_no = f"OTA_H_{platform.upper()}_{uuid.uuid4().hex[:12].upper()}"

                order = HotelOrder(
                    order_no=local_order_no,
                    user_id=1,
                    hotel_id=hotel_id,
                    room_id=room_id,
                    room_count=payload.get("room_count", 1),
                    checkin_date=checkin,
                    checkout_date=checkout,
                    nights=nights,
                    total_price=total_price,
                    status=HotelOrderStatus.PAID,
                    guest_name=guest_name,
                    guest_phone=guest_phone,
                    paid_at=datetime.utcnow(),
                    remark=f"[OTA:{platform}] 渠道订单:{ota_order_id}",
                )
                db.add(order)

            await db.flush()

            # 存入内存仓库
            _ota_order_store[ota_order_id] = {
                "ota_order_id": ota_order_id,
                "platform": platform,
                "local_order_no": local_order_no,
                "status": OtaOrderStatus.SYNCED.value,
                "action": req.action,
                "product_type": req.product_type,
                "created_at": datetime.utcnow().isoformat(),
                "payload": payload,
            }

            return OtaCallbackResponse(code=0, message=f"订单同步成功: {local_order_no}")

        except Exception as e:
            _ota_order_store[ota_order_id] = {
                "ota_order_id": ota_order_id,
                "platform": platform,
                "local_order_no": local_order_no,
                "status": OtaOrderStatus.ERROR.value,
                "error": str(e),
                "created_at": datetime.utcnow().isoformat(),
            }
            return OtaCallbackResponse(code=1, message=f"订单同步失败: {str(e)}")

    elif req.action == "cancel":
        # 取消订单
        if ota_order_id in _ota_order_store:
            stored = _ota_order_store[ota_order_id]
            local_order_no = stored.get("local_order_no")

            if stored.get("product_type") == "ticket":
                result = await db.execute(
                    select(TicketOrder).where(TicketOrder.order_no == local_order_no)
                )
                order = result.scalar_one_or_none()
                if order and order.status == TicketOrderStatus.PAID:
                    order.status = TicketOrderStatus.CANCELLED
                    order.cancelled_at = datetime.utcnow()
                    order.remark = f"[OTA:{platform}] 渠道取消: {ota_order_id}"
            else:
                result = await db.execute(
                    select(HotelOrder).where(HotelOrder.order_no == local_order_no)
                )
                order = result.scalar_one_or_none()
                if order and order.status == HotelOrderStatus.PAID:
                    order.status = HotelOrderStatus.CANCELLED
                    order.cancelled_at = datetime.utcnow()
                    order.cancel_reason = f"[OTA:{platform}] 渠道取消: {ota_order_id}"

            stored["status"] = OtaOrderStatus.CANCELLED.value
            stored["action"] = "cancel"
            await db.flush()
            return OtaCallbackResponse(code=0, message="订单已取消")

        return OtaCallbackResponse(code=1, message="未找到对应的OTA订单")

    elif req.action == "modify":
        if ota_order_id in _ota_order_store:
            _ota_order_store[ota_order_id]["payload"].update(payload)
            _ota_order_store[ota_order_id]["action"] = "modify"
            return OtaCallbackResponse(code=0, message="订单已修改")
        return OtaCallbackResponse(code=1, message="未找到对应的OTA订单")

    return OtaCallbackResponse(code=1, message=f"未知操作: {req.action}")


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
    items = list(_ota_order_store.values())

    if platform:
        items = [i for i in items if i.get("platform") == platform.value]
    if status:
        items = [i for i in items if i.get("status") == status]

    items.sort(key=lambda x: x.get("created_at", ""), reverse=True)

    total = len(items)
    start = (page - 1) * page_size
    end = start + page_size
    paged = items[start:end]

    return OtaOrderListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=paged,
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
    if platform not in _ota_configs:
        raise HTTPException(status_code=404, detail=f"OTA平台 {platform} 未配置")

    cfg = _ota_configs[platform]
    if not cfg.get("is_enabled"):
        raise HTTPException(status_code=400, detail=f"OTA平台 {platform} 已禁用")

    # 模拟API调用：更新本地库存记录
    if req.product_type == "ticket":
        result = await db.execute(
            select(TicketType).where(TicketType.id == req.product_id)
        )
        product = result.scalar_one_or_none()
        if not product:
            raise HTTPException(status_code=404, detail=f"票种不存在: {req.product_id}")
        product.daily_stock = req.available_stock
    elif req.product_type == "room":
        result = await db.execute(
            select(Room).where(Room.id == req.product_id)
        )
        product = result.scalar_one_or_none()
        if not product:
            raise HTTPException(status_code=404, detail=f"房型不存在: {req.product_id}")
        product.available_count = req.available_stock
    else:
        raise HTTPException(status_code=400, detail="product_type 必须是 ticket 或 room")

    await db.flush()

    # 模拟OTA API调用
    mock_sign = _mock_ota_sign(platform, {
        "product_id": req.product_id,
        "stock": req.available_stock,
    })

    cfg["last_sync_at"] = datetime.utcnow()

    return OtaStockSyncResponse(
        success=True,
        platform=platform,
        product_type=req.product_type,
        product_id=req.product_id,
        available_stock=req.available_stock,
        message=f"库存已同步到 {platform}，sign={mock_sign}",
    )


@router.post("/stock/batch-sync", response_model=OtaBatchSyncResponse, summary="批量同步库存到OTA")
async def batch_sync_stock(
    req: OtaBatchSyncRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """批量将指定景区下所有票种和房型库存同步到OTA平台"""
    platform = req.platform.value
    if platform not in _ota_configs:
        raise HTTPException(status_code=404, detail=f"OTA平台 {platform} 未配置")

    details = []
    synced = 0
    failed = 0

    if req.product_type in (None, "ticket"):
        q = select(TicketType).where(TicketType.is_active == True)
        if req.spot_id:
            q = q.where(TicketType.spot_id == req.spot_id)
        result = await db.execute(q)
        for tt in result.scalars().all():
            try:
                _ota_configs[platform]["last_sync_at"] = datetime.utcnow()
                details.append({
                    "type": "ticket",
                    "id": tt.id,
                    "name": tt.name,
                    "stock": tt.daily_stock,
                    "status": "success",
                })
                synced += 1
            except Exception as e:
                details.append({
                    "type": "ticket",
                    "id": tt.id,
                    "name": tt.name,
                    "status": "failed",
                    "error": str(e),
                })
                failed += 1

    if req.product_type in (None, "room"):
        q = select(Room).where(Room.is_active == True)
        if req.spot_id:
            hotel_q = select(Hotel.id).where(Hotel.spot_id == req.spot_id)
            hotel_ids = (await db.execute(hotel_q)).scalars().all()
            if hotel_ids:
                q = q.where(Room.hotel_id.in_(hotel_ids))
            else:
                q = q.where(Room.id == -1)  # no results
        result = await db.execute(q)
        for room in result.scalars().all():
            try:
                details.append({
                    "type": "room",
                    "id": room.id,
                    "name": room.name,
                    "stock": room.available_count,
                    "status": "success",
                })
                synced += 1
            except Exception as e:
                details.append({
                    "type": "room",
                    "id": room.id,
                    "name": room.name,
                    "status": "failed",
                    "error": str(e),
                })
                failed += 1

    return OtaBatchSyncResponse(
        success=failed == 0,
        platform=platform,
        synced_count=synced,
        failed_count=failed,
        message=f"批量同步完成：成功 {synced}，失败 {failed}",
        details=details,
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
    platforms = [platform.value] if platform else list(_ota_configs.keys())
    reports = []

    for pf in platforms:
        pf_orders = [v for v in _ota_order_store.values()
                     if v.get("platform") == pf and v.get("status") == OtaOrderStatus.SYNCED.value]

        ticket_count = sum(1 for o in pf_orders if o.get("product_type") == "ticket")
        hotel_count = sum(1 for o in pf_orders if o.get("product_type") == "hotel")
        total_revenue = sum(
            o.get("payload", {}).get("total_price", 0) for o in pf_orders
        )
        # 佣金按10%估算
        total_commission = total_revenue * 0.10

        reports.append(OtaRevenueReport(
            platform=pf,
            total_orders=len(pf_orders),
            total_revenue=round(total_revenue, 2),
            total_commission=round(total_commission, 2),
            net_revenue=round(total_revenue - total_commission, 2),
            ticket_count=ticket_count,
            hotel_count=hotel_count,
        ))

    return {"total_platforms": len(reports), "items": [r.model_dump() for r in reports]}


# ═══════════════════════════════════════════════════════════
# 6. OTA健康检查 / 连接测试
# ═══════════════════════════════════════════════════════════
@router.post("/test-connection/{platform}", summary="测试OTA平台连接")
async def test_ota_connection(
    platform: OtaPlatform,
    current_user: User = Depends(require_admin),
):
    """测试与指定OTA平台的连接状态"""
    if platform.value not in _ota_configs:
        raise HTTPException(status_code=404, detail=f"OTA平台 {platform.value} 未配置")

    cfg = _ota_configs[platform.value]
    # 模拟连接测试
    test_result = {
        "platform": platform.value,
        "connected": cfg.get("is_enabled", False),
        "api_endpoint": cfg.get("base_url", ""),
        "latency_ms": 45 + hash(platform.value) % 100,
        "test_time": datetime.utcnow().isoformat(),
        "hotel_id": cfg.get("hotel_id"),
        "spot_id": cfg.get("spot_id"),
        "message": "连接正常" if cfg.get("is_enabled") else "已禁用",
    }
    return test_result


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
    if platform not in _ota_configs:
        raise HTTPException(status_code=404, detail=f"OTA平台 {platform} 未配置")

    if req.product_type == "ticket":
        result = await db.execute(select(TicketType).where(TicketType.id == req.product_id))
        product = result.scalar_one_or_none()
        if not product:
            raise HTTPException(status_code=404, detail=f"票种不存在: {req.product_id}")
        product.price = req.ota_price
        if req.original_price is not None:
            product.original_price = req.original_price
    elif req.product_type == "room":
        result = await db.execute(select(Room).where(Room.id == req.product_id))
        product = result.scalar_one_or_none()
        if not product:
            raise HTTPException(status_code=404, detail=f"房型不存在: {req.product_id}")
        product.price = req.ota_price
    else:
        raise HTTPException(status_code=400, detail="product_type 必须是 ticket 或 room")

    await db.flush()

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
    products = []

    if product_type in (None, "ticket"):
        q = select(TicketType).where(TicketType.is_active == True)
        if spot_id:
            q = q.where(TicketType.spot_id == spot_id)
        result = await db.execute(q)
        for tt in result.scalars().all():
            products.append({
                "type": "ticket",
                "id": tt.id,
                "spot_id": tt.spot_id,
                "name": tt.name,
                "price": tt.price,
                "original_price": tt.original_price,
                "stock": tt.daily_stock,
                "category": tt.category,
            })

    if product_type in (None, "room"):
        q = select(Room, Hotel).join(Hotel, Room.hotel_id == Hotel.id).where(
            Room.is_active == True
        )
        if spot_id:
            q = q.where(Hotel.spot_id == spot_id)
        result = await db.execute(q)
        for room, hotel in result.all():
            products.append({
                "type": "room",
                "id": room.id,
                "hotel_id": room.hotel_id,
                "hotel_name": hotel.name,
                "spot_id": hotel.spot_id,
                "name": room.name,
                "price": room.price,
                "stock": room.available_count,
                "total_count": room.total_count,
                "room_type": room.room_type,
            })

    return {"total": len(products), "items": products}


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

    # 按OTA订单号查
    if ota_order_id and ota_order_id in _ota_order_store:
        stored = _ota_order_store[ota_order_id]
        return {
            "found": True,
            "ota_order_id": ota_order_id,
            "platform": stored.get("platform"),
            "local_order_no": stored.get("local_order_no"),
            "status": stored.get("status"),
            "action": stored.get("action"),
            "product_type": stored.get("product_type"),
            "created_at": stored.get("created_at"),
            "last_sync_at": stored.get("last_sync_at"),
            "local_status": stored.get("local_status"),
        }

    # 按本地订单号查
    if local_order_no:
        for ota_id, stored in _ota_order_store.items():
            if stored.get("local_order_no") == local_order_no:
                return {
                    "found": True,
                    "ota_order_id": ota_id,
                    "platform": stored.get("platform"),
                    "local_order_no": local_order_no,
                    "status": stored.get("status"),
                    "action": stored.get("action"),
                    "product_type": stored.get("product_type"),
                    "created_at": stored.get("created_at"),
                    "last_sync_at": stored.get("last_sync_at"),
                    "local_status": stored.get("local_status"),
                }

    # 也尝试从本地数据库查找关联
    if local_order_no:
        # 查找票务订单
        ticket_result = await db.execute(
            select(TicketOrder).where(TicketOrder.order_no == local_order_no)
        )
        ticket_order = ticket_result.scalar_one_or_none()
        if ticket_order:
            ota_status = _LOCAL_TO_OTA_STATUS.get(ticket_order.status)
            return {
                "found": False,
                "local_order_no": local_order_no,
                "local_type": "ticket",
                "local_status": ticket_order.status,
                "ota_status": ota_status.value if ota_status else "unknown",
                "message": "该订单未在OTA仓库中找到，可能非OTA来源",
            }

        # 查找酒店订单
        hotel_result = await db.execute(
            select(HotelOrder).where(HotelOrder.order_no == local_order_no)
        )
        hotel_order = hotel_result.scalar_one_or_none()
        if hotel_order:
            ota_status = _LOCAL_TO_OTA_STATUS.get(hotel_order.status)
            return {
                "found": False,
                "local_order_no": local_order_no,
                "local_type": "hotel",
                "local_status": hotel_order.status,
                "ota_status": ota_status.value if ota_status else "unknown",
                "message": "该订单未在OTA仓库中找到，可能非OTA来源",
            }

    raise HTTPException(status_code=404, detail="未找到对应的OTA订单记录")


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
    local_order_no = req.local_order_no

    # 先从本地数据库查找
    local_status = None
    order_type = None

    ticket_result = await db.execute(
        select(TicketOrder).where(TicketOrder.order_no == local_order_no)
    )
    ticket_order = ticket_result.scalar_one_or_none()
    if ticket_order:
        local_status = ticket_order.status
        order_type = "ticket"
    else:
        hotel_result = await db.execute(
            select(HotelOrder).where(HotelOrder.order_no == local_order_no)
        )
        hotel_order = hotel_result.scalar_one_or_none()
        if hotel_order:
            local_status = hotel_order.status
            order_type = "hotel"

    if not local_status:
        raise HTTPException(status_code=404, detail="本地订单不存在")

    target_status = req.new_status or local_status

    # 同步到OTA仓库
    synced_id = _sync_local_status_to_ota_store(local_order_no, target_status)

    if synced_id:
        return {
            "success": True,
            "local_order_no": local_order_no,
            "ota_order_id": synced_id,
            "order_type": order_type,
            "previous_local_status": local_status,
            "synced_status": target_status,
            "message": f"OTA状态已同步: {target_status}",
        }

    return {
        "success": True,
        "local_order_no": local_order_no,
        "order_type": order_type,
        "local_status": local_status,
        "synced": False,
        "message": "该订单非OTA来源，无需同步到OTA仓库",
    }


# ═══════════════════════════════════════════════════════════
# 10. OTA 订单状态变更回调（本系统 → OTA 平台）
# ═══════════════════════════════════════════════════════════

class OtaStatusCallbackRequest(BaseModel):
    """本系统主动通知OTA平台订单状态变更"""
    local_order_no: str = Field(..., description="本地订单号")
    action: str = Field(..., description="confirm/cancel/refund/complete")
    reason: Optional[str] = Field(None, description="变更原因")


@router.post("/orders/callback", summary="向OTA平台回传订单状态变更")
async def callback_to_ota(
    req: OtaStatusCallbackRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    模拟向OTA平台回传订单状态变更。
    本系统状态变更后，通过此接口通知携程/美团/飞猪。
    """
    # 在OTA仓库中查找
    ota_order_id = None
    platform = None

    for oid, stored in _ota_order_store.items():
        if stored.get("local_order_no") == req.local_order_no:
            ota_order_id = oid
            platform = stored.get("platform")
            break

    if not ota_order_id:
        raise HTTPException(status_code=404, detail="未找到对应的OTA订单，无法回传状态")

    if platform not in _ota_configs:
        raise HTTPException(status_code=404, detail=f"OTA平台 {platform} 未配置")

    cfg = _ota_configs[platform]
    if not cfg.get("is_enabled"):
        raise HTTPException(status_code=400, detail=f"OTA平台 {platform} 已禁用")

    # 更新OTA仓库状态
    stored = _ota_order_store[ota_order_id]

    action_map = {
        "confirm": OtaOrderStatus.CONFIRMED,
        "cancel": OtaOrderStatus.CANCELLED,
        "refund": OtaOrderStatus.REFUNDED,
        "complete": OtaOrderStatus.CONFIRMED,
    }
    new_status = action_map.get(req.action, OtaOrderStatus.CONFIRMED)
    stored["status"] = new_status.value
    stored["last_sync_at"] = datetime.utcnow().isoformat()
    stored["callback_reason"] = req.reason

    # 模拟OTA API调用签名
    mock_sign = _mock_ota_sign(platform, {
        "order_no": ota_order_id,
        "action": req.action,
        "timestamp": datetime.utcnow().isoformat(),
    })

    # 如果OTA端需要更新本地订单状态
    if req.action == "cancel":
        if stored.get("product_type") == "ticket":
            t_result = await db.execute(
                select(TicketOrder).where(TicketOrder.order_no == req.local_order_no)
            )
            t_order = t_result.scalar_one_or_none()
            if t_order and t_order.status == TicketOrderStatus.PAID:
                t_order.status = TicketOrderStatus.CANCELLED
                t_order.cancelled_at = datetime.utcnow()
                t_order.remark = f"[OTA回传] {req.reason or '管理员取消'}"
        else:
            h_result = await db.execute(
                select(HotelOrder).where(HotelOrder.order_no == req.local_order_no)
            )
            h_order = h_result.scalar_one_or_none()
            if h_order and h_order.status == HotelOrderStatus.PAID:
                h_order.status = HotelOrderStatus.CANCELLED
                h_order.cancelled_at = datetime.utcnow()
                h_order.cancel_reason = f"[OTA回传] {req.reason or '管理员取消'}"

    await db.flush()

    return {
        "success": True,
        "ota_order_id": ota_order_id,
        "platform": platform,
        "local_order_no": req.local_order_no,
        "action": req.action,
        "new_status": new_status.value,
        "callback_sign": mock_sign,
        "message": f"已向 {platform} 回传状态变更: {req.action}",
    }
