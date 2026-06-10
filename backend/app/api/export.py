"""
景区智慧管理系统 - 数据导出 API
票务数据导出 / 营收报表导出 / 停车记录导出（CSV格式，管理员）
"""
import csv
import io
from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import (
    get_db, User, ScenicSpot, TicketType, TicketOrder, TicketOrderStatus,
    HotelOrder, HotelOrderStatus, ParkingRecord, ParkingRate,
)
from app.api.auth import require_admin

router = APIRouter(prefix="/api/export", tags=["数据导出"])


# ========== 1. 导出票务数据 (CSV) ==========

@router.get("/tickets", summary="导出票务数据（CSV, 管理员）")
async def export_tickets_csv(
    start_date: Optional[str] = Query(None, description="起始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD"),
    spot_id: Optional[int] = Query(None, description="景区ID"),
    ticket_type_id: Optional[int] = Query(None, description="票种ID"),
    status: Optional[str] = Query(None, description="订单状态"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """导出票务数据为CSV格式，支持日期范围/景区/票种筛选"""
    # 构建查询
    q = select(TicketOrder)

    if start_date:
        try:
            sd = date.fromisoformat(start_date)
            q = q.where(TicketOrder.visit_date >= sd)
        except ValueError:
            raise HTTPException(status_code=400, detail="start_date 格式错误（需要 YYYY-MM-DD）")

    if end_date:
        try:
            ed = date.fromisoformat(end_date)
            q = q.where(TicketOrder.visit_date <= ed)
        except ValueError:
            raise HTTPException(status_code=400, detail="end_date 格式错误（需要 YYYY-MM-DD）")

    if spot_id:
        q = q.where(TicketOrder.spot_id == spot_id)

    if ticket_type_id:
        q = q.where(TicketOrder.ticket_type_id == ticket_type_id)

    if status:
        q = q.where(TicketOrder.status == status)

    q = q.order_by(TicketOrder.created_at.desc())

    result = await db.execute(q)
    orders = result.scalars().all()

    # 收集所有需要的 ticket_type_id / spot_id / user_id 批量查询名称
    tt_ids = list(set(o.ticket_type_id for o in orders))
    spot_ids_list = list(set(o.spot_id for o in orders))
    user_ids = list(set(o.user_id for o in orders if o.user_id))

    # 批量查询票种名称
    tt_names = {}
    if tt_ids:
        tt_result = await db.execute(
            select(TicketType.id, TicketType.name).where(TicketType.id.in_(tt_ids))
        )
        for row in tt_result.all():
            tt_names[row[0]] = row[1]

    # 批量查询景区名称
    spot_names = {}
    if spot_ids_list:
        spot_result = await db.execute(
            select(ScenicSpot.id, ScenicSpot.name).where(ScenicSpot.id.in_(spot_ids_list))
        )
        for row in spot_result.all():
            spot_names[row[0]] = row[1]

    # 批量查询用户名
    user_names = {}
    if user_ids:
        user_result = await db.execute(
            select(User.id, User.username).where(User.id.in_(user_ids))
        )
        for row in user_result.all():
            user_names[row[0]] = row[1]

    # 生成CSV
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "订单号", "用户名", "游客姓名", "游客电话", "景区",
        "票种", "游览日期", "时段", "数量", "金额", "状态",
        "下单时间", "支付时间", "核销时间",
    ])

    status_map = {
        TicketOrderStatus.PENDING: "待支付",
        TicketOrderStatus.PAID: "已支付",
        TicketOrderStatus.VERIFIED: "已核销",
        TicketOrderStatus.CANCELLED: "已取消",
        TicketOrderStatus.REFUNDING: "退款中",
        TicketOrderStatus.REFUNDED: "已退款",
        TicketOrderStatus.EXPIRED: "已过期",
    }

    for o in orders:
        writer.writerow([
            o.order_no,
            user_names.get(o.user_id, f"用户{o.user_id}") if o.user_id else "",
            o.visitor_name or "",
            o.visitor_phone or "",
            spot_names.get(o.spot_id, f"景区{o.spot_id}"),
            tt_names.get(o.ticket_type_id, f"票种{o.ticket_type_id}"),
            o.visit_date.isoformat() if o.visit_date else "",
            o.time_slot,
            o.quantity,
            round(o.total_price, 2),
            status_map.get(o.status, o.status),
            o.created_at.strftime("%Y-%m-%d %H:%M:%S") if o.created_at else "",
            o.paid_at.strftime("%Y-%m-%d %H:%M:%S") if o.paid_at else "",
            o.verified_at.strftime("%Y-%m-%d %H:%M:%S") if o.verified_at else "",
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8-sig",
        headers={"Content-Disposition": "attachment; filename=tickets_export.csv"},
    )


# ========== 2. 导出营收报表 (CSV) ==========

@router.get("/revenue", summary="导出营收报表（CSV, 管理员）")
async def export_revenue_csv(
    period: str = Query("day", description="day/week/month 统计粒度"),
    start_date: Optional[str] = Query(None, description="起始日期 YYYY-MM-DD，不传默认30天"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD，不传默认今天"),
    spot_id: Optional[int] = Query(None, description="景区ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """导出营收报表为CSV格式，支持日/周/月维度"""
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
    if spot_id:
        spot_result = await db.execute(select(ScenicSpot).where(ScenicSpot.id == spot_id))
        if not spot_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="景区不存在")
        spot_ids = [spot_id]

    # 票务营收（按日期）
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

    # 酒店营收（按日期）
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

    # 停车营收（按日期）
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

    # 构建每日数据点
    daily_points = []
    cursor = sd
    while cursor <= ed:
        d_str = cursor.isoformat()
        t_rev = ticket_by_date.get(d_str, 0.0)
        h_rev = hotel_by_date.get(d_str, 0.0)
        p_rev = parking_by_date.get(d_str, 0.0)
        daily_points.append({
            "date": d_str,
            "ticket_revenue": round(t_rev, 2),
            "hotel_revenue": round(h_rev, 2),
            "parking_revenue": round(p_rev, 2),
            "total_revenue": round(t_rev + h_rev + p_rev, 2),
        })
        cursor += timedelta(days=1)

    # 按period聚合
    if period == "week":
        aggregated = {}
        for p in daily_points:
            d = date.fromisoformat(p["date"])
            iso_year, iso_week, _ = d.isocalendar()
            key = f"{iso_year}-W{iso_week:02d}"
            if key not in aggregated:
                week_start = d - timedelta(days=d.weekday())
                aggregated[key] = {
                    "label": f"{week_start.isoformat()} ~ {(week_start + timedelta(days=6)).isoformat()}",
                    "ticket_revenue": 0.0, "hotel_revenue": 0.0,
                    "parking_revenue": 0.0, "total_revenue": 0.0,
                }
            for field in ("ticket_revenue", "hotel_revenue", "parking_revenue", "total_revenue"):
                aggregated[key][field] += p[field]
        rows = [{"period": k, **v} for k, v in sorted(aggregated.items())]
        period_header = "周"
    elif period == "month":
        aggregated = {}
        for p in daily_points:
            key = p["date"][:7]
            if key not in aggregated:
                aggregated[key] = {
                    "label": key,
                    "ticket_revenue": 0.0, "hotel_revenue": 0.0,
                    "parking_revenue": 0.0, "total_revenue": 0.0,
                }
            for field in ("ticket_revenue", "hotel_revenue", "parking_revenue", "total_revenue"):
                aggregated[key][field] += p[field]
        rows = [{"period": k, **v} for k, v in sorted(aggregated.items())]
        period_header = "月份"
    else:
        rows = daily_points
        period_header = "日期"

    # 生成CSV
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([period_header, "门票收入", "酒店收入", "停车收入", "总计"])

    for row in rows:
        label = row.get("label", row.get("date", row.get("period", "")))
        writer.writerow([
            label,
            round(row.get("ticket_revenue", 0), 2),
            round(row.get("hotel_revenue", 0), 2),
            round(row.get("parking_revenue", 0), 2),
            round(row.get("total_revenue", 0), 2),
        ])

    # 汇总行
    total_ticket = round(sum(r.get("ticket_revenue", 0) for r in rows), 2)
    total_hotel = round(sum(r.get("hotel_revenue", 0) for r in rows), 2)
    total_parking = round(sum(r.get("parking_revenue", 0) for r in rows), 2)
    grand_total = round(total_ticket + total_hotel + total_parking, 2)
    writer.writerow(["合计", total_ticket, total_hotel, total_parking, grand_total])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8-sig",
        headers={"Content-Disposition": f"attachment; filename=revenue_{period}_export.csv"},
    )


# ========== 3. 导出停车记录 (CSV) ==========

@router.get("/parking", summary="导出停车记录（CSV, 管理员）")
async def export_parking_csv(
    start_date: Optional[str] = Query(None, description="起始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD"),
    spot_id: Optional[int] = Query(None, description="景区ID"),
    plate_number: Optional[str] = Query(None, description="车牌号搜索"),
    status: Optional[str] = Query(None, description="parking/completed"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """导出停车记录为CSV格式"""
    q = select(ParkingRecord)

    if start_date:
        try:
            sd = datetime.fromisoformat(start_date)
            q = q.where(ParkingRecord.checkin_time >= sd)
        except ValueError:
            raise HTTPException(status_code=400, detail="start_date 格式错误（需要 YYYY-MM-DD）")

    if end_date:
        try:
            ed = datetime.fromisoformat(end_date)
            # end_date 应包含整天
            ed_end = ed + timedelta(days=1)
            q = q.where(ParkingRecord.checkin_time < ed_end)
        except ValueError:
            raise HTTPException(status_code=400, detail="end_date 格式错误（需要 YYYY-MM-DD）")

    if plate_number:
        q = q.where(ParkingRecord.plate_number.like(f"%{plate_number}%"))

    if status:
        q = q.where(ParkingRecord.status == status)

    if spot_id:
        q = q.join(ParkingRate, ParkingRecord.rate_id == ParkingRate.id).where(
            ParkingRate.spot_id == spot_id
        )

    q = q.order_by(ParkingRecord.checkin_time.desc())

    result = await db.execute(q)
    records = result.scalars().all()

    # 批量查询停车场名称
    rate_ids = list(set(r.rate_id for r in records))
    rate_names = {}
    if rate_ids:
        rate_result = await db.execute(
            select(ParkingRate.id, ParkingRate.name).where(ParkingRate.id.in_(rate_ids))
        )
        for row in rate_result.all():
            rate_names[row[0]] = row[1]

    # 生成CSV
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "记录ID", "停车场", "车牌号", "车辆类型", "入场时间", "出场时间",
        "停车时长(分钟)", "停车费(元)", "状态", "支付状态", "支付方式", "支付时间",
    ])

    status_map = {
        "parking": "停车中",
        "completed": "已完成",
        "cancelled": "已取消",
    }
    pay_status_map = {
        "unpaid": "未支付",
        "paid": "已支付",
    }
    vehicle_type_map = {
        "car": "小汽车",
        "bus": "大巴",
        "truck": "卡车",
        "motorcycle": "摩托车",
    }

    for r in records:
        writer.writerow([
            r.id,
            rate_names.get(r.rate_id, f"停车场{r.rate_id}"),
            r.plate_number,
            vehicle_type_map.get(r.vehicle_type, r.vehicle_type),
            r.checkin_time.strftime("%Y-%m-%d %H:%M:%S") if r.checkin_time else "",
            r.checkout_time.strftime("%Y-%m-%d %H:%M:%S") if r.checkout_time else "",
            r.duration_minutes or "",
            round(r.total_fee, 2) if r.total_fee is not None else "",
            status_map.get(r.status, r.status),
            pay_status_map.get(r.pay_status, r.pay_status),
            r.pay_method or "",
            r.paid_at.strftime("%Y-%m-%d %H:%M:%S") if r.paid_at else "",
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8-sig",
        headers={"Content-Disposition": "attachment; filename=parking_export.csv"},
    )
