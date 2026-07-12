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
    get_db, User, TicketOrder, ParkingRecord
)
from app.api.auth import require_admin

router = APIRouter(prefix="/api/export", tags=["导出汇总"])


# ── Schemas ──────────────────────────────────────────
class ExportSummaryResponse(BaseModel):
    code: int = 0
    msg: str = "ok"
    total_tickets: int = 0
    total_parking: int = 0


# ── API ─────────────────────────────────────────────
@router.get("/summary", response_model=ExportSummaryResponse, summary="导出数据汇总")
async def export_summary(
    start_date: Optional[str] = Query(None, description="起始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """返回可导出数据的汇总统计（酒店订单统计暂缺，仅统计票务+停车）"""
    ticket_q = select(func.count(TicketOrder.id))
    parking_q = select(func.count(ParkingRecord.id))

    if start_date:
        try:
            sd = date.fromisoformat(start_date)
            ticket_q = ticket_q.where(TicketOrder.created_at >= sd)
            parking_q = parking_q.where(ParkingRecord.checkin_time >= sd)
        except ValueError:
            raise HTTPException(status_code=400, detail="start_date 格式错误")

    if end_date:
        try:
            ed = date.fromisoformat(end_date)
            ticket_q = ticket_q.where(TicketOrder.created_at < ed)
            parking_q = parking_q.where(ParkingRecord.checkin_time < ed)
        except ValueError:
            raise HTTPException(status_code=400, detail="end_date 格式错误")

    ticket_result = await db.execute(ticket_q)
    parking_result = await db.execute(parking_q)

    return ExportSummaryResponse(
        total_tickets=ticket_result.scalar() or 0,
        total_parking=parking_result.scalar() or 0,
    )


@router.get("/ticket-orders", summary="导出票务订单（CSV）")
async def export_ticket_orders_csv(
    start_date: Optional[str] = Query(None, description="起始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD"),
    status: Optional[str] = Query(None, description="订单状态"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """导出票务订单为CSV"""
    q = select(TicketOrder)
    if start_date:
        try:
            sd = date.fromisoformat(start_date)
            q = q.where(TicketOrder.created_at >= sd)
        except ValueError:
            raise HTTPException(status_code=400, detail="start_date 格式错误")
    if end_date:
        try:
            ed = date.fromisoformat(end_date)
            q = q.where(TicketOrder.created_at < ed)
        except ValueError:
            raise HTTPException(status_code=400, detail="end_date 格式错误")
    if status:
        q = q.where(TicketOrder.status == status)

    q = q.order_by(TicketOrder.created_at.desc())
    result = await db.execute(q)
    orders = result.scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["订单号", "票种ID", "景区ID", "数量", "游览日期", "时段", "总价", "状态", "游客姓名", "游客电话", "下单时间"])
    for o in orders:
        writer.writerow([
            o.order_no, o.ticket_type_id, o.spot_id, o.quantity,
            o.visit_date, o.time_slot, o.total_price, o.status,
            o.visitor_name or "", o.visitor_phone or "",
            o.created_at.strftime("%Y-%m-%d %H:%M:%S") if o.created_at else "",
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=ticket_orders.csv"},
    )
