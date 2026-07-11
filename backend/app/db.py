"""
景区智慧管理系统 - 数据库模型
User / ScenicSpot / TicketType / TicketOrder / Hotel / Room / HotelOrder
"""
from datetime import datetime, date
from typing import Optional, List

from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, Date, Text,
    ForeignKey, Enum as SAEnum, Index, create_engine
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.config import settings


# ── Base ─────────────────────────────────────────────
class Base(DeclarativeBase):
    pass


# ── Enums / Status Constants ─────────────────────────
class UserRole:
    ADMIN = "admin"
    GUEST = "guest"
    STAFF = "staff"       # 景区工作人员（核销员）
    FRONT_DESK = "front_desk"


class TicketOrderStatus:
    PENDING = "pending"        # 待支付
    PAID = "paid"              # 已支付（待使用）
    VERIFIED = "verified"      # 已核销（已使用）
    CANCELLED = "cancelled"    # 已取消
    REFUNDING = "refunding"    # 退款审核中（待管理员确认）
    REFUNDED = "refunded"      # 已退款
    EXPIRED = "expired"        # 已过期


class HotelOrderStatus:
    PENDING = "pending"
    PAID = "paid"
    CHECKED_IN = "checked_in"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    REFUNDING = "refunding"    # 退款审核中
    REFUNDED = "refunded"


class VerifyResult:
    """核销结果"""
    SUCCESS = "success"
    ALREADY_VERIFIED = "already_verified"
    INVALID_TOKEN = "invalid_token"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


# ── 用户模型（复用伊家人字段） ──────────────────────
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(20), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(256), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default=UserRole.GUEST)
    nickname: Mapped[Optional[str]] = mapped_column(String(100))
    avatar_url: Mapped[Optional[str]] = mapped_column(Text)
    wx_openid: Mapped[Optional[str]] = mapped_column(String(128), unique=True, index=True)
    wx_unionid: Mapped[Optional[str]] = mapped_column(String(128), unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    ticket_orders: Mapped[List["TicketOrder"]] = relationship(
        back_populates="user", foreign_keys="TicketOrder.user_id"
    )
    hotel_orders: Mapped[List["HotelOrder"]] = relationship(back_populates="user")


# ── 景区信息 ────────────────────────────────────────
class ScenicSpot(Base):
    __tablename__ = "scenic_spots"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, comment="景区名称")
    address: Mapped[str] = mapped_column(String(500), nullable=False)
    city: Mapped[str] = mapped_column(String(50), index=True)
    district: Mapped[Optional[str]] = mapped_column(String(50))
    phone: Mapped[Optional[str]] = mapped_column(String(20))
    description: Mapped[Optional[str]] = mapped_column(Text, comment="景区简介")
    cover_image: Mapped[Optional[str]] = mapped_column(Text, comment="封面图")
    images: Mapped[Optional[str]] = mapped_column(Text, comment="图片列表 JSON")
    lat: Mapped[Optional[float]] = mapped_column(Float)
    lng: Mapped[Optional[float]] = mapped_column(Float)
    open_time: Mapped[str] = mapped_column(String(10), default="08:00", comment="开园时间 HH:MM")
    close_time: Mapped[str] = mapped_column(String(10), default="17:00", comment="闭园时间 HH:MM")
    daily_limit: Mapped[int] = mapped_column(Integer, default=5000, comment="每日最大接待量")
    rating: Mapped[float] = mapped_column(Float, default=4.5)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # 关系
    ticket_types: Mapped[List["TicketType"]] = relationship(back_populates="spot")
    hotels: Mapped[List["Hotel"]] = relationship(back_populates="spot")


