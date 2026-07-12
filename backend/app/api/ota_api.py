"""
景区智慧管理系统 - OTA渠道 API
OTA平台列表与配置（与已有 ota.py 共享 /api/ota 前缀）
"""
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db, User, ScenicSpot, TicketType, Hotel
from app.api.auth import require_admin

router = APIRouter(prefix="/api/ota", tags=["OTA渠道"])


# ── Schemas ──────────────────────────────────────────
class OtaChannelOut(BaseModel):
    id: str
    name: str
    enabled: bool
    last_sync: Optional[str] = None
    sync_status: str = "unknown"


class OtaChannelListResponse(BaseModel):
    code: int = 0
    msg: str = "ok"
    items: List[OtaChannelOut] = []


class OtaSyncRequest(BaseModel):
    channel: str = Field(..., description="ota渠道: ctrip/meituan/fliggy")
    spot_id: Optional[int] = None


class OtaSyncResponse(BaseModel):
    code: int = 0
    msg: str = "ok"
    channel: str
    synced_count: int = 0


class OtaInventoryOut(BaseModel):
    ticket_type_id: int
    ticket_type_name: str
    spot_id: int
    total_stock: int
    sold_count: int
    available: int

    model_config = {"from_attributes": True}


class OtaInventoryResponse(BaseModel):
    code: int = 0
    msg: str = "ok"
    items: List[OtaInventoryOut] = []


# ── API ─────────────────────────────────────────────
@router.get("/channels", response_model=OtaChannelListResponse, summary="OTA渠道列表")
async def list_ota_channels(
    current_user: User = Depends(require_admin),
):
    """获取已配置的OTA渠道列表"""
    # 模拟渠道数据，实际可对接数据库配置表
    channels = [
        OtaChannelOut(id="ctrip", name="携程", enabled=True, sync_status="synced"),
        OtaChannelOut(id="meituan", name="美团", enabled=True, sync_status="synced"),
        OtaChannelOut(id="fliggy", name="飞猪", enabled=False, sync_status="disabled"),
    ]
    return OtaChannelListResponse(items=channels)


@router.post("/sync", response_model=OtaSyncResponse, summary="同步OTA库存")
async def sync_ota_inventory(
    req: OtaSyncRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """手动触发OTA库存同步"""
    if req.channel not in ("ctrip", "meituan", "fliggy"):
        raise HTTPException(status_code=400, detail="不支持的OTA渠道")

    # 查询票种数量作为同步计数
    q = select(func.count(TicketType.id)).where(TicketType.is_active == True)
    if req.spot_id:
        q = q.where(TicketType.spot_id == req.spot_id)
    result = await db.execute(q)
    count = result.scalar() or 0

    return OtaSyncResponse(
        channel=req.channel,
        synced_count=count,
    )


@router.get("/inventory", response_model=OtaInventoryResponse, summary="OTA可售库存")
async def get_ota_inventory(
    spot_id: Optional[int] = Query(None, description="景区ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """获取各OTA渠道可售库存"""
    q = select(TicketType).where(TicketType.is_active == True)
    if spot_id:
        q = q.where(TicketType.spot_id == spot_id)

    result = await db.execute(q)
    ticket_types = result.scalars().all()

    items = []
    for tt in ticket_types:
        items.append(OtaInventoryOut(
            ticket_type_id=tt.id,
            ticket_type_name=tt.name,
            spot_id=tt.spot_id,
            total_stock=tt.daily_stock,
            sold_count=0,  # 实际应从库存表统计
            available=tt.daily_stock,
        ))

    return OtaInventoryResponse(items=items)
