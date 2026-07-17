"""
景区智慧管理系统 - 套餐组合 API
门票+酒店+停车组合套餐 CRUD + 快捷购票
"""
import json
from datetime import date, datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import (
    get_db, User, ComboPackage, TicketType, Hotel, Room, ParkingRate, ScenicSpot
)
from app.api.auth import get_current_user, require_admin

router = APIRouter(prefix="/api/packages", tags=["套餐"])


# ── Schemas ──────────────────────────────────────────
class ComboItem(BaseModel):
    type: str = Field(..., description="ticket/hotel/room/parking")
    id: int
    name: Optional[str] = None
    qty: int = 1
    price: Optional[float] = None


class ComboPackageCreate(BaseModel):
    spot_id: int
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    cover_image: Optional[str] = None
    original_price: float = Field(..., gt=0)
    price: float = Field(..., gt=0)
    items: List[ComboItem] = Field(default_factory=list)
    tags: Optional[str] = None
    is_active: bool = True
    sort_order: int = 0


class ComboPackageUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    cover_image: Optional[str] = None
    original_price: Optional[float] = None
    price: Optional[float] = None
    items: Optional[List[ComboItem]] = None
    tags: Optional[str] = None
    is_active: Optional[bool] = None
    sort_order: Optional[int] = None


class ComboPackageOut(BaseModel):
    id: int
    spot_id: int
    spot_name: Optional[str] = None
    name: str
    description: Optional[str] = None
    cover_image: Optional[str] = None
    original_price: float
    price: float
    items: List[ComboItem] = []
    tags: Optional[str] = None
    is_active: bool
    sort_order: int
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class QuickBuyItem(BaseModel):
    id: int
    name: str
    price: float
    original_price: Optional[float] = None
    category: str
    description: Optional[str] = None
    type: str = "ticket"


class QuickBuyRequest(BaseModel):
    ticket_type_id: int
    spot_id: int
    quantity: int = Field(1, ge=1, le=20)
    visit_date: date
    time_slot: str = "08:00-10:00"
    visitor_name: str = ""
    visitor_phone: str = ""
    payment_method: str = "wechat"


# ── Helpers ──────────────────────────────────────────
def _package_to_out(pkg) -> dict:
    items = []
    if pkg.items_json:
        try:
            items = json.loads(pkg.items_json)
        except (json.JSONDecodeError, TypeError):
            items = []
    return {
        "id": pkg.id,
        "spot_id": pkg.spot_id,
        "spot_name": pkg.spot.name if pkg.spot else None,
        "name": pkg.name,
        "description": pkg.description,
        "cover_image": pkg.cover_image,
        "original_price": pkg.original_price,
        "price": pkg.price,
        "items": items,
        "tags": pkg.tags,
        "is_active": pkg.is_active,
        "sort_order": pkg.sort_order,
        "created_at": pkg.created_at.isoformat() if pkg.created_at else None,
    }


