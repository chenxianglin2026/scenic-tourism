"""
景区智慧管理系统 - 停车模块 API
停车费率查询 / 入场 / 出场缴费 / 停车记录
"""
import uuid
from datetime import datetime, date
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db, User, ScenicSpot, ParkingRate, ParkingRecord
from app.api.auth import get_current_user, require_staff, require_admin

router = APIRouter(prefix="/api/parking", tags=["停车"])


# ── Schemas ──────────────────────────────────────────
class ParkingRateOut(BaseModel):
    id: int
    spot_id: int
    name: str
    vehicle_type: str
    first_hour_price: float
    additional_hour_price: float
    daily_cap: float
    free_minutes: int
    total_spots: int
    available_spots: int
    open_time: str
    close_time: str
    is_active: bool

    model_config = {"from_attributes": True}


class ParkingCheckinRequest(BaseModel):
    rate_id: int
    plate_number: str = Field(..., min_length=1, max_length=20, description="车牌号")
    vehicle_type: str = Field("car", description="car/bus/truck/motorcycle")


class ParkingManualCheckinRequest(BaseModel):
    plate_no: str = Field(..., min_length=1, max_length=20, description="车牌号")
    spot_id: int = Field(..., description="景区ID")
    entry_time: datetime = Field(..., description="入场时间")
    vehicle_type: str = Field("car", description="car/bus/truck/motorcycle")


class ParkingCheckoutRequest(BaseModel):
    pay_method: str = Field("wechat", description="wechat/alipay/cash")


class ParkingRecordOut(BaseModel):
    id: int
    rate_id: int
    parking_name: Optional[str] = None
    user_id: Optional[int] = None
    plate_number: str
    vehicle_type: str
    checkin_time: datetime
    checkout_time: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    total_fee: Optional[float] = None
    status: str
    pay_status: str
    pay_method: Optional[str] = None
    paid_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ParkingRecordListResponse(BaseModel):
    total: int
    items: List[ParkingRecordOut]


class ParkingRateCreate(BaseModel):
    spot_id: int
    name: str = Field(..., min_length=1, max_length=100)
    vehicle_type: str = Field("car", description="car/bus/truck/motorcycle")
    first_hour_price: float = Field(5.0, ge=0)
    additional_hour_price: float = Field(3.0, ge=0)
    daily_cap: float = Field(30.0, ge=0)
    free_minutes: int = Field(15, ge=0)
    total_spots: int = Field(200, ge=0)
    available_spots: Optional[int] = Field(None, ge=0)
    open_time: str = Field("00:00", max_length=5)
    close_time: str = Field("24:00", max_length=5)


class ParkingRateUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    vehicle_type: Optional[str] = None
    first_hour_price: Optional[float] = Field(None, ge=0)
    additional_hour_price: Optional[float] = Field(None, ge=0)
    daily_cap: Optional[float] = Field(None, ge=0)
    free_minutes: Optional[int] = Field(None, ge=0)
    total_spots: Optional[int] = Field(None, ge=0)
    available_spots: Optional[int] = Field(None, ge=0)
    open_time: Optional[str] = None
    close_time: Optional[str] = None
    is_active: Optional[bool] = None


class ParkingCheckinResponse(BaseModel):
    success: bool
    message: str
    record: Optional[ParkingRecordOut] = None
    record_id: Optional[int] = None


class ParkingCheckoutResponse(BaseModel):
    success: bool
    message: str
    record: Optional[ParkingRecordOut] = None
    duration_minutes: int = 0
    total_fee: float = 0.0


