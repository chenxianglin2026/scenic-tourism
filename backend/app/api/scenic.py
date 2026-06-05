"""
景区智慧管理系统 - 景区信息 API
景区介绍 / 公告 / 导览点位(POI)
"""
import json
from datetime import datetime, date, timedelta
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import get_db, User, ScenicSpot, Announcement, Poi, TicketType
from app.api.auth import get_current_user, require_admin

router = APIRouter(prefix="/api/scenic", tags=["景区信息"])


# ── Schemas ──────────────────────────────────────────
class ScenicInfoOut(BaseModel):
    id: int
    name: str
    address: str
    city: str
    district: Optional[str] = None
    phone: Optional[str] = None
    description: Optional[str] = None
    cover_image: Optional[str] = None
    images: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    open_time: str
    close_time: str
    daily_limit: int
    rating: float
    is_active: bool
    ticket_types: List[dict] = []
    latest_announcements: List[dict] = []

    model_config = {"from_attributes": True}


class AnnouncementOut(BaseModel):
    id: int
    spot_id: int
    title: str
    content: str
    category: str
    priority: int
    is_published: bool
    published_at: datetime
    expires_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AnnouncementListResponse(BaseModel):
    total: int
    items: List[AnnouncementOut]


class AnnouncementCreate(BaseModel):
    spot_id: int
    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1)
    category: str = Field("notice", description="notice/event/maintenance/emergency")
    priority: int = Field(0, ge=0, le=2, description="0-低 1-中 2-高")
    expires_at: Optional[datetime] = None


class PoiOut(BaseModel):
    id: int
    spot_id: int
    name: str
    category: str
    description: Optional[str] = None
    lat: float
    lng: float
    images: Optional[str] = None
    audio_url: Optional[str] = None
    sort_order: int
    is_active: bool

    model_config = {"from_attributes": True}


class ScenicInfoUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=200)
    address: Optional[str] = Field(None, max_length=500)
    city: Optional[str] = Field(None, max_length=50)
    district: Optional[str] = Field(None, max_length=50)
    phone: Optional[str] = Field(None, max_length=20)
    description: Optional[str] = None
    cover_image: Optional[str] = None
    images: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    open_time: Optional[str] = None
    close_time: Optional[str] = None
    daily_limit: Optional[int] = Field(None, ge=1)
    rating: Optional[float] = Field(None, ge=0, le=5)
    is_active: Optional[bool] = None


class AnnouncementUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    content: Optional[str] = Field(None, min_length=1)
    category: Optional[str] = Field(None, description="notice/event/maintenance/emergency")
    priority: Optional[int] = Field(None, ge=0, le=2)
    is_published: Optional[bool] = None
    expires_at: Optional[datetime] = None


class WeatherResponse(BaseModel):
    spot_id: int
    city: str
    temperature: float
    weather: str
    humidity: int
    wind: str
    aqi: int
    update_time: str
    forecast: List[dict]


# ── 辅助函数 ─────────────────────────────────────────
def _parse_json_images(images_str: Optional[str]) -> List[str]:
    """将JSON字符串解析为图片列表"""
    if not images_str:
        return []
    try:
        return json.loads(images_str)
    except (json.JSONDecodeError, TypeError):
        return []


# ── 景区信息 ─────────────────────────────────────────
@router.get("/info", response_model=ScenicInfoOut, summary="获取景区完整信息")
async def scenic_info(
    spot_id: Optional[int] = Query(None, description="景区ID，不传则返回第一个"),
    db: AsyncSession = Depends(get_db),
):
    """返回景区介绍、图片、开放时间、票种、最新公告"""
    q = select(ScenicSpot).where(ScenicSpot.is_active == True)
    if spot_id:
        q = q.where(ScenicSpot.id == spot_id)
    result = await db.execute(q)
    spot = result.scalars().first()

    if not spot:
        raise HTTPException(status_code=404, detail="景区不存在")

    # 获取票种
    tt_result = await db.execute(
        select(TicketType).where(
            TicketType.spot_id == spot.id,
            TicketType.is_active == True,
        ).order_by(TicketType.sort_order)
    )
    ticket_types = tt_result.scalars().all()

    # 获取最新公告（最多5条）
    ann_result = await db.execute(
        select(Announcement).where(
            Announcement.spot_id == spot.id,
            Announcement.is_published == True,
        ).order_by(Announcement.priority.desc(), Announcement.published_at.desc()).limit(5)
    )
    announcements = ann_result.scalars().all()

    return ScenicInfoOut(
        id=spot.id,
        name=spot.name,
        address=spot.address,
        city=spot.city,
        district=spot.district,
        phone=spot.phone,
        description=spot.description,
        cover_image=spot.cover_image,
        images=spot.images,
        lat=spot.lat,
        lng=spot.lng,
        open_time=spot.open_time,
        close_time=spot.close_time,
        daily_limit=spot.daily_limit,
        rating=spot.rating,
        is_active=spot.is_active,
        ticket_types=[
            {
                "id": tt.id,
                "name": tt.name,
                "category": tt.category,
                "price": tt.price,
                "original_price": tt.original_price,
                "daily_stock": tt.daily_stock,
                "description": tt.description,
                "min_age": tt.min_age,
                "max_age": tt.max_age,
            }
            for tt in ticket_types
        ],
        latest_announcements=[
            {
                "id": a.id,
                "title": a.title,
                "content": a.content,
                "category": a.category,
                "priority": a.priority,
                "published_at": a.published_at.isoformat() if a.published_at else None,
                "expires_at": a.expires_at.isoformat() if a.expires_at else None,
            }
            for a in announcements
        ],
    )