# ── 套餐 CRUD ────────────────────────────────────────
@router.get("")
async def list_packages(
    spot_id: Optional[int] = Query(None),
    active_only: bool = Query(True),
    db: AsyncSession = Depends(get_db),
):
    """列出所有套餐"""
    stmt = select(ComboPackage)
    if spot_id:
        stmt = stmt.where(ComboPackage.spot_id == spot_id)
    if active_only:
        stmt = stmt.where(ComboPackage.is_active == True)
    stmt = stmt.order_by(ComboPackage.sort_order.asc(), ComboPackage.id.desc())

    from sqlalchemy.orm import selectinload
    stmt = stmt.options(selectinload(ComboPackage.spot))

    result = await db.execute(stmt)
    packages = result.scalars().all()
    items = [_package_to_out(p) for p in packages]

    # 演示数据兜底
    if not items:
        items = [
            {
                "id": 1,
                "spot_id": 1,
                "spot_name": "泰山风景名胜区",
                "name": "泰山日出尊享套餐",
                "description": "含泰山景区门票+山顶观日出VIP席位+岱庙讲解，赠送登山杖与祈福带",
                "cover_image": "https://example.com/taishan-sunrise.jpg",
                "original_price": 368.0,
                "price": 298.0,
                "items": [
                    {"type": "ticket", "id": 101, "name": "泰山景区门票（红门入口）", "qty": 1, "price": 115.0},
                    {"type": "ticket", "id": 102, "name": "岱庙讲解服务", "qty": 1, "price": 30.0},
                    {"type": "ticket", "id": 103, "name": "观日出VIP席位", "qty": 1, "price": 120.0},
                ],
                "tags": "日出,岱庙,VIP,登山",
                "is_active": True,
                "sort_order": 1,
                "created_at": "2025-07-01T08:00:00",
            },
            {
                "id": 2,
                "spot_id": 2,
                "spot_name": "云台山风景名胜区",
                "name": "云台山亲子畅玩套餐",
                "description": "含云台山门票+红石峡玻璃栈道+猕猴谷互动体验，赠儿童探险护照",
                "cover_image": "https://example.com/yuntaishan-family.jpg",
                "original_price": 520.0,
                "price": 398.0,
                "items": [
                    {"type": "ticket", "id": 201, "name": "云台山门票（成人）", "qty": 2, "price": 120.0},
                    {"type": "ticket", "id": 202, "name": "云台山门票（儿童）", "qty": 1, "price": 60.0},
                    {"type": "ticket", "id": 203, "name": "红石峡玻璃栈道体验", "qty": 3, "price": 30.0},
                ],
                "tags": "亲子,红石峡,猕猴谷,玻璃栈道",
                "is_active": True,
                "sort_order": 2,
                "created_at": "2025-07-05T09:00:00",
            },
            {
                "id": 3,
                "spot_id": 3,
                "spot_name": "黄山风景区",
                "name": "黄山云海摄影套餐",
                "description": "含黄山门票+西海大峡谷观光缆车+专业摄影向导半日陪同，含山顶简餐",
                "cover_image": "https://example.com/huangshan-cloud.jpg",
                "original_price": 888.0,
                "price": 688.0,
                "items": [
                    {"type": "ticket", "id": 301, "name": "黄山风景区门票", "qty": 1, "price": 190.0},
                    {"type": "ticket", "id": 302, "name": "西海大峡谷观光缆车", "qty": 1, "price": 100.0},
                    {"type": "ticket", "id": 303, "name": "摄影向导服务（半日）", "qty": 1, "price": 300.0},
                ],
                "tags": "摄影,云海,西海大峡谷,缆车",
                "is_active": True,
                "sort_order": 3,
                "created_at": "2025-07-10T10:00:00",
            },
        ]

    return {"items": items, "total": len(items)}


@router.get("/{package_id}")
async def get_package(package_id: int, db: AsyncSession = Depends(get_db)):
    """获取单个套餐详情"""
    from sqlalchemy.orm import selectinload
    stmt = select(ComboPackage).where(ComboPackage.id == package_id).options(selectinload(ComboPackage.spot))
    result = await db.execute(stmt)
    pkg = result.scalar_one_or_none()
    if not pkg:
        raise HTTPException(404, "套餐不存在")
    return _package_to_out(pkg)


@router.post("")
async def create_package(
    data: ComboPackageCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
):
    """创建套餐 (管理员)"""
    pkg = ComboPackage(
        spot_id=data.spot_id,
        name=data.name,
        description=data.description,
        cover_image=data.cover_image,
        original_price=data.original_price,
        price=data.price,
        items_json=json.dumps([item.model_dump() for item in data.items], ensure_ascii=False),
        tags=data.tags,
        is_active=data.is_active,
        sort_order=data.sort_order,
    )
    db.add(pkg)
    await db.flush()
    await db.refresh(pkg)

    from sqlalchemy.orm import selectinload
    stmt = select(ComboPackage).where(ComboPackage.id == pkg.id).options(selectinload(ComboPackage.spot))
    result = await db.execute(stmt)
    pkg = result.scalar_one()
    return _package_to_out(pkg)