# ── 费率计算工具 ─────────────────────────────────────
def _calc_parking_fee(duration_minutes: int, rate: ParkingRate) -> float:
    """计算停车费用"""
    if duration_minutes <= rate.free_minutes:
        return 0.0
    
    # 超过免费时长，从第1分钟开始计费
    total_hours = duration_minutes / 60.0
    days = int(total_hours // 24)
    remaining_hours = total_hours % 24

    fee = 0.0
    # 每天封顶费用
    for _ in range(days):
        fee += rate.daily_cap
    
    # 剩余小时数
    if remaining_hours > 0:
        if remaining_hours <= 1:
            fee += rate.first_hour_price
        else:
            fee += rate.first_hour_price
            extra_hours = remaining_hours - 1
            fee += extra_hours * rate.additional_hour_price
            # 当天封顶
            fee = min(fee, fee - days * rate.daily_cap + rate.daily_cap)

    return round(min(fee, rate.daily_cap * (days + 1)), 2)


# ── 停车费率 ─────────────────────────────────────────
@router.get("/rates", response_model=List[ParkingRateOut], summary="停车费率列表")
async def list_parking_rates(
    spot_id: Optional[int] = Query(None, description="景区ID"),
    db: AsyncSession = Depends(get_db),
):
    """返回停车费率配置"""
    q = select(ParkingRate).where(ParkingRate.is_active == True)
    if spot_id:
        q = q.where(ParkingRate.spot_id == spot_id)
    result = await db.execute(q)
    return result.scalars().all()


@router.post("/rates", response_model=ParkingRateOut, status_code=201, summary="添加停车费率（管理员）")
async def create_parking_rate(
    req: ParkingRateCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """管理员添加停车费率配置"""
    spot_result = await db.execute(select(ScenicSpot).where(ScenicSpot.id == req.spot_id))
    if not spot_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="景区不存在")

    available_spots = req.available_spots if req.available_spots is not None else req.total_spots

    rate = ParkingRate(
        spot_id=req.spot_id,
        name=req.name,
        vehicle_type=req.vehicle_type,
        first_hour_price=req.first_hour_price,
        additional_hour_price=req.additional_hour_price,
        daily_cap=req.daily_cap,
        free_minutes=req.free_minutes,
        total_spots=req.total_spots,
        available_spots=available_spots,
        open_time=req.open_time,
        close_time=req.close_time,
    )
    db.add(rate)
    await db.flush()
    await db.refresh(rate)
    return rate


@router.put("/rates/{rate_id}", response_model=ParkingRateOut, summary="编辑停车费率（管理员）")
async def update_parking_rate(
    rate_id: int,
    req: ParkingRateUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """管理员编辑停车费率配置"""
    result = await db.execute(select(ParkingRate).where(ParkingRate.id == rate_id))
    rate = result.scalar_one_or_none()
    if not rate:
        raise HTTPException(status_code=404, detail="停车场费率不存在")

    update_data = req.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(rate, key, value)

    await db.flush()
    await db.refresh(rate)
    return rate


@router.delete("/rates/{rate_id}", summary="删除停车费率（管理员）")
async def delete_parking_rate(
    rate_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """管理员删除停车费率配置"""
    result = await db.execute(select(ParkingRate).where(ParkingRate.id == rate_id))
    rate = result.scalar_one_or_none()
    if not rate:
        raise HTTPException(status_code=404, detail="停车场费率不存在")
    # 检查是否有进行中的停车记录
    active_result = await db.execute(
        select(func.count(ParkingRecord.id)).where(
            ParkingRecord.rate_id == rate_id,
            ParkingRecord.status == "parking",
        )
    )
    active_count = active_result.scalar() or 0
    if active_count > 0:
        raise HTTPException(
            status_code=400,
            detail=f"该停车场有 {active_count} 辆车在场，无法删除。请等待所有车辆出场后再操作。",
        )
    await db.delete(rate)
    await db.flush()
    return {"success": True, "message": f"停车场费率 {rate.name} 已删除"}


# ── 停车入场 ─────────────────────────────────────────
@router.post("/checkin", response_model=ParkingCheckinResponse, summary="停车入场")
async def parking_checkin(
    req: ParkingCheckinRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """车辆入场登记，扣减可用车位"""
    # 校验停车场
    rate_result = await db.execute(
        select(ParkingRate).where(ParkingRate.id == req.rate_id, ParkingRate.is_active == True)
    )
    rate = rate_result.scalar_one_or_none()
    if not rate:
        raise HTTPException(status_code=404, detail="停车场不存在")

    # 校验车位
    if rate.available_spots <= 0:
        raise HTTPException(status_code=400, detail="车位已满")

    # 检查是否存在未出场记录
    exist_result = await db.execute(
        select(ParkingRecord).where(
            ParkingRecord.plate_number == req.plate_number,
            ParkingRecord.status == "parking",
        )
    )
    if exist_result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail=f"车牌 {req.plate_number} 已有在场记录，请先出场")

    # 创建停车记录
    record = ParkingRecord(
        rate_id=req.rate_id,
        user_id=current_user.id,
        plate_number=req.plate_number,
        vehicle_type=req.vehicle_type,
        checkin_time=datetime.utcnow(),
        status="parking",
        pay_status="unpaid",
    )
    db.add(record)

    # 扣减可用车位
    rate.available_spots -= 1
    if rate.available_spots < 0:
        raise HTTPException(status_code=400, detail="车位不足")

    await db.flush()
    await db.refresh(record)

    return ParkingCheckinResponse(
        success=True,
        message=f"车辆 {req.plate_number} 入场成功",
        record=ParkingRecordOut(
            id=record.id,
            rate_id=record.rate_id,
            parking_name=rate.name,
            user_id=record.user_id,
            plate_number=record.plate_number,
            vehicle_type=record.vehicle_type,
            checkin_time=record.checkin_time,
            status=record.status,
            pay_status=record.pay_status,
            created_at=record.created_at,
        ),
        record_id=record.id,
    )


# ── 管理员手动入场 ────────────────────────────────────
@router.post("/checkin/admin", response_model=ParkingCheckinResponse, summary="管理员手动入场")
async def parking_manual_checkin(
    req: ParkingManualCheckinRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """管理员手动登记车辆入场，可指定入场时间与景区"""
    rate_result = await db.execute(
        select(ParkingRate).where(
            ParkingRate.spot_id == req.spot_id,
            ParkingRate.is_active == True,
        ).order_by(ParkingRate.id.asc()).limit(1)
    )
    rate = rate_result.scalar_one_or_none()
    if not rate:
        raise HTTPException(status_code=404, detail="该景区未配置停车场")

    if rate.available_spots <= 0:
        raise HTTPException(status_code=400, detail="车位已满")

    exist_result = await db.execute(
        select(ParkingRecord).where(
            ParkingRecord.plate_number == req.plate_no,
            ParkingRecord.status == "parking",
        )
    )
    if exist_result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail=f"车牌 {req.plate_no} 已有在场记录，请先出场")

    record = ParkingRecord(
        rate_id=rate.id,
        user_id=current_user.id,
        plate_number=req.plate_no,
        vehicle_type=req.vehicle_type,
        checkin_time=req.entry_time,
        status="parking",
        pay_status="unpaid",
    )
    db.add(record)
    rate.available_spots -= 1
    if rate.available_spots < 0:
        raise HTTPException(status_code=400, detail="车位不足")

    await db.flush()
    await db.refresh(record)

    return ParkingCheckinResponse(
        success=True,
        message=f"车辆 {req.plate_no} 手动入场成功",
        record=ParkingRecordOut(
            id=record.id,
            rate_id=record.rate_id,
            parking_name=rate.name,
            user_id=record.user_id,
            plate_number=record.plate_number,
            vehicle_type=record.vehicle_type,
            checkin_time=record.checkin_time,
            status=record.status,
            pay_status=record.pay_status,
            created_at=record.created_at,
        ),
        record_id=record.id,
    )


# ── 停车出场 ─────────────────────────────────────────
@router.post("/checkout/{record_id}", response_model=ParkingCheckoutResponse, summary="停车出场缴费")
async def parking_checkout(
    record_id: int,
    req: ParkingCheckoutRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """车辆出场，计算费用，恢复车位"""
    # 查询停车记录
    record_result = await db.execute(
        select(ParkingRecord).where(ParkingRecord.id == record_id)
    )
    record = record_result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="停车记录不存在")

    if record.status != "parking":
        raise HTTPException(status_code=400, detail=f"该记录状态为 {record.status}，无法出场")

    # 查询费率
    rate_result = await db.execute(select(ParkingRate).where(ParkingRate.id == record.rate_id))
    rate = rate_result.scalar_one_or_none()
    if not rate:
        raise HTTPException(status_code=404, detail="停车场配置不存在")

    # 计算停车时长和费用
    checkout_time = datetime.utcnow()
    duration_seconds = (checkout_time - record.checkin_time).total_seconds()
    duration_minutes = max(1, int(duration_seconds / 60))
    total_fee = _calc_parking_fee(duration_minutes, rate)

    # 更新记录
    record.checkout_time = checkout_time
    record.duration_minutes = duration_minutes
    record.total_fee = total_fee
    record.status = "completed"
    record.pay_status = "paid"
    record.pay_method = req.pay_method
    record.paid_at = checkout_time

    # 恢复可用车位
    rate.available_spots = min(rate.total_spots, rate.available_spots + 1)

    await db.flush()
    await db.refresh(record)

    return ParkingCheckoutResponse(
        success=True,
        message=f"出场成功，停车 {duration_minutes} 分钟，费用 ¥{total_fee}",
        record=ParkingRecordOut(
            id=record.id,
            rate_id=record.rate_id,
            parking_name=rate.name,
            user_id=record.user_id,
            plate_number=record.plate_number,
            vehicle_type=record.vehicle_type,
            checkin_time=record.checkin_time,
            checkout_time=record.checkout_time,
            duration_minutes=record.duration_minutes,
            total_fee=record.total_fee,
            status=record.status,
            pay_status=record.pay_status,
            pay_method=record.pay_method,
            paid_at=record.paid_at,
            created_at=record.created_at,
        ),
        duration_minutes=duration_minutes,
        total_fee=total_fee,
    )


# ── 停车记录 ─────────────────────────────────────────
@router.get("/records", response_model=ParkingRecordListResponse, summary="我的停车记录")
async def list_parking_records(
    status: Optional[str] = Query(None, description="parking/completed"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """查询当前用户的停车记录"""
    base_q = select(ParkingRecord).where(ParkingRecord.user_id == current_user.id)
    count_q = select(func.count(ParkingRecord.id)).where(ParkingRecord.user_id == current_user.id)

    if status:
        base_q = base_q.where(ParkingRecord.status == status)
        count_q = count_q.where(ParkingRecord.status == status)

    total_result = await db.execute(count_q)
    total = total_result.scalar() or 0

    offset = (page - 1) * page_size
    items_result = await db.execute(
        base_q.order_by(ParkingRecord.checkin_time.desc()).offset(offset).limit(page_size)
    )
    records = items_result.scalars().all()

    items = []
    for r in records:
        # 获取停车场名称
        rate_result = await db.execute(select(ParkingRate).where(ParkingRate.id == r.rate_id))
        rate = rate_result.scalar_one_or_none()
        items.append(ParkingRecordOut(
            id=r.id,
            rate_id=r.rate_id,
            parking_name=rate.name if rate else None,
            user_id=r.user_id,
            plate_number=r.plate_number,
            vehicle_type=r.vehicle_type,
            checkin_time=r.checkin_time,
            checkout_time=r.checkout_time,
            duration_minutes=r.duration_minutes,
            total_fee=r.total_fee,
            status=r.status,
            pay_status=r.pay_status,
            pay_method=r.pay_method,
            paid_at=r.paid_at,
            created_at=r.created_at,
        ))

    return ParkingRecordListResponse(total=total, items=items)


# ── 全部停车记录（管理员） ──────────────────────────
@router.get("/records/all", response_model=ParkingRecordListResponse, summary="全部停车记录（管理员）")
async def list_all_parking_records(
    plate_number: Optional[str] = Query(None, description="车牌号搜索"),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """管理员查看全部停车记录"""
    base_q = select(ParkingRecord)
    count_q = select(func.count(ParkingRecord.id))

    if plate_number:
        base_q = base_q.where(ParkingRecord.plate_number.like(f"%{plate_number}%"))
        count_q = count_q.where(ParkingRecord.plate_number.like(f"%{plate_number}%"))
    if status:
        base_q = base_q.where(ParkingRecord.status == status)
        count_q = count_q.where(ParkingRecord.status == status)

    total_result = await db.execute(count_q)
    total = total_result.scalar() or 0

    offset = (page - 1) * page_size
    items_result = await db.execute(
        base_q.order_by(ParkingRecord.checkin_time.desc()).offset(offset).limit(page_size)
    )
    records = items_result.scalars().all()

    items = []
    for r in records:
        rate_result = await db.execute(select(ParkingRate).where(ParkingRate.id == r.rate_id))
        rate = rate_result.scalar_one_or_none()
        items.append(ParkingRecordOut(
            id=r.id,
            rate_id=r.rate_id,
            parking_name=rate.name if rate else None,
            user_id=r.user_id,
            plate_number=r.plate_number,
            vehicle_type=r.vehicle_type,
            checkin_time=r.checkin_time,
            checkout_time=r.checkout_time,
            duration_minutes=r.duration_minutes,
            total_fee=r.total_fee,
            status=r.status,
            pay_status=r.pay_status,
            pay_method=r.pay_method,
            paid_at=r.paid_at,
            created_at=r.created_at,
        ))

    return ParkingRecordListResponse(total=total, items=items)


# ── 管理员强制出场 ────────────────────────────────────
@router.post("/checkout/{record_id}/admin", response_model=ParkingCheckoutResponse, summary="管理员强制出场")
async def admin_force_checkout(
    record_id: int,
    req: ParkingCheckoutRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """管理员强制车辆出场，计算费用，恢复车位（无需是记录所有人）"""
    record_result = await db.execute(
        select(ParkingRecord).where(ParkingRecord.id == record_id)
    )
    record = record_result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="停车记录不存在")

    if record.status != "parking":
        raise HTTPException(status_code=400, detail=f"该记录状态为 {record.status}，无法出场")

    rate_result = await db.execute(select(ParkingRate).where(ParkingRate.id == record.rate_id))
    rate = rate_result.scalar_one_or_none()

    checkout_time = datetime.utcnow()
    duration_seconds = (checkout_time - record.checkin_time).total_seconds()
    duration_minutes = max(1, int(duration_seconds / 60))
    total_fee = _calc_parking_fee(duration_minutes, rate) if rate else 0.0

    record.checkout_time = checkout_time
    record.duration_minutes = duration_minutes
    record.total_fee = total_fee
    record.status = "completed"
    record.pay_status = "paid"
    record.pay_method = req.pay_method or "cash"
    record.paid_at = checkout_time

    if rate:
        rate.available_spots = min(rate.total_spots, rate.available_spots + 1)

    await db.flush()
    await db.refresh(record)

    return ParkingCheckoutResponse(
        success=True,
        message=f"管理员强制出场，停车 {duration_minutes} 分钟，费用 ¥{total_fee}",
        record=ParkingRecordOut(
            id=record.id,
            rate_id=record.rate_id,
            parking_name=rate.name if rate else None,
            user_id=record.user_id,
            plate_number=record.plate_number,
            vehicle_type=record.vehicle_type,
            checkin_time=record.checkin_time,
            checkout_time=record.checkout_time,
            duration_minutes=record.duration_minutes,
            total_fee=record.total_fee,
            status=record.status,
            pay_status=record.pay_status,
            pay_method=record.pay_method,
            paid_at=record.paid_at,
            created_at=record.created_at,
        ),
        duration_minutes=duration_minutes,
        total_fee=total_fee,
    )