# ── 公告列表 ─────────────────────────────────────────
@router.get("/announcements", response_model=AnnouncementListResponse, summary="公告列表")
async def list_announcements(
    spot_id: Optional[int] = Query(None, description="景区ID"),
    category: Optional[str] = Query(None, description="公告分类"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """返回景区公告列表，支持分页和分类过滤"""
    base_q = select(Announcement).where(Announcement.is_published == True)
    count_q = select(func.count(Announcement.id)).where(Announcement.is_published == True)

    if spot_id:
        base_q = base_q.where(Announcement.spot_id == spot_id)
        count_q = count_q.where(Announcement.spot_id == spot_id)
    if category:
        base_q = base_q.where(Announcement.category == category)
        count_q = count_q.where(Announcement.category == category)

    total_result = await db.execute(count_q)
    total = total_result.scalar() or 0

    offset = (page - 1) * page_size
    items_result = await db.execute(
        base_q.order_by(Announcement.priority.desc(), Announcement.published_at.desc())
        .offset(offset).limit(page_size)
    )
    items = items_result.scalars().all()

    return AnnouncementListResponse(total=total, items=list(items))


@router.post("/announcements", response_model=AnnouncementOut, status_code=201, summary="创建公告（管理员）")
async def create_announcement(
    req: AnnouncementCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """管理员创建景区公告"""
    spot_result = await db.execute(select(ScenicSpot).where(ScenicSpot.id == req.spot_id))
    if not spot_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="景区不存在")

    announcement = Announcement(
        spot_id=req.spot_id,
        title=req.title,
        content=req.content,
        category=req.category,
        priority=req.priority,
        expires_at=req.expires_at,
    )
    db.add(announcement)
    await db.flush()
    await db.refresh(announcement)
    return announcement


@router.delete("/announcements/{announcement_id}", summary="删除公告（管理员）")
async def delete_announcement(
    announcement_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """管理员删除公告"""
    result = await db.execute(select(Announcement).where(Announcement.id == announcement_id))
    announcement = result.scalar_one_or_none()
    if not announcement:
        raise HTTPException(status_code=404, detail="公告不存在")
    await db.delete(announcement)
    await db.flush()
    return {"success": True, "message": "公告已删除"}


# ── 导览点位 (POI) ───────────────────────────────────
@router.get("/pois", response_model=List[PoiOut], summary="导览点位列表")
async def list_pois(
    spot_id: Optional[int] = Query(None, description="景区ID"),
    category: Optional[str] = Query(None, description="点位分类"),
    db: AsyncSession = Depends(get_db),
):
    """返回景区导览点位"""
    q = select(Poi).where(Poi.is_active == True)
    if spot_id:
        q = q.where(Poi.spot_id == spot_id)
    if category:
        q = q.where(Poi.category == category)
    q = q.order_by(Poi.sort_order, Poi.id)

    result = await db.execute(q)
    return result.scalars().all()


# ── 景区信息编辑 ─────────────────────────────────────
@router.put("/info", response_model=ScenicInfoOut, summary="编辑景区信息（管理员）")
async def update_scenic_info(
    req: ScenicInfoUpdate,
    spot_id: Optional[int] = Query(None, description="景区ID，不传则编辑第一个"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """管理员编辑景区信息"""
    q = select(ScenicSpot).where(ScenicSpot.is_active == True)
    if spot_id:
        q = q.where(ScenicSpot.id == spot_id)
    result = await db.execute(q)
    spot = result.scalars().first()

    if not spot:
        raise HTTPException(status_code=404, detail="景区不存在")

    # 只更新传入的非None字段
    update_data = req.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(spot, key, value)

    await db.flush()
    await db.refresh(spot)

    # 获取票种
    tt_result = await db.execute(
        select(TicketType).where(
            TicketType.spot_id == spot.id,
            TicketType.is_active == True,
        ).order_by(TicketType.sort_order)
    )
    ticket_types = tt_result.scalars().all()

    # 获取最新公告
    ann_result = await db.execute(
        select(Announcement).where(
            Announcement.spot_id == spot.id,
            Announcement.is_published == True,
        ).order_by(Announcement.priority.desc(), Announcement.published_at.desc()).limit(5)
    )
    announcements = ann_result.scalars().all()

    return ScenicInfoOut(
        id=spot.id,
        name=spot.name,
        address=spot.address,
        city=spot.city,
        district=spot.district,
        phone=spot.phone,
        description=spot.description,
        cover_image=spot.cover_image,
        images=spot.images,
        lat=spot.lat,
        lng=spot.lng,
        open_time=spot.open_time,
        close_time=spot.close_time,
        daily_limit=spot.daily_limit,
        rating=spot.rating,
        is_active=spot.is_active,
        ticket_types=[
            {
                "id": tt.id,
                "name": tt.name,
                "category": tt.category,
                "price": tt.price,
                "original_price": tt.original_price,
                "daily_stock": tt.daily_stock,
                "description": tt.description,
                "min_age": tt.min_age,
                "max_age": tt.max_age,
            }
            for tt in ticket_types
        ],
        latest_announcements=[
            {
                "id": a.id,
                "title": a.title,
                "content": a.content,
                "category": a.category,
                "priority": a.priority,
                "published_at": a.published_at.isoformat() if a.published_at else None,
                "expires_at": a.expires_at.isoformat() if a.expires_at else None,
            }
            for a in announcements
        ],
    )


# ── 公告编辑 ─────────────────────────────────────────
@router.put("/announcements/{announcement_id}", response_model=AnnouncementOut, summary="编辑公告（管理员）")
async def update_announcement(
    announcement_id: int,
    req: AnnouncementUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """管理员编辑景区公告"""
    result = await db.execute(select(Announcement).where(Announcement.id == announcement_id))
    announcement = result.scalar_one_or_none()
    if not announcement:
        raise HTTPException(status_code=404, detail="公告不存在")

    update_data = req.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(announcement, key, value)

    await db.flush()
    await db.refresh(announcement)
    return announcement


# ── 景区天气 ─────────────────────────────────────────
@router.get("/weather", response_model=WeatherResponse, summary="景区天气")
async def scenic_weather(
    spot_id: Optional[int] = Query(None, description="景区ID，不传则返回第一个景区天气"),
    db: AsyncSession = Depends(get_db),
):
    """返回景区天气信息（mock数据，可对接公开天气API）"""
    q = select(ScenicSpot).where(ScenicSpot.is_active == True)
    if spot_id:
        q = q.where(ScenicSpot.id == spot_id)
    result = await db.execute(q)
    spot = result.scalars().first()

    if not spot:
        raise HTTPException(status_code=404, detail="景区不存在")

    # Mock weather data — 实际部署可对接和风天气/OpenWeather等公开API
    import random
    random.seed(spot.id)
    temps = [18.5, 22.0, 25.5, 28.0, 30.5, 32.0, 26.0, 20.0]
    weathers = ["晴", "多云", "阴", "小雨", "晴转多云", "多云转晴", "阴转多云", "晴"]
    winds = ["微风", "东南风2级", "南风3级", "东北风2级", "西南风3级", "北风1级", "东风2级", "南风2级"]

    return WeatherResponse(
        spot_id=spot.id,
        city=spot.city,
        temperature=temps[spot.id % len(temps)],
        weather=weathers[spot.id % len(weathers)],
        humidity=random.randint(40, 85),
        wind=winds[spot.id % len(winds)],
        aqi=random.randint(30, 120),
        update_time=datetime.utcnow().strftime("%Y-%m-%d %H:%M"),
        forecast=[
            {"date": (date.today() + timedelta(days=d)).isoformat(),
             "weather": weathers[(spot.id + d) % len(weathers)],
             "temp_high": temps[(spot.id + d) % len(temps)] + 5,
             "temp_low": temps[(spot.id + d) % len(temps)] - 5}
            for d in range(3)
        ],
    )