# ── 票种模型 ────────────────────────────────────────
class TicketType(Base):
    __tablename__ = "ticket_types"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    spot_id: Mapped[int] = mapped_column(ForeignKey("scenic_spots.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="票种名称: 成人票/儿童票/老人票/团体票/套票")
    category: Mapped[str] = mapped_column(String(50), default="standard", comment="standard/child/senior/group/combo")
    price: Mapped[float] = mapped_column(Float, nullable=False, comment="单价(元)")
    original_price: Mapped[Optional[float]] = mapped_column(Float, comment="原价(划线价)")
    daily_stock: Mapped[int] = mapped_column(Integer, default=1000, comment="每日库存")
    description: Mapped[Optional[str]] = mapped_column(Text)
    min_age: Mapped[Optional[int]] = mapped_column(Integer, comment="年龄下限")
    max_age: Mapped[Optional[int]] = mapped_column(Integer, comment="年龄上限")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, comment="排序")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    spot: Mapped["ScenicSpot"] = relationship(back_populates="ticket_types")
    orders: Mapped[List["TicketOrder"]] = relationship(back_populates="ticket_type")


# ── 购票订单模型 ──────────────────────────────────────
class TicketOrder(Base):
    __tablename__ = "ticket_orders"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    order_no: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False, comment="订单号")
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    ticket_type_id: Mapped[int] = mapped_column(ForeignKey("ticket_types.id", ondelete="CASCADE"), index=True)
    spot_id: Mapped[int] = mapped_column(ForeignKey("scenic_spots.id", ondelete="CASCADE"), index=True)
    quantity: Mapped[int] = mapped_column(Integer, default=1, comment="购买数量")
    visit_date: Mapped[date] = mapped_column(Date, nullable=False, comment="游览日期", index=True)
    time_slot: Mapped[str] = mapped_column(String(20), nullable=False, comment="分时段: 08:00-10:00 / 10:00-12:00 / 12:00-14:00 / 14:00-17:00")
    total_price: Mapped[float] = mapped_column(Float, nullable=False, comment="总价")
    status: Mapped[str] = mapped_column(String(20), default=TicketOrderStatus.PENDING, index=True)
    # 二维码核销
    qr_token: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False, comment="二维码核销token")
    # 游客信息
    visitor_name: Mapped[Optional[str]] = mapped_column(String(50), comment="游客姓名")
    visitor_phone: Mapped[Optional[str]] = mapped_column(String(20), comment="游客电话")
    visitor_id_card: Mapped[Optional[str]] = mapped_column(String(18), comment="身份证号")
    # 核销信息
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime, comment="核销时间")
    verified_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), comment="核销员ID")
    # 时间
    paid_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    remark: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_ticket_orders_user_id_status", "user_id", "status"),
    )

    # 关系
    user: Mapped["User"] = relationship(back_populates="ticket_orders", foreign_keys=[user_id])
    ticket_type: Mapped["TicketType"] = relationship(back_populates="orders")
    spot: Mapped["ScenicSpot"] = relationship()
    verifier: Mapped[Optional["User"]] = relationship(foreign_keys=[verified_by], viewonly=True)


