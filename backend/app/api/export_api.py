"""
景区智慧管理系统 - 导出接口 API
汇总导出入口（与已有 export.py 共享 /api/export 前缀）
"""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
import io
import csv

from app.db import (
    get_db, User, HotelOrder, HotelOrderStatus, ParkingRecord
)
from app.api.auth import require_admin

router = APIRouter(prefix="/api/export", tags=["导出汇总"])


# ── Schemas ──────────────────────────────────────────
class ExportSummaryResponse(BaseModel):
    code: int = 0
    msg: str = "ok"
    total_orders: int = 0
    total_parking: int = 0


# ── API ─────────────────────────────────────────────
@router.get("/summary", response_model=ExportSummaryResponse, summary="导出数据汇总")
async def export_summary(
    start_date: Optional[str] = Query(None, description="起始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """返回可导出数据的汇总统计"""
    hotel_q = select(func.count(HotelOrder.id))
    parking_q = select(func.count(ParkingRecord.id))

    if start_date:
        try:
            sd = date.fromisoformat(start_date)
            hotel_q = hotel_q.where(HotelOrder.created_at >= sd)
            parking_q = parking_q.where(ParkingRecord.checkin_time >= sd)
        except ValueError:
            raise HTTPException(status_code=400, detail="start_date 格式错误")

    if end_date:
        try:
            ed = date.fromisoformat(end_date)
            hotel_q = hotel_q.where(HotelOrder.created_at < ed)
            parking_q = parking_q.where(ParkingRecord.checkin_time < ed)
        except ValueError:
            raise HTTPException(status_code=400, detail="end_date 格式错误")

    hotel_result = await db.execute(hotel_q)
    parking_result = await db.execute(parking_q)

    return ExportSummaryResponse(
        total_orders=hotel_result.scalar() or 0,
        total_parking=parking_result.scalar() or 0,
    )


@router.get("/hotel-orders", summary="导出酒店订单（CSV）")
async def export_hotel_orders_csv(
    start_date: Optional[str] = Query(None, description="起始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD"),
    status: Optional[str] = Query(None, description="订单状态"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """导出酒店订单为CSV"""
    q = select(HotelOrder)
    if start_date:
        try:
            sd = date.fromisoformat(start_date)
            q = q.where(HotelOrder.created_at >= sd)
        except ValueError:
            raise HTTPException(status_code=400, detail="start_date 格式错误")
    if end_date:
        try:
            ed = date.fromisoformat(end_date)
            q = q.where(HotelOrder.created_at < ed)
        except ValueError:
            raise HTTPException(status_code=400, detail="end_date 格式错误")
    if status:
        q = q.where(HotelOrder.status == status)

    q = q.order_by(HotelOrder.created_at.desc())
    result = await db.execute(q)
    orders = result.scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["订单号", "酒店ID", "房型ID", "入住人", "电话", "入住日期", "离店日期", "间数", "天数", "总价", "状态", "下单时间"])
    for o in orders:
        writer.writerow([
            o.order_no, o.hotel_id, o.room_id, o.guest_name, o.guest_phone,
            o.checkin_date, o.checkout_date, o.room_count, o.nights,
            o.total_price, o.status,
            o.created_at.strftime("%Y-%m-%d %H:%M:%S") if o.created_at else "",
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=hotel_orders.csv"},
    )
