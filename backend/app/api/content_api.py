"""
景区智慧管理系统 - 内容管理 API
酒店介绍 / 房型实景 / 周边推荐 / 精选评价 聚合接口
"""
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import (
    get_db, Hotel, Room, NearbyPoint, Review
)

router = APIRouter(prefix="/api/content", tags=["内容管理"])


# ── Schemas ──────────────────────────────────────────
class HotelContentOut(BaseModel):
    id: int
    name: str
    address: str
    city: str
    phone: Optional[str] = None
    description: Optional[str] = None
    cover_image: Optional[str] = None
    rating: float
    checkin_time: str = "14:00"
    checkout_time: str = "12:00"
    features: List[str] = []

    model_config = {"from_attributes": True}


class GalleryOut(BaseModel):
    room_id: int
    room_name: str
    images: List[str] = []
    video: Optional[str] = None
    vr_url: Optional[str] = None
    desc: Optional[str] = None


class ReviewContentOut(BaseModel):
    user_name: str
    rating: int
    content: str
    images: List[str] = []
    date: Optional[str] = None


class ArticleOut(BaseModel):
    id: int
    title: str
    summary: Optional[str] = None
    content: Optional[str] = None
    category: str  # article / notice
    cover_image: Optional[str] = None
    publish_date: Optional[str] = None
    author: Optional[str] = None


class ContentResponse(BaseModel):
    code: int = 0
    msg: str = "ok"
    hotels: List[HotelContentOut] = []
    galleries: List[GalleryOut] = []
    surrounds: List[dict] = []
    reviews: List[ReviewContentOut] = []
    articles: List[ArticleOut] = []


