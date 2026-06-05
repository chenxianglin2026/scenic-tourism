"""
景区智慧管理系统 - 数据库模型
User / ScenicSpot / TicketType / TicketOrder / Hotel / Room / HotelOrder
"""
from datetime import datetime, date
from typing import Optional, List

from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, Date, Text,
    ForeignKey, Enum as SAEnum, create_engine
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
    REFUNDED = "refunded"      # 已退款
    EXPIRED = "expired"        # 已过期


class HotelOrderStatus:
    PENDING = "pending"
    PAID = "paid"
    CHECKED_IN = "checked_in"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
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
    visit_date: Mapped[date] = mapped_column(Date, nullable=False, comment="游览日期")
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
    checkin_date: Mapped[date] = mapped_column(Date, nullable=False, comment="入住日期")
    checkout_date: Mapped[date] = mapped_column(Date, nullable=False, comment="离店日期")
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

    # 关系
    user: Mapped["User"] = relationship(back_populates="hotel_orders")
    hotel: Mapped["Hotel"] = relationship(back_populates="orders")
    room: Mapped["Room"] = relationship(back_populates="orders")


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
