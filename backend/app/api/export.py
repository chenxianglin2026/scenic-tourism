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
    """导出票务数据为CSV格式，支持日期范围/景区/票种筛选（占位）"""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "订单号", "用户名", "游客姓名", "游客电话", "景区",
        "票种", "游览日期", "时段", "数量", "金额", "状态",
        "下单时间", "支付时间", "核销时间",
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
    """导出营收报表为CSV格式，支持日/周/月维度（占位）"""
    period_header = "日期"
    if period == "week":
        period_header = "周"
    elif period == "month":
        period_header = "月份"

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([period_header, "门票收入", "酒店收入", "停车收入", "总计"])
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
    """导出停车记录为CSV格式（占位）"""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "记录ID", "停车场", "车牌号", "车辆类型", "入场时间", "出场时间",
        "停车时长(分钟)", "停车费(元)", "状态", "支付状态", "支付方式", "支付时间",
    ])
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8-sig",
        headers={"Content-Disposition": "attachment; filename=parking_export.csv"},
    )
