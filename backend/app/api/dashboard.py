"""
景区智慧管理系统 - 仪表盘统计 API
管理后台统计数据
"""
from datetime import date, datetime, timedelta
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import (
    get_db, User, ScenicSpot, TicketType, TicketOrder, TicketOrderStatus,
    Hotel, Room, HotelOrder, HotelOrderStatus, ParkingRate, ParkingRecord, PaymentRecord
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


# ── 营收报表 API ─────────────────────────────────────

class RevenuePoint(BaseModel):
    date: str
    ticket_revenue: float = 0.0
    hotel_revenue: float = 0.0
    parking_revenue: float = 0.0
    total_revenue: float = 0.0


class RevenueReportResponse(BaseModel):
    code: int = 0
    msg: str = "ok"
    data: dict = {}


@router.get("/revenue", response_model=RevenueReportResponse, summary="营收报表（按日/周/月）")
async def revenue_report(
    period: str = Query("day", description="day/week/month，统计粒度"),
    start_date: Optional[str] = Query(None, description="起始日期 YYYY-MM-DD，不传默认30天"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD，不传默认今天"),
    spot_id: Optional[int] = Query(None, description="景区ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """营收报表：汇总票务+酒店+停车营收，支持按日/周/月分组"""
    if period not in ("day", "week", "month"):
        raise HTTPException(status_code=400, detail="period 必须是 day/week/month")

    # 日期范围
    today = date.today()
    if end_date:
        try:
            ed = date.fromisoformat(end_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="end_date 格式错误")
    else:
        ed = today

    if start_date:
        try:
            sd = date.fromisoformat(start_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="start_date 格式错误")
    else:
        sd = ed - timedelta(days=30)

    if sd > ed:
        raise HTTPException(status_code=400, detail="start_date 不能晚于 end_date")

    # 景区过滤
    spot_ids = []
    spot_filter_clause = True
    if spot_id:
        result = await db.execute(select(ScenicSpot).where(ScenicSpot.id == spot_id))
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="景区不存在")
        spot_ids = [spot_id]
        spot_filter_clause = TicketOrder.spot_id.in_(spot_ids)

    # ── 票务营收 ──
    ticket_q = select(
        func.date(TicketOrder.paid_at).label("d"),
        func.coalesce(func.sum(TicketOrder.total_price), 0.0),
    ).where(
        TicketOrder.status.in_([TicketOrderStatus.PAID, TicketOrderStatus.VERIFIED]),
        TicketOrder.paid_at >= datetime(sd.year, sd.month, sd.day),
        TicketOrder.paid_at < datetime(ed.year, ed.month, ed.day) + timedelta(days=1),
    )
    if spot_ids:
        ticket_q = ticket_q.where(TicketOrder.spot_id.in_(spot_ids))
    ticket_q = ticket_q.group_by(func.date(TicketOrder.paid_at))
    ticket_result = await db.execute(ticket_q)
    ticket_by_date = {str(d): float(v) for d, v in ticket_result.all()}

    # ── 酒店营收 ──
    hotel_q = select(
        func.date(HotelOrder.paid_at).label("d"),
        func.coalesce(func.sum(HotelOrder.total_price), 0.0),
    ).where(
        HotelOrder.status.in_([HotelOrderStatus.PAID, HotelOrderStatus.CHECKED_IN, HotelOrderStatus.COMPLETED]),
        HotelOrder.paid_at >= datetime(sd.year, sd.month, sd.day),
        HotelOrder.paid_at < datetime(ed.year, ed.month, ed.day) + timedelta(days=1),
    )
    hotel_result = await db.execute(hotel_q)
    hotel_by_date = {str(d): float(v) for d, v in hotel_result.all()}

    # ── 停车营收 ──
    parking_q = select(
        func.date(ParkingRecord.paid_at).label("d"),
        func.coalesce(func.sum(ParkingRecord.total_fee), 0.0),
    ).where(
        ParkingRecord.pay_status == "paid",
        ParkingRecord.paid_at >= datetime(sd.year, sd.month, sd.day),
        ParkingRecord.paid_at < datetime(ed.year, ed.month, ed.day) + timedelta(days=1),
    )
    parking_result = await db.execute(parking_q)
    parking_by_date = {str(d): float(v) for d, v in parking_result.all()}

    # ── 构建分组数据 ──
    points = []
    cursor = sd
    while cursor <= ed:
        d_str = cursor.isoformat()
        t_rev = ticket_by_date.get(d_str, 0.0)
        h_rev = hotel_by_date.get(d_str, 0.0)
        p_rev = parking_by_date.get(d_str, 0.0)
        points.append(RevenuePoint(
            date=d_str,
            ticket_revenue=round(t_rev, 2),
            hotel_revenue=round(h_rev, 2),
            parking_revenue=round(p_rev, 2),
            total_revenue=round(t_rev + h_rev + p_rev, 2),
        ))
        cursor += timedelta(days=1)

    # ── 按 period 聚合 ──
    if period == "week":
        aggregated = {}
        for p in points:
            d = date.fromisoformat(p.date)
            iso_year, iso_week, _ = d.isocalendar()
            key = f"{iso_year}-W{iso_week:02d}"
            if key not in aggregated:
                week_start = d - timedelta(days=d.weekday())
                aggregated[key] = {"label": f"{week_start.isoformat()} ~ {(week_start + timedelta(days=6)).isoformat()}", "ticket_revenue": 0.0, "hotel_revenue": 0.0, "parking_revenue": 0.0, "total_revenue": 0.0}
            aggregated[key]["ticket_revenue"] += p.ticket_revenue
            aggregated[key]["hotel_revenue"] += p.hotel_revenue
            aggregated[key]["parking_revenue"] += p.parking_revenue
            aggregated[key]["total_revenue"] += p.total_revenue
        pivot = [{"period": k, **{kk: round(vv, 2) if isinstance(vv, float) else vv for kk, vv in v.items()}} for k, v in sorted(aggregated.items())]
    elif period == "month":
        aggregated = {}
        for p in points:
            key = p.date[:7]  # YYYY-MM
            if key not in aggregated:
                aggregated[key] = {"label": key, "ticket_revenue": 0.0, "hotel_revenue": 0.0, "parking_revenue": 0.0, "total_revenue": 0.0}
            aggregated[key]["ticket_revenue"] += p.ticket_revenue
            aggregated[key]["hotel_revenue"] += p.hotel_revenue
            aggregated[key]["parking_revenue"] += p.parking_revenue
            aggregated[key]["total_revenue"] += p.total_revenue
        pivot = [{"period": k, **{kk: round(vv, 2) if isinstance(vv, float) else vv for kk, vv in v.items()}} for k, v in sorted(aggregated.items())]
    else:
        # daily
        pivot = [p.model_dump() for p in points]

    # 汇总
    total_ticket = round(sum(p.ticket_revenue for p in points), 2)
    total_hotel = round(sum(p.hotel_revenue for p in points), 2)
    total_parking = round(sum(p.parking_revenue for p in points), 2)
    grand_total = round(total_ticket + total_hotel + total_parking, 2)

    return RevenueReportResponse(data={
        "period": period,
        "start_date": sd.isoformat(),
        "end_date": ed.isoformat(),
        "spot_id": spot_id,
        "summary": {
            "ticket_revenue": total_ticket,
            "hotel_revenue": total_hotel,
            "parking_revenue": total_parking,
            "total_revenue": grand_total,
        },
        "items": pivot,
    })
