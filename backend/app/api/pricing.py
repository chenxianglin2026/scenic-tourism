"""
景区智慧管理系统 - 价格策略 API
多品类定价规则: 门票/酒店/停车/套餐
"""
from datetime import date, datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import (
    get_db, PricingRule, TicketType, Room, ParkingRate, ComboPackage
)
from app.api.auth import require_admin

router = APIRouter(prefix="/api/pricing", tags=["价格策略"])


# ── Schemas ──────────────────────────────────────────
class PricingRuleCreate(BaseModel):
    target_type: str = Field(..., pattern="^(ticket|hotel|parking|package)$")
    target_id: Optional[int] = None
    name: str = Field(..., min_length=1, max_length=100)
    rule_type: str = Field(..., pattern="^(weekend|weekday|holiday|advance_book|long_stay|seasonal)$")
    adjust_type: str = Field(..., pattern="^(percent|fixed|override)$")
    adjust_value: float
    priority: int = Field(0, ge=0, le=9999)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    weekdays: Optional[str] = None
    min_nights: Optional[int] = Field(None, ge=1)
    max_advance_days: Optional[int] = Field(None, ge=0)
    is_active: bool = True


class PricingRuleUpdate(BaseModel):
    target_type: Optional[str] = Field(None, pattern="^(ticket|hotel|parking|package)$")
    target_id: Optional[int] = None
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    rule_type: Optional[str] = Field(None, pattern="^(weekend|weekday|holiday|advance_book|long_stay|seasonal)$")
    adjust_type: Optional[str] = Field(None, pattern="^(percent|fixed|override)$")
    adjust_value: Optional[float] = None
    priority: Optional[int] = Field(None, ge=0, le=9999)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    weekdays: Optional[str] = None
    min_nights: Optional[int] = Field(None, ge=1)
    max_advance_days: Optional[int] = Field(None, ge=0)
    is_active: Optional[bool] = None


class PricingRuleOut(BaseModel):
    id: int
    target_type: str
    target_id: Optional[int] = None
    name: str
    rule_type: str
    adjust_type: str
    adjust_value: float
    priority: int
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    weekdays: Optional[str] = None
    min_nights: Optional[int] = None
    max_advance_days: Optional[int] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PricingRuleListResponse(BaseModel):
    total: int
    items: List[PricingRuleOut]


class CalculateRequest(BaseModel):
    target_type: str = Field(..., pattern="^(ticket|hotel|parking|package)$")
    target_id: int
    date: date
    nights: int = Field(1, ge=1)
    advance_days: Optional[int] = Field(None, ge=0)


class BreakdownItem(BaseModel):
    rule_id: int
    rule_name: str
    adjust_type: str
    adjust_value: float
    price_before: float
    price_after: float


class CalculateResponse(BaseModel):
    base_price: float
    final_price: float
    applied_rules: List[PricingRuleOut]
    breakdown: List[BreakdownItem]
    total: float


# ── 核心计算逻辑 ─────────────────────────────────────
def _match_rule(rule: PricingRule, target_type: str, target_id: int, query_date: date, nights: int, advance_days: Optional[int]) -> bool:
    """判断单条规则是否匹配给定条件"""
    if not rule.is_active:
        return False
    if rule.target_type != target_type:
        return False
    if rule.target_id is not None and rule.target_id != target_id:
        return False
    if rule.start_date is not None and query_date < rule.start_date:
        return False
    if rule.end_date is not None and query_date > rule.end_date:
        return False
    if rule.weekdays is not None:
        weekday_str = str(query_date.weekday())
        allowed = [w.strip() for w in rule.weekdays.split(",")]
        if weekday_str not in allowed:
            return False
    if rule.min_nights is not None and nights < rule.min_nights:
        return False
    if rule.max_advance_days is not None:
        if advance_days is None:
            return False
        if advance_days > rule.max_advance_days:
            return False
    return True


def _apply_adjustment(current_price: float, adjust_type: str, adjust_value: float) -> float:
    """应用单次调价"""
    if adjust_type == "percent":
        return current_price * (1 + adjust_value / 100.0)
    elif adjust_type == "fixed":
        return current_price + adjust_value
    elif adjust_type == "override":
        return adjust_value
    return current_price


async def get_base_price(
    db: AsyncSession,
    target_type: str,
    target_id: int,
    nights: int = 1,
) -> float:
    """获取基础价格"""
    if target_type == "ticket":
        result = await db.execute(select(TicketType.price).where(TicketType.id == target_id))
        price = result.scalar_one_or_none()
        if price is None:
            raise HTTPException(status_code=404, detail="票种不存在")
        return price
    elif target_type == "hotel":
        result = await db.execute(select(Room.price).where(Room.id == target_id))
        price = result.scalar_one_or_none()
        if price is None:
            raise HTTPException(status_code=404, detail="房型不存在")
        return price * nights
    elif target_type == "parking":
        result = await db.execute(select(ParkingRate.first_hour_price).where(ParkingRate.id == target_id))
        price = result.scalar_one_or_none()
        if price is None:
            raise HTTPException(status_code=404, detail="停车费率不存在")
        return price
    elif target_type == "package":
        result = await db.execute(select(ComboPackage.price).where(ComboPackage.id == target_id))
        price = result.scalar_one_or_none()
        if price is None:
            raise HTTPException(status_code=404, detail="套餐不存在")
        return price
    else:
        raise HTTPException(status_code=400, detail=f"不支持的 target_type: {target_type}")


