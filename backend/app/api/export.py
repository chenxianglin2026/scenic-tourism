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
    writer.writerow(["T20250701001", "zhangsan", "张三", "13800138000", "云溪景区", "成人票", "2025-07-15", "全天", "2", "196.00", "已支付", "2025-07-01 10:23", "2025-07-01 10:25", "2025-07-15 08:30"])
    writer.writerow(["T20250701002", "lisi", "李四", "13800138001", "云溪景区", "亲子票", "2025-07-16", "上午", "1", "168.00", "已支付", "2025-07-02 14:15", "2025-07-02 14:18", ""])
    writer.writerow(["T20250701003", "wangwu", "王五", "13800138002", "云溪景区", "老人票", "2025-07-17", "全天", "1", "78.00", "已核销", "2025-07-03 09:10", "2025-07-03 09:12", "2025-07-17 09:00"])
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
    writer.writerow(["2025-07-01", "12800", "5600", "1200", "19600"])
    writer.writerow(["2025-07-02", "15600", "7200", "1500", "24300"])
    writer.writerow(["2025-07-03", "11200", "4800", "900", "16900"])
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
    writer.writerow(["P20250701001", "P1停车场", "浙A12345", "小型车", "2025-07-01 08:30", "2025-07-01 16:45", "495", "25.00", "已完成", "已支付", "微信支付", "2025-07-01 16:45"])
    writer.writerow(["P20250701002", "P2停车场", "浙B67890", "小型车", "2025-07-01 09:15", "2025-07-01 14:20", "305", "20.00", "已完成", "已支付", "支付宝", "2025-07-01 14:20"])
    writer.writerow(["P20250701003", "P1停车场", "浙C11111", "大型车", "2025-07-01 10:00", "", "", "", "停车中", "未支付", "", ""])
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8-sig",
        headers={"Content-Disposition": "attachment; filename=parking_export.csv"},
    )