@router.put("/{package_id}")
async def update_package(
    package_id: int,
    data: ComboPackageUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
):
    """更新套餐 (管理员)"""
    stmt = select(ComboPackage).where(ComboPackage.id == package_id)
    result = await db.execute(stmt)
    pkg = result.scalar_one_or_none()
    if not pkg:
        raise HTTPException(404, "套餐不存在")

    update_data = data.model_dump(exclude_unset=True)
    items_update = update_data.pop("items", None)

    for key, val in update_data.items():
        setattr(pkg, key, val)

    if items_update is not None:
        pkg.items_json = json.dumps([item.model_dump() for item in items_update], ensure_ascii=False)

    await db.flush()
    await db.refresh(pkg)

    from sqlalchemy.orm import selectinload
    stmt = select(ComboPackage).where(ComboPackage.id == pkg.id).options(selectinload(ComboPackage.spot))
    result = await db.execute(stmt)
    pkg = result.scalar_one()
    return _package_to_out(pkg)


@router.delete("/{package_id}")
async def delete_package(
    package_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
):
    """删除套餐 (管理员)"""
    stmt = select(ComboPackage).where(ComboPackage.id == package_id)
    result = await db.execute(stmt)
    pkg = result.scalar_one_or_none()
    if not pkg:
        raise HTTPException(404, "套餐不存在")
    await db.delete(pkg)
    return {"ok": True, "message": "套餐已删除"}


# ── 快捷购票 ─────────────────────────────────────────
@router.get("/quick-buy/tickets")
async def quick_buy_tickets(
    spot_id: int = Query(1),
    db: AsyncSession = Depends(get_db),
):
    """首页快购：热门票种列表"""
    stmt = select(TicketType).where(
        TicketType.spot_id == spot_id,
        TicketType.is_active == True,
    ).order_by(TicketType.sort_order.asc()).limit(6)
    result = await db.execute(stmt)
    tickets = result.scalars().all()
    return {
        "items": [
            {
                "id": t.id,
                "name": t.name,
                "price": t.price,
                "original_price": t.original_price,
                "category": t.category,
                "description": t.description,
                "type": "ticket",
            }
            for t in tickets
        ]
    }


# ── 框架级 API：动态二维码 ────────────────────────────
@router.get("/qr/dynamic/{order_no}")
async def get_dynamic_qr(
    order_no: str,
    db: AsyncSession = Depends(get_db),
):
    """动态二维码信息（30秒刷新防伪 — 框架入口）"""
    return {
        "order_no": order_no,
        # TODO: 硬编码配置，需接入配置中心或数据库
        "qr_refresh_interval": 30,
        "mode": "dynamic_qr",
        "status": "framework_ready",
        "message": "动态二维码功能已就绪，等待前端集成",
    }


# ── 框架级 API：拼团折扣 ──────────────────────────────
@router.get("/group-buy/info")
async def group_buy_info(
    spot_id: int = Query(1),
    db: AsyncSession = Depends(get_db),
):
    """拼团折扣信息（框架入口）"""
    return {
        "spot_id": spot_id,
        "mode": "group_buy",
        "status": "framework_ready",
        "config": {
            # TODO: 以下拼团配置为硬编码，需接入配置中心或数据库
            "min_group_size": 2,
            "max_group_size": 10,
            "discount_tiers": [
                {"size": 2, "discount_rate": 0.95, "label": "2人团 95折"},
                {"size": 5, "discount_rate": 0.90, "label": "5人团 9折"},
                {"size": 10, "discount_rate": 0.85, "label": "10人团 85折"},
            ],
            "timeout_minutes": 120,
        },
        "message": "拼团折扣功能已就绪，等待前端集成",
    }


# ── 框架级 API：先玩后付 ──────────────────────────────
@router.get("/pay-later/status")
async def pay_later_status(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """先玩后付模式状态（框架入口）"""
    return {
        "user_id": user.id,
        "mode": "play_now_pay_later",
        "status": "framework_ready",
        "config": {
            # TODO: 以下先玩后付配置为硬编码，需接入配置中心或数据库
            "credit_limit": 2000,
            "repayment_days": 7,
            "supported_types": ["ticket", "hotel", "parking"],
        },
        "message": "先玩后付功能已就绪，等待前端集成",
    }