async def calculate_price(
    db: AsyncSession,
    target_type: str,
    target_id: int,
    query_date: date,
    nights: int = 1,
    advance_days: Optional[int] = None,
) -> dict:
    """
    计算最终价格（内部函数，供订单模块调用）
    返回字典: {base_price, final_price, applied_rules, breakdown, total}
    """
    base_price = await get_base_price(db, target_type, target_id, nights)
    current_price = base_price

    # 查询所有活跃规则，按优先级升序
    result = await db.execute(
        select(PricingRule)
        .where(PricingRule.is_active == True)
        .where(PricingRule.target_type == target_type)
        .order_by(PricingRule.priority.asc(), PricingRule.id.asc())
    )
    rules = result.scalars().all()

    matched_rules = []
    breakdown = []

    for rule in rules:
        if _match_rule(rule, target_type, target_id, query_date, nights, advance_days):
            price_before = current_price
            current_price = _apply_adjustment(current_price, rule.adjust_type, rule.adjust_value)
            matched_rules.append(rule)
            breakdown.append({
                "rule_id": rule.id,
                "rule_name": rule.name,
                "adjust_type": rule.adjust_type,
                "adjust_value": rule.adjust_value,
                "price_before": round(price_before, 2),
                "price_after": round(current_price, 2),
            })

    final_price = round(max(current_price, 0), 2)
    return {
        "base_price": round(base_price, 2),
        "final_price": final_price,
        "applied_rules": matched_rules,
        "breakdown": breakdown,
        "total": final_price,
    }


# ── 管理员 CRUD ──────────────────────────────────────
@router.get("/rules", response_model=PricingRuleListResponse, summary="价格策略列表")
async def list_pricing_rules(
    target_type: Optional[str] = Query(None, pattern="^(ticket|hotel|parking|package)$"),
    is_active: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user = Depends(require_admin),
):
    """管理员查看价格策略列表"""
    base_q = select(PricingRule)
    count_q = select(func.count(PricingRule.id))

    if target_type:
        base_q = base_q.where(PricingRule.target_type == target_type)
        count_q = count_q.where(PricingRule.target_type == target_type)
    if is_active is not None:
        base_q = base_q.where(PricingRule.is_active == is_active)
        count_q = count_q.where(PricingRule.is_active == is_active)

    total_result = await db.execute(count_q)
    total = total_result.scalar() or 0

    offset = (page - 1) * page_size
    items_result = await db.execute(
        base_q.order_by(PricingRule.priority.asc(), PricingRule.id.desc()).offset(offset).limit(page_size)
    )
    items = items_result.scalars().all()

    return PricingRuleListResponse(total=total, items=list(items))


@router.post("/rules", response_model=PricingRuleOut, status_code=201, summary="创建价格策略")
async def create_pricing_rule(
    req: PricingRuleCreate,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(require_admin),
):
    """管理员创建价格策略"""
    rule = PricingRule(**req.model_dump())
    db.add(rule)
    await db.flush()
    await db.refresh(rule)
    return rule


@router.put("/rules/{rule_id}", response_model=PricingRuleOut, summary="编辑价格策略")
async def update_pricing_rule(
    rule_id: int,
    req: PricingRuleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(require_admin),
):
    """管理员编辑价格策略"""
    result = await db.execute(select(PricingRule).where(PricingRule.id == rule_id))
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="价格策略不存在")

    update_data = req.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(rule, key, value)

    await db.flush()
    await db.refresh(rule)
    return rule


@router.delete("/rules/{rule_id}", summary="删除价格策略")
async def delete_pricing_rule(
    rule_id: int,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(require_admin),
):
    """管理员删除价格策略"""
    result = await db.execute(select(PricingRule).where(PricingRule.id == rule_id))
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="价格策略不存在")
    await db.delete(rule)
    await db.flush()
    return {"success": True, "message": f"价格策略 '{rule.name}' 已删除"}


@router.get("/rules/{rule_id}/toggle", response_model=PricingRuleOut, summary="启停价格策略")
async def toggle_pricing_rule(
    rule_id: int,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(require_admin),
):
    """切换价格策略启停状态"""
    result = await db.execute(select(PricingRule).where(PricingRule.id == rule_id))
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="价格策略不存在")

    rule.is_active = not rule.is_active
    await db.flush()
    await db.refresh(rule)
    return rule


# ── 公开计算接口 ─────────────────────────────────────
@router.get("/calculate", summary="价格计算")
async def public_calculate(
    target_type: str = Query(..., pattern="^(ticket|hotel|parking|package)$"),
    target_id: int = Query(..., ge=1),
    date: date = Query(..., description="查询日期"),
    nights: int = Query(1, ge=1),
    advance_days: Optional[int] = Query(None, ge=0, description="提前预订天数（酒店/提前预订策略用）"),
    db: AsyncSession = Depends(get_db),
):
    """
    公开价格计算接口
    参数: target_type, target_id, date, nights, advance_days
    返回: {base_price, final_price, applied_rules, breakdown, total}
    """
    result = await calculate_price(db, target_type, target_id, date, nights, advance_days)
    # 序列化 applied_rules
    result["applied_rules"] = [PricingRuleOut.model_validate(r) for r in result["applied_rules"]]
    result["breakdown"] = [BreakdownItem.model_validate(b) for b in result["breakdown"]]
    return CalculateResponse.model_validate(result)
