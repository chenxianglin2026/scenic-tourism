"""
景区智慧管理系统 - 仪表盘统计 API
管理后台统计数据
"""
from datetime import date, datetime, timedelta
from typing import Optional, List

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import (
    get_db, User, ScenicSpot, TicketType, TicketOrder, TicketOrderStatus,
    Hotel, Room, HotelOrder, HotelOrderStatus
)
from app.api.auth import get_current_user, require_admin

router = APIRouter(prefix="/api/dashboard", tags=["仪表盘"])


# ── Schemas ──────────────────────────────────────────
class TrendPoint(BaseModel):
    date: str
    value: float
    label: str = ""


class DashboardStats(BaseModel):
    spot_id: Optional[int] = None
    spot_name: Optional[str] = None
    # 票务
    total_ticket_types: int = 0
    tickets_sold_today: int = 0
    tickets_verified_today: int = 0
    ticket_revenue_today: float = 0.0
    # 酒店
    total_hotels: int = 0
    total_rooms: int = 0
    occupied_rooms: int = 0
    hotel_revenue_today: float = 0.0
    # 汇总
    total_revenue_today: float = 0.0
    # 趋势
    ticket_revenue_trend: List[TrendPoint] = []
    tickets_sold_trend: List[TrendPoint] = []


class DashboardResponse(BaseModel):
    code: int = 0
    data: DashboardStats
    msg: str = "ok"


# ── API ─────────────────────────────────────────────
@router.get("/stats", response_model=DashboardResponse, summary="仪表盘完整统计数据")
async def dashboard_stats(
    spot_id: Optional[int] = Query(None, description="景区ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    today = date.today()
    today_start = datetime(today.year, today.month, today.day)
    today_end = today_start + timedelta(days=1)

    stats = DashboardStats()

    # 景区过滤
    spot_ids = []
    if spot_id:
        result = await db.execute(select(ScenicSpot).where(ScenicSpot.id == spot_id, ScenicSpot.is_active == True))
        spot = result.scalar_one_or_none()
        if not spot:
            from fastapi import HTTPException
            raise HTTPException(404, "景区不存在")
        spot_ids = [spot.id]
        stats.spot_id = spot_id
        stats.spot_name = spot.name
    else:
        result = await db.execute(select(ScenicSpot).where(ScenicSpot.is_active == True))
        spots = result.scalars().all()
        spot_ids = [s.id for s in spots]

    if not spot_ids:
        return DashboardResponse(data=stats, msg="暂无景区数据")

    # ── 票务统计 ──
    # 票种数量
    tt_result = await db.execute(
        select(func.count(TicketType.id)).where(
            TicketType.spot_id.in_(spot_ids),
            TicketType.is_active == True,
        )
    )
    stats.total_ticket_types = tt_result.scalar() or 0

    # 今日售出票数
    sold_result = await db.execute(
        select(func.coalesce(func.sum(TicketOrder.quantity), 0)).where(
            TicketOrder.spot_id.in_(spot_ids),
            TicketOrder.created_at >= today_start,
            TicketOrder.created_at < today_end,
            TicketOrder.status.in_([TicketOrderStatus.PAID, TicketOrderStatus.VERIFIED]),
        )
    )
    stats.tickets_sold_today = int(sold_result.scalar() or 0)

    # 今日核销数
    verified_result = await db.execute(
        select(func.count(TicketOrder.id)).where(
            TicketOrder.spot_id.in_(spot_ids),
            TicketOrder.status == TicketOrderStatus.VERIFIED,
            TicketOrder.verified_at >= today_start,
            TicketOrder.verified_at < today_end,
        )
    )
    stats.tickets_verified_today = verified_result.scalar() or 0

    # 今日票务营收
    ticket_rev = await db.execute(
        select(func.coalesce(func.sum(TicketOrder.total_price), 0.0)).where(
            TicketOrder.spot_id.in_(spot_ids),
            TicketOrder.created_at >= today_start,
            TicketOrder.created_at < today_end,
            TicketOrder.status.in_([TicketOrderStatus.PAID, TicketOrderStatus.VERIFIED]),
        )
    )
    stats.ticket_revenue_today = round(float(ticket_rev.scalar() or 0), 2)

    # ── 酒店统计 ──
    # 酒店数量
    hotel_q = select(func.count(Hotel.id)).where(Hotel.is_active == True)
    if spot_ids:
        hotel_q = hotel_q.where(Hotel.spot_id.in_(spot_ids))
    hotel_count = await db.execute(hotel_q)
    stats.total_hotels = hotel_count.scalar() or 0

    # 总房间数
    room_q = select(func.coalesce(func.sum(Room.total_count), 0)).where(Room.is_active == True)
    if spot_ids:
        # 关联酒店到景区
        room_q = room_q.where(Room.hotel_id.in_(
            select(Hotel.id).where(Hotel.spot_id.in_(spot_ids))
        ))
    room_total = await db.execute(room_q)
    stats.total_rooms = int(room_total.scalar() or 0)

    # 已占用房间数
    occupied_q = select(func.coalesce(func.sum(Room.total_count - Room.available_count), 0)).where(Room.is_active == True)
    if spot_ids:
        occupied_q = occupied_q.where(Room.hotel_id.in_(
            select(Hotel.id).where(Hotel.spot_id.in_(spot_ids))
        ))
    occ_result = await db.execute(occupied_q)
    stats.occupied_rooms = int(occ_result.scalar() or 0)

    # 今日酒店营收
    hotel_rev = await db.execute(
        select(func.coalesce(func.sum(HotelOrder.total_price), 0.0)).where(
            HotelOrder.created_at >= today_start,
            HotelOrder.created_at < today_end,
            HotelOrder.status.in_([HotelOrderStatus.PAID, HotelOrderStatus.CHECKED_IN, HotelOrderStatus.COMPLETED]),
        )
    )
    stats.hotel_revenue_today = round(float(hotel_rev.scalar() or 0), 2)

    # 汇总总收入
    stats.total_revenue_today = round(stats.ticket_revenue_today + stats.hotel_revenue_today, 2)

    # ── 近7天票务营收趋势 ──
    ticket_revenue_trend = []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        ds = datetime(d.year, d.month, d.day)
        de = ds + timedelta(days=1)
        r = await db.execute(
            select(func.coalesce(func.sum(TicketOrder.total_price), 0.0)).where(
                TicketOrder.created_at >= ds,
                TicketOrder.created_at < de,
                TicketOrder.status.in_([TicketOrderStatus.PAID, TicketOrderStatus.VERIFIED]),
            )
        )
        val = round(float(r.scalar() or 0), 2)
        ticket_revenue_trend.append(TrendPoint(
            date=d.isoformat(), value=val, label=f"{d.month}/{d.day}"
        ))
    stats.ticket_revenue_trend = ticket_revenue_trend

    # ── 近7天售出趋势 ──
    tickets_sold_trend = []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        ds = datetime(d.year, d.month, d.day)
        de = ds + timedelta(days=1)
        r = await db.execute(
            select(func.coalesce(func.sum(TicketOrder.quantity), 0)).where(
                TicketOrder.created_at >= ds,
                TicketOrder.created_at < de,
                TicketOrder.status.in_([TicketOrderStatus.PAID, TicketOrderStatus.VERIFIED]),
            )
        )
        val = int(r.scalar() or 0)
        tickets_sold_trend.append(TrendPoint(
            date=d.isoformat(), value=val, label=f"{d.month}/{d.day}"
        ))
    stats.tickets_sold_trend = tickets_sold_trend

    return DashboardResponse(data=stats)