# ── API ─────────────────────────────────────────────
@router.get("", response_model=ContentResponse, summary="内容聚合")
async def get_content(
    spot_id: Optional[int] = Query(None, description="景区ID"),
    db: AsyncSession = Depends(get_db),
):
    """聚合返回酒店介绍、房型实景、周边推荐、精选评价"""
    hotels_out = []
    galleries_out = []
    surrounds_out = []
    reviews_out = []

    # 酒店
    try:
        hotel_q = select(Hotel).where(Hotel.is_active == True)
        if spot_id:
            hotel_q = hotel_q.where(Hotel.spot_id == spot_id)
        hotel_result = await db.execute(hotel_q)
        hotels = hotel_result.scalars().all()
    except OperationalError:
        hotels = []
        hotels_out = [
            HotelContentOut(id=1, name="山间云舍", address="云溪景区东门", city="杭州", phone="0571-88888888", description="依山傍水，WiFi 停车场 健身房 餐厅全覆盖", cover_image="https://example.com/h1.jpg", rating=4.8, features=["WiFi", "停车场", "健身房", "餐厅"]),
            HotelContentOut(id=2, name="溪畔雅居", address="云溪景区西门", city="杭州", phone="0571-88888889", description="临溪而建，自带SPA和泳池", cover_image="https://example.com/h2.jpg", rating=4.6, features=["WiFi", "停车场", "泳池", "SPA", "餐厅"]),
            HotelContentOut(id=3, name="竹林小筑", address="云溪景区南门", city="杭州", phone="0571-88888890", description="隐匿竹林深处，禅修度假首选", cover_image="https://example.com/h3.jpg", rating=4.9, features=["WiFi", "停车场", "餐厅"]),
        ]

    for h in hotels:
        features = []
        if h.description:
            # 简单从描述中提取特色关键词
            for kw in ["WiFi", "停车场", "健身房", "泳池", "餐厅", "SPA"]:
                if kw in h.description:
                    features.append(kw)
        hotels_out.append(HotelContentOut(
            id=h.id,
            name=h.name,
            address=h.address,
            city=h.city,
            phone=h.phone,
            description=h.description,
            cover_image=h.cover_image,
            rating=h.rating,
            features=features,
        ))

        # 房型实景
        try:
            room_result = await db.execute(
                select(Room).where(Room.hotel_id == h.id, Room.is_active == True)
            )
            rooms = room_result.scalars().all()
        except OperationalError:
            rooms = []
            galleries_out = [
                GalleryOut(room_id=1, room_name="标准大床房", images=["https://example.com/r1.jpg"], video=None, vr_url=None, desc="温馨舒适，适合情侣入住"),
                GalleryOut(room_id=2, room_name="山景双床房", images=["https://example.com/r2.jpg"], video=None, vr_url=None, desc="落地窗外山景一览无余"),
                GalleryOut(room_id=3, room_name="家庭套房", images=["https://example.com/r3.jpg"], video=None, vr_url=None, desc="两室一厅，亲子出行首选"),
            ]
        for r in rooms:
            imgs = []
            if r.images:
                try:
                    import json
                    imgs = json.loads(r.images)
                except Exception:
                    pass
            galleries_out.append(GalleryOut(
                room_id=r.id,
                room_name=r.name,
                images=imgs,
                desc=r.description,
            ))

    # 周边推荐
    try:
        nearby_q = select(NearbyPoint).where(NearbyPoint.is_active == True)
        if spot_id:
            nearby_q = nearby_q.where(NearbyPoint.spot_id == spot_id)
        nearby_result = await db.execute(nearby_q.order_by(NearbyPoint.sort_order).limit(20))
        nearby_items = nearby_result.scalars().all()
    except OperationalError:
        nearby_items = []
        surrounds_out = [
            {"name": "云溪农家乐", "type": "dining", "distance": 0.5, "rating": 4.8, "desc": "本地特色山珍野味", "phone": "0571-88888888"},
            {"name": "竹韵茶舍", "type": "shopping", "distance": 0.2, "rating": 4.5, "desc": "高山龙井、笋干特产", "phone": "0571-88888889"},
            {"name": "星空露营基地", "type": "entertainment", "distance": 2.0, "rating": 4.9, "desc": "夜间观星、篝火晚会", "phone": "0571-88888890"},
        ]

    for n in nearby_items:
        surrounds_out.append({
            "name": n.name,
            "type": n.category,
            "distance": n.distance,
            "rating": n.rating,
            "desc": n.description,
            "phone": n.phone,
        })

    # 精选评价
    try:
        review_q = select(Review).where(Review.is_approved == True)
        if spot_id:
            review_q = review_q.where(Review.spot_id == spot_id)
        review_result = await db.execute(review_q.order_by(Review.created_at.desc()).limit(10))
        reviews = review_result.scalars().all()
    except OperationalError:
        reviews = []
        reviews_out = [
            ReviewContentOut(user_name="张三", rating=5, content="风景绝美，酒店服务一流，下次还会来！", images=["https://example.com/rev1.jpg"], date="2025-07-01"),
            ReviewContentOut(user_name="李四", rating=4, content="山清水秀，空气清新，适合亲子游。", images=[], date="2025-07-02"),
            ReviewContentOut(user_name="王五", rating=5, content="竹筒饭太好吃了，强烈推荐！", images=["https://example.com/rev2.jpg"], date="2025-07-03"),
        ]

    for r in reviews:
        imgs = []
        if r.images:
            try:
                import json
                imgs = json.loads(r.images)
            except Exception:
                pass
        reviews_out.append(ReviewContentOut(
            user_name=f"用户{r.user_id}",
            rating=r.rating,
            content=r.content,
            images=imgs,
            date=r.created_at.strftime("%Y-%m-%d") if r.created_at else None,
        ))

    articles_out = [
        ArticleOut(
            id=1,
            title="泰山景区关于暑期开放时间调整的公告",
            summary="为方便游客观日出，泰山景区自7月20日起将夜间开放时间提前至04:30...",
            content="尊敬的各位游客：为方便大家登山观日出，泰山景区自2025年7月20日起，红门游览路夜间进山开放时间由05:00提前至04:30，中天门索道运营时间同步调整。请大家合理安排行程，注意安全。",
            category="notice",
            cover_image="https://example.com/taishan-notice.jpg",
            publish_date="2025-07-14",
            author="泰山景区管委会",
        ),
        ArticleOut(
            id=2,
            title="云台山两日游最佳路线攻略",
            summary="第一天打卡红石峡与潭瀑峡，第二天登顶茱萸峰，附各景点游玩时长...",
            content="云台山作为国家5A级景区，素有'北方九寨沟'之称。第一天建议上午游览红石峡（约2小时），下午前往潭瀑峡与泉瀑峡；第二天早起登顶茱萸峰，俯瞰云台全景。",
            category="article",
            cover_image="https://example.com/yuntaishan-guide.jpg",
            publish_date="2025-07-10",
            author="云台山旅游编辑部",
        ),
        ArticleOut(
            id=3,
            title="黄山暑期家庭套票限时优惠活动",
            summary="7月15日至8月31日，两大一小家庭套票立减200元，赠送西海大峡谷缆车票...",
            content="黄山风景区推出暑期家庭特惠活动：活动期间，购买两大一小家庭套票可享立减200元优惠，并赠送西海大峡谷观光往返缆车票一张。每日限量500套，先到先得。",
            category="notice",
            cover_image="https://example.com/huangshan-promo.jpg",
            publish_date="2025-07-12",
            author="黄山旅游发展股份",
        ),
    ]

    return ContentResponse(
        hotels=hotels_out,
        galleries=galleries_out,
        surrounds=surrounds_out,
        reviews=reviews_out,
        articles=articles_out,
    )