# ── 酒店门店模型 ────────────────────────────────────
class Hotel(Base):
    __tablename__ = "hotels"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    spot_id: Mapped[int] = mapped_column(ForeignKey("scenic_spots.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, comment="酒店名称")
    address: Mapped[str] = mapped_column(String(500), nullable=False)
    city: Mapped[str] = mapped_column(String(50), index=True)
    district: Mapped[Optional[str]] = mapped_column(String(50))
    phone: Mapped[Optional[str]] = mapped_column(String(20))
    description: Mapped[Optional[str]] = mapped_column(Text, comment="酒店简介")
    cover_image: Mapped[Optional[str]] = mapped_column(Text, comment="封面图")
    images: Mapped[Optional[str]] = mapped_column(Text, comment="图片列表 JSON")
    lat: Mapped[Optional[float]] = mapped_column(Float)
    lng: Mapped[Optional[float]] = mapped_column(Float)
    rating: Mapped[float] = mapped_column(Float, default=4.5)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # 关系
    spot: Mapped["ScenicSpot"] = relationship(back_populates="hotels")
    rooms: Mapped[List["Room"]] = relationship(back_populates="hotel")
    orders: Mapped[List["HotelOrder"]] = relationship(back_populates="hotel")


# ── 房型/房间模型 ────────────────────────────────────
class Room(Base):
    __tablename__ = "rooms"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    hotel_id: Mapped[int] = mapped_column(ForeignKey("hotels.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="房型名称")
    room_type: Mapped[str] = mapped_column(String(50), comment="大床房/双床房/套房等")
    price: Mapped[float] = mapped_column(Float, nullable=False, comment="单价(元/晚)")
    total_count: Mapped[int] = mapped_column(Integer, default=10, comment="总房间数")
    available_count: Mapped[int] = mapped_column(Integer, default=10, comment="可用房间数")
    area: Mapped[Optional[float]] = mapped_column(Float, comment="面积(m²)")
    bed_type: Mapped[Optional[str]] = mapped_column(String(50), comment="床型")
    max_guests: Mapped[int] = mapped_column(Integer, default=2, comment="最大入住人数")
    has_window: Mapped[bool] = mapped_column(Boolean, default=True, comment="有无窗户")
    has_wifi: Mapped[bool] = mapped_column(Boolean, default=True)
    has_bathtub: Mapped[bool] = mapped_column(Boolean, default=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    images: Mapped[Optional[str]] = mapped_column(Text, comment="图片列表 JSON")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # 关系
    hotel: Mapped["Hotel"] = relationship(back_populates="rooms")
    orders: Mapped[List["HotelOrder"]] = relationship(back_populates="room")


# ── 客房订单模型 ────────────────────────────────────
class HotelOrder(Base):
    __tablename__ = "hotel_orders"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    order_no: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False, comment="订单号")
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    hotel_id: Mapped[int] = mapped_column(ForeignKey("hotels.id", ondelete="CASCADE"), index=True)
    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.id", ondelete="CASCADE"), index=True)
    room_count: Mapped[int] = mapped_column(Integer, default=1, comment="预订间数")
    checkin_date: Mapped[date] = mapped_column(Date, nullable=False, comment="入住日期", index=True)
    checkout_date: Mapped[date] = mapped_column(Date, nullable=False, comment="离店日期", index=True)
    nights: Mapped[int] = mapped_column(Integer, nullable=False, comment="入住天数")
    total_price: Mapped[float] = mapped_column(Float, nullable=False, comment="总价")
    status: Mapped[str] = mapped_column(String(20), default=HotelOrderStatus.PENDING, index=True)
    guest_name: Mapped[str] = mapped_column(String(50), nullable=False, comment="入住人姓名")
    guest_phone: Mapped[str] = mapped_column(String(20), nullable=False, comment="入住人电话")
    remark: Mapped[Optional[str]] = mapped_column(Text, comment="备注")
    cancel_reason: Mapped[Optional[str]] = mapped_column(String(500), comment="取消原因")
    paid_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_hotel_orders_user_id_status", "user_id", "status"),
    )

    # 关系
    user: Mapped["User"] = relationship(back_populates="hotel_orders")
    hotel: Mapped["Hotel"] = relationship(back_populates="orders")
    room: Mapped["Room"] = relationship(back_populates="orders")


# ── 景区公告模型 ────────────────────────────────────
class Announcement(Base):
    __tablename__ = "announcements"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    spot_id: Mapped[int] = mapped_column(ForeignKey("scenic_spots.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False, comment="公告标题")
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="公告内容")
    category: Mapped[str] = mapped_column(String(20), default="notice", comment="notice/event/maintenance/emergency")
    priority: Mapped[int] = mapped_column(Integer, default=0, comment="优先级 0-低 1-中 2-高")
    is_published: Mapped[bool] = mapped_column(Boolean, default=True)
    published_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, comment="过期时间")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ── 导览点位 (POI) 模型 ─────────────────────────────
class Poi(Base):
    __tablename__ = "pois"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    spot_id: Mapped[int] = mapped_column(ForeignKey("scenic_spots.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, comment="点位名称")
    category: Mapped[str] = mapped_column(String(50), default="viewpoint", comment="viewpoint/toilet/restaurant/shop/parking/entrance/service")
    description: Mapped[Optional[str]] = mapped_column(Text, comment="点位描述")
    lat: Mapped[float] = mapped_column(Float, nullable=False, comment="纬度")
    lng: Mapped[float] = mapped_column(Float, nullable=False, comment="经度")
    images: Mapped[Optional[str]] = mapped_column(Text, comment="图片JSON")
    audio_url: Mapped[Optional[str]] = mapped_column(Text, comment="语音讲解URL")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ── 停车费率模型 ────────────────────────────────────
class ParkingRate(Base):
    __tablename__ = "parking_rates"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    spot_id: Mapped[int] = mapped_column(ForeignKey("scenic_spots.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="停车场名称")
    vehicle_type: Mapped[str] = mapped_column(String(20), default="car", comment="car/bus/truck/motorcycle")
    first_hour_price: Mapped[float] = mapped_column(Float, default=5.0, comment="首小时价格(元)")
    additional_hour_price: Mapped[float] = mapped_column(Float, default=3.0, comment="每小时加收(元)")
    daily_cap: Mapped[float] = mapped_column(Float, default=30.0, comment="每日封顶(元)")
    free_minutes: Mapped[int] = mapped_column(Integer, default=15, comment="免费分钟数")
    total_spots: Mapped[int] = mapped_column(Integer, default=200, comment="总车位数")
    available_spots: Mapped[int] = mapped_column(Integer, default=200, comment="可用车位数")
    open_time: Mapped[str] = mapped_column(String(5), default="00:00")
    close_time: Mapped[str] = mapped_column(String(5), default="24:00")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ── 停车记录模型 ────────────────────────────────────
class ParkingRecord(Base):
    __tablename__ = "parking_records"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    rate_id: Mapped[int] = mapped_column(ForeignKey("parking_rates.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    plate_number: Mapped[str] = mapped_column(String(20), nullable=False, index=True, comment="车牌号")
    vehicle_type: Mapped[str] = mapped_column(String(20), default="car")
    checkin_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, comment="入场时间", index=True)
    checkout_time: Mapped[Optional[datetime]] = mapped_column(DateTime, comment="出场时间")
    duration_minutes: Mapped[Optional[int]] = mapped_column(Integer, comment="停车时长(分钟)")
    total_fee: Mapped[Optional[float]] = mapped_column(Float, comment="停车费(元)")
    status: Mapped[str] = mapped_column(String(20), default="parking", comment="parking/completed/cancelled", index=True)
    pay_status: Mapped[str] = mapped_column(String(20), default="unpaid", comment="unpaid/paid")
    pay_method: Mapped[Optional[str]] = mapped_column(String(20), comment="wechat/alipay/cash")
    paid_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ── 景区附近推荐点位模型 ──────────────────────────────
class NearbyPoint(Base):
    """景区周边餐饮/购物/娱乐推荐"""
    __tablename__ = "nearby_points"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    spot_id: Mapped[int] = mapped_column(ForeignKey("scenic_spots.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, comment="商户名称")
    category: Mapped[str] = mapped_column(String(30), default="dining", comment="dining/shopping/entertainment")
    description: Mapped[Optional[str]] = mapped_column(Text, comment="推荐理由/描述")
    address: Mapped[Optional[str]] = mapped_column(String(500))
    phone: Mapped[Optional[str]] = mapped_column(String(20))
    lat: Mapped[Optional[float]] = mapped_column(Float, comment="纬度")
    lng: Mapped[Optional[float]] = mapped_column(Float, comment="经度")
    rating: Mapped[float] = mapped_column(Float, default=4.0, comment="推荐评分 1-5")
    images: Mapped[Optional[str]] = mapped_column(Text, comment="图片JSON数组")
    distance: Mapped[Optional[float]] = mapped_column(Float, comment="距离景区(米)")
    price_range: Mapped[Optional[str]] = mapped_column(String(20), comment="人均消费区间")
    open_time: Mapped[Optional[str]] = mapped_column(String(20), comment="营业时间")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_nearby_points_spot_id_category", "spot_id", "category"),
    )


# ── 游客评价模型 ────────────────────────────────────
class Review(Base):
    """游客对景区的评价（评分+评论+图片）"""
    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    spot_id: Mapped[int] = mapped_column(ForeignKey("scenic_spots.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    rating: Mapped[int] = mapped_column(Integer, nullable=False, comment="评分 1-5")
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="评价内容")
    images: Mapped[Optional[str]] = mapped_column(Text, comment="评价图片JSON数组")
    is_approved: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否审核通过")
    like_count: Mapped[int] = mapped_column(Integer, default=0, comment="点赞数")
    visit_date: Mapped[Optional[date]] = mapped_column(Date, comment="游览日期")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_reviews_spot_id_rating", "spot_id", "rating"),
    )


# ── 支付记录模型 ────────────────────────────────────
class PaymentRecord(Base):
    __tablename__ = "payment_records"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    order_no: Mapped[str] = mapped_column(String(32), index=True, nullable=False, comment="关联订单号（票务/酒店）")
    order_type: Mapped[str] = mapped_column(String(20), nullable=False, comment="ticket / hotel")
    transaction_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False, comment="微信支付交易号")
    amount: Mapped[float] = mapped_column(Float, nullable=False, comment="支付金额(元)")
    status: Mapped[str] = mapped_column(String(20), default="pending", comment="pending / success / failed / refund", index=True)
    pay_method: Mapped[str] = mapped_column(String(20), default="wechat_jsapi")
    prepay_id: Mapped[Optional[str]] = mapped_column(String(64), comment="微信预支付ID")
    pay_time: Mapped[Optional[datetime]] = mapped_column(DateTime)
    refund_time: Mapped[Optional[datetime]] = mapped_column(DateTime)
    raw_data: Mapped[Optional[str]] = mapped_column(Text, comment="回调原始数据 JSON")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ── 票务库存模型（原子扣减） ─────────────────────────
class TicketInventory(Base):
    """票务库存表：按票种+日期+时段粒度管理可售库存，支持原子扣减"""
    __tablename__ = "ticket_inventory"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ticket_type_id: Mapped[int] = mapped_column(
        ForeignKey("ticket_types.id", ondelete="CASCADE"), index=True, nullable=False
    )
    visit_date: Mapped[date] = mapped_column(Date, nullable=False, index=True, comment="游览日期")
    time_slot: Mapped[str] = mapped_column(String(20), nullable=False, comment="时段")
    total_stock: Mapped[int] = mapped_column(Integer, nullable=False, comment="该时段总库存")
    sold_count: Mapped[int] = mapped_column(Integer, default=0, comment="已售数量")
    version: Mapped[int] = mapped_column(Integer, default=0, comment="乐观锁版本号")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    __table_args__ = (
        Index("ix_ticket_inventory_type_date_slot", "ticket_type_id", "visit_date", "time_slot", unique=True),
    )


# ── 套餐组合模型 ────────────────────────────────────
class ComboPackage(Base):
    """套餐组合: 门票+酒店+停车组合"""
    __tablename__ = "combo_packages"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    spot_id: Mapped[int] = mapped_column(ForeignKey("scenic_spots.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, comment="套餐名称")
    description: Mapped[Optional[str]] = mapped_column(Text, comment="套餐说明")
    cover_image: Mapped[Optional[str]] = mapped_column(Text, comment="封面图")
    original_price: Mapped[float] = mapped_column(Float, nullable=False, comment="原价总和")
    price: Mapped[float] = mapped_column(Float, nullable=False, comment="套餐售价")
    items_json: Mapped[Optional[str]] = mapped_column(Text, comment="套餐内容JSON: [{type,id,name,qty,price}]")
    tags: Mapped[Optional[str]] = mapped_column(String(200), comment="标签: 热门/推荐/限时")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    spot: Mapped["ScenicSpot"] = relationship()


# ── 天气缓存模型 ────────────────────────────────────
class WeatherCache(Base):
    """景区天气缓存表"""
    __tablename__ = "weather_cache"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    spot_id: Mapped[int] = mapped_column(ForeignKey("scenic_spots.id", ondelete="CASCADE"), unique=True, index=True)
    city: Mapped[str] = mapped_column(String(50))
    temperature: Mapped[float] = mapped_column(Float, comment="当前温度(℃)")
    weather: Mapped[str] = mapped_column(String(50), comment="天气状况:晴/多云/阴/小雨等")
    humidity: Mapped[int] = mapped_column(Integer, comment="湿度(%)")
    wind: Mapped[str] = mapped_column(String(50), comment="风力描述")
    aqi: Mapped[int] = mapped_column(Integer, comment="空气质量指数")
    forecast_json: Mapped[Optional[str]] = mapped_column(Text, comment="3天预报 JSON")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ── 引擎 & 会话工厂 ──────────────────────────────────
_async_engine = None
_async_session_factory = None


def get_async_engine():
    global _async_engine
    if _async_engine is None:
        _async_engine = create_async_engine(
            settings.db_url,
            echo=settings.DEBUG,
            connect_args={"check_same_thread": False} if settings.DEV_MODE else {},
        )
    return _async_engine


def get_async_session_factory() -> async_sessionmaker[AsyncSession]:
    global _async_session_factory
    if _async_session_factory is None:
        _async_session_factory = async_sessionmaker(
            get_async_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _async_session_factory


async def get_db() -> AsyncSession:
    """FastAPI 依赖注入：获取数据库会话"""
    factory = get_async_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db():
    """创建所有表（启动时调用）"""
    engine = get_async_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
