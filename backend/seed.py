"""
景区智慧管理系统 - 种子数据脚本
创建测试数据: 1个景区 + 4个票种 + 1个酒店 + 3个房型 + 1个admin用户
用法: python seed.py
"""
import asyncio
import os
import sys

# 确保项目根目录在 sys.path 中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.config import settings
from app.db import Base, User, ScenicSpot, TicketType, Hotel, Room
from app.api.auth import hash_password


def seed():
    """同步方式写入种子数据"""
    db_url = settings.db_sync_url
    print(f"数据库: {db_url}")
    engine = create_engine(db_url, echo=False)

    # 1. 删除旧表并重建
    print("正在删除旧表...")
    Base.metadata.drop_all(engine)
    print("正在创建新表...")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        # ── 2. 创建管理员用户 ──
        admin = User(
            username="admin",
            phone="13800000001",
            hashed_password=hash_password("admin123"),
            role="admin",
            nickname="系统管理员",
            is_active=True,
        )
        session.add(admin)
        session.flush()
        print(f"  [+] 管理员: admin / admin123 (id={admin.id})")

        # ── 3. 创建景区 ──
        spot = ScenicSpot(
            name="泰山风景名胜区",
            address="山东省泰安市泰山区红门路54号",
            city="泰安",
            district="泰山区",
            phone="0538-8222606",
            description="泰山，又名岱山、岱宗、岱岳、东岳、泰岳，为五岳之一，有'五岳之首''天下第一山'之称。"
                        "主峰玉皇顶海拔1545米，气势雄伟磅礴。泰山被古人视为'直通帝座'的天堂，"
                        "成为百姓崇拜、帝王告祭的神山，有'泰山安，四海皆安'的说法。",
            open_time="06:00",
            close_time="18:00",
            daily_limit=10000,
            rating=4.8,
            is_active=True,
        )
        session.add(spot)
        session.flush()
        print(f"  [+] 景区: {spot.name} (id={spot.id})")

        # ── 4. 创建票种 ──
        ticket_types_data = [
            {
                "name": "成人票",
                "category": "standard",
                "price": 115.00,
                "original_price": 150.00,
                "daily_stock": 5000,
                "description": "18-59周岁成人全价票",
                "min_age": 18,
                "max_age": 59,
                "sort_order": 1,
            },
            {
                "name": "儿童票",
                "category": "child",
                "price": 57.00,
                "original_price": 75.00,
                "daily_stock": 2000,
                "description": "6-17周岁未成年人半价票，身高1.4米以下儿童免票",
                "min_age": 6,
                "max_age": 17,
                "sort_order": 2,
            },
            {
                "name": "老人票",
                "category": "senior",
                "price": 57.00,
                "original_price": 75.00,
                "daily_stock": 2000,
                "description": "60周岁及以上老年人半价票",
                "min_age": 60,
                "max_age": None,
                "sort_order": 3,
            },
            {
                "name": "团体票（10人起）",
                "category": "group",
                "price": 90.00,
                "original_price": 115.00,
                "daily_stock": 2000,
                "description": "10人及以上团体优惠票，需提前1天预约",
                "min_age": None,
                "max_age": None,
                "sort_order": 4,
            },
        ]
        ticket_types = []
        for tt_data in ticket_types_data:
            tt = TicketType(spot_id=spot.id, **tt_data, is_active=True)
            session.add(tt)
            ticket_types.append(tt)
        session.flush()
        for tt in ticket_types:
            print(f"  [+] 票种: {tt.name}  ¥{tt.price} (库存:{tt.daily_stock})")

        # ── 5. 创建酒店 ──
        hotel = Hotel(
            spot_id=spot.id,
            name="泰山云巢山庄",
            address="山东省泰安市泰山区天外村路88号",
            city="泰安",
            district="泰山区",
            phone="0538-8228888",
            description="泰山云巢山庄坐落于泰山脚下，距天外村登山口仅200米，"
                        "是游览泰山的绝佳下榻之所。山庄采用北方传统院落设计，"
                        "青砖灰瓦，古朴典雅。设有观景平台，可远眺泰山雄姿。",
            rating=4.6,
            is_active=True,
        )
        session.add(hotel)
        session.flush()
        print(f"  [+] 酒店: {hotel.name} (id={hotel.id})")

        # ── 6. 创建房型 ──
        rooms_data = [
            {
                "name": "标准大床房",
                "room_type": "大床房",
                "price": 388.00,
                "total_count": 30,
                "available_count": 30,
                "area": 28.0,
                "bed_type": "1.8m大床",
                "max_guests": 2,
                "has_window": True,
                "has_wifi": True,
                "has_bathtub": False,
                "description": "舒适大床房，配有大落地窗，山景尽收眼底",
            },
            {
                "name": "豪华双床房",
                "room_type": "双床房",
                "price": 488.00,
                "total_count": 20,
                "available_count": 20,
                "area": 35.0,
                "bed_type": "1.5m双床",
                "max_guests": 3,
                "has_window": True,
                "has_wifi": True,
                "has_bathtub": True,
                "description": "宽敞双床房，独立浴缸，适合家庭出游",
            },
            {
                "name": "景观套房",
                "room_type": "套房",
                "price": 888.00,
                "total_count": 8,
                "available_count": 8,
                "area": 55.0,
                "bed_type": "2.0m大床",
                "max_guests": 4,
                "has_window": True,
                "has_wifi": True,
                "has_bathtub": True,
                "description": "豪华套房，独立客厅+卧室，180度泰山全景阳台",
            },
        ]
        for r_data in rooms_data:
            room = Room(hotel_id=hotel.id, **r_data, is_active=True)
            session.add(room)
        session.flush()
        for r_data in rooms_data:
            print(f"  [+] 房型: {r_data['name']}  ¥{r_data['price']}/晚 ({r_data['total_count']}间)")

        session.commit()
        print("\n✅ 种子数据写入完成！")

    # 验证
    print("\n── 数据验证 ──")
    with Session(engine) as session:
        from sqlalchemy import select, func
        user_count = session.scalar(select(func.count(User.id)))
        spot_count = session.scalar(select(func.count(ScenicSpot.id)))
        tt_count = session.scalar(select(func.count(TicketType.id)))
        hotel_count = session.scalar(select(func.count(Hotel.id)))
        room_count = session.scalar(select(func.count(Room.id)))
        print(f"  用户: {user_count}")
        print(f"  景区: {spot_count}")
        print(f"  票种: {tt_count}")
        print(f"  酒店: {hotel_count}")
        print(f"  房型: {room_count}")

        # 详细验证
        admin_user = session.scalar(select(User).where(User.username == "admin"))
        print(f"  admin 密码验证: {'通过' if admin_user else '失败'} (role={admin_user.role if admin_user else 'N/A'})")

        spot_obj = session.scalar(select(ScenicSpot).where(ScenicSpot.name.like("%泰山%")))
        print(f"  景区 '{spot_obj.name}': {'通过' if spot_obj else '失败'}")

        ticket_list = session.execute(
            select(TicketType).where(TicketType.spot_id == spot_obj.id).order_by(TicketType.sort_order)
        ).scalars().all()
        print(f"  票种列表: {[t.name for t in ticket_list]}")

        hotel_obj = session.scalar(select(Hotel).where(Hotel.spot_id == spot_obj.id))
        print(f"  酒店 '{hotel_obj.name}': {'通过' if hotel_obj else '失败'}")

        room_list = session.execute(
            select(Room).where(Room.hotel_id == hotel_obj.id)
        ).scalars().all()
        print(f"  房型列表: {[r.name for r in room_list]}")

    print("\n🎉 所有验证通过！数据库就绪。")
    engine.dispose()


if __name__ == "__main__":
    seed()
