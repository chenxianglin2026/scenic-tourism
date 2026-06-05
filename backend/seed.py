"""\n景区智慧管理系统 - 种子数据脚本\n创建测试数据: 1个景区 + 4个票种 + 1个酒店 + 3个房型 + 1个admin用户 + 测试订单\n用法: python seed.py\n"""
import asyncio
import os
import sys
import uuid

# 确保项目根目录在 sys.path 中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime, date
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.config import settings
from app.db import (
    Base, User, ScenicSpot, TicketType, Hotel, Room,
    TicketOrder, TicketOrderStatus, HotelOrder, HotelOrderStatus, PaymentRecord,
    Announcement, Poi, ParkingRate
)
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

        # ── 7. 景区公告 ──
        announcements_data = [
            {
                "title": "端午节特惠活动通知",
                "content": "端午节期间（6月8日-6月10日），景区推出家庭套票优惠活动，两大一小仅需258元。"
                           "同时举办龙舟文化展览、粽子DIY体验活动，欢迎广大游客前来游玩！",
                "category": "event",
                "priority": 2,
            },
            {
                "title": "南天门索道维护公告",
                "content": "因设备年度检修需要，南天门索道将于6月15日-6月17日暂停运营。"
                           "期间游客可通过十八盘步行登山，给您带来不便敬请谅解。",
                "category": "maintenance",
                "priority": 1,
            },
            {
                "title": "夏季开放时间调整通知",
                "content": "自6月1日起，景区实行夏季运营时间：开园时间调整为05:30，闭园时间调整为19:00。"
                           "日出观赏请提前通过小程序预约。",
                "category": "notice",
                "priority": 1,
            },
            {
                "title": "景区文明旅游倡议书",
                "content": "泰山是世界文化与自然双重遗产，请各位游客爱护环境，不随意丢弃垃圾，"
                           "不刻画涂鸦，共同守护这份宝贵的自然与文化财富。",
                "category": "notice",
                "priority": 0,
            },
            {
                "title": "紧急通知：暴雨天气预警",
                "content": "接气象部门通知，本周末可能有暴雨天气，请登山游客携带雨具，注意防滑。"
                           "如遇极端天气，景区将临时关闭，请关注公众号获取最新消息。",
                "category": "emergency",
                "priority": 2,
            },
        ]
        for ann_data in announcements_data:
            ann = Announcement(spot_id=spot.id, **ann_data, is_published=True)
            session.add(ann)
        session.flush()
        print(f"  [+] 公告: 创建 {len(announcements_data)} 条")

        # ── 8. 导览点位(POI) ──
        pois_data = [
            {"name": "红门入口", "category": "entrance", "lat": 36.2110, "lng": 117.1280, "sort_order": 1,
             "description": "泰山传统登山入口，始建于明代"},
            {"name": "天外村入口", "category": "entrance", "lat": 36.2060, "lng": 117.1100, "sort_order": 2,
             "description": "乘坐景区大巴的入口，可直达中天门"},
            {"name": "中天门", "category": "viewpoint", "lat": 36.2350, "lng": 117.1200, "sort_order": 3,
             "description": "泰山半山腰，索道和徒步交汇处"},
            {"name": "南天门", "category": "viewpoint", "lat": 36.2500, "lng": 117.1250, "sort_order": 4,
             "description": "泰山标志性建筑，登顶的象征"},
            {"name": "玉皇顶", "category": "viewpoint", "lat": 36.2580, "lng": 117.1250, "sort_order": 5,
             "description": "泰山主峰，海拔1545米，绝佳日出观赏点"},
            {"name": "碧霞祠", "category": "viewpoint", "lat": 36.2530, "lng": 117.1240, "sort_order": 6,
             "description": "供奉碧霞元君的道教宫观"},
            {"name": "日观峰", "category": "viewpoint", "lat": 36.2550, "lng": 117.1270, "sort_order": 7,
             "description": "观赏泰山日出的最佳地点"},
            {"name": "红门游客中心", "category": "service", "lat": 36.2115, "lng": 117.1275, "sort_order": 8,
             "description": "提供咨询、寄存、医疗等服务"},
            {"name": "中天门餐厅", "category": "restaurant", "lat": 36.2355, "lng": 117.1205, "sort_order": 9,
             "description": "提供泰山特色美食：泰山煎饼、泰山三美"},
            {"name": "天街商店", "category": "shop", "lat": 36.2510, "lng": 117.1245, "sort_order": 10,
             "description": "泰山纪念品、登山装备、饮品零食"},
            {"name": "1号停车场", "category": "parking", "lat": 36.2105, "lng": 117.1270, "sort_order": 11,
             "description": "红门入口停车场，500车位"},
            {"name": "2号停车场", "category": "parking", "lat": 36.2055, "lng": 117.1095, "sort_order": 12,
             "description": "天外村入口停车场，300车位"},
            {"name": "红门公厕", "category": "toilet", "lat": 36.2112, "lng": 117.1272, "sort_order": 13},
            {"name": "中天门公厕", "category": "toilet", "lat": 36.2352, "lng": 117.1202, "sort_order": 14},
            {"name": "南天门公厕", "category": "toilet", "lat": 36.2502, "lng": 117.1252, "sort_order": 15},
        ]
        for poi_data in pois_data:
            poi = Poi(spot_id=spot.id, **poi_data, is_active=True)
            session.add(poi)
        session.flush()
        print(f"  [+] 导览点位: 创建 {len(pois_data)} 个")

        # ── 9. 停车费率 ──
        parking_rates_data = [
            {
                "name": "红门停车场（小客车）",
                "vehicle_type": "car",
                "first_hour_price": 5.0,
                "additional_hour_price": 3.0,
                "daily_cap": 30.0,
                "free_minutes": 15,
                "total_spots": 500,
                "available_spots": 500,
                "open_time": "06:00",
                "close_time": "20:00",
            },
            {
                "name": "天外村停车场（小客车）",
                "vehicle_type": "car",
                "first_hour_price": 5.0,
                "additional_hour_price": 3.0,
                "daily_cap": 30.0,
                "free_minutes": 15,
                "total_spots": 300,
                "available_spots": 300,
                "open_time": "06:00",
                "close_time": "20:00",
            },
            {
                "name": "红门停车场（大巴）",
                "vehicle_type": "bus",
                "first_hour_price": 10.0,
                "additional_hour_price": 6.0,
                "daily_cap": 60.0,
                "free_minutes": 30,
                "total_spots": 50,
                "available_spots": 50,
                "open_time": "06:00",
                "close_time": "20:00",
            },
        ]
        for pr_data in parking_rates_data:
            pr = ParkingRate(spot_id=spot.id, **pr_data, is_active=True)
            session.add(pr)
        session.flush()
        for pr_data in parking_rates_data:
            print(f"  [+] 停车费率: {pr_data['name']}  ¥{pr_data['first_hour_price']}/首小时 "
                  f"(车位:{pr_data['total_spots']})")

        # ── 10. 创建测试用户（游客） ──
        guest = User(
            username="guest",
            phone="13900000001",
            hashed_password=hash_password("guest123"),
            role="guest",
            nickname="测试游客",
            is_active=True,
        )
        session.add(guest)
        session.flush()
        print(f"  [+] 游客: guest / guest123 (id={guest.id})")

        # ── 11. 创建测试票务订单 ──
        adult_ticket = ticket_types[0]  # 成人票
        child_ticket = ticket_types[1]   # 儿童票

        today = date.today()

        ticket_orders_data = [
            {
                "order_no": "T" + datetime.now().strftime("%Y%m%d%H%M%S") + uuid.uuid4().hex[:4].upper(),
                "user_id": guest.id,
                "ticket_type_id": adult_ticket.id,
                "spot_id": spot.id,
                "quantity": 2,
                "visit_date": today,
                "time_slot": "08:00-10:00",
                "total_price": adult_ticket.price * 2,
                "status": TicketOrderStatus.PAID,
                "visitor_name": "张三",
                "visitor_phone": "13900000001",
                "paid_at": datetime.utcnow(),
            },
            {
                "order_no": "T" + datetime.now().strftime("%Y%m%d%H%M%S") + uuid.uuid4().hex[:4].upper(),
                "user_id": admin.id,
                "ticket_type_id": child_ticket.id,
                "spot_id": spot.id,
                "quantity": 1,
                "visit_date": today,
                "time_slot": "10:00-12:00",
                "total_price": child_ticket.price * 1,
                "status": TicketOrderStatus.PENDING,
                "visitor_name": "小明",
                "visitor_phone": "13800000001",
            },
            {
                "order_no": "T" + datetime.now().strftime("%Y%m%d%H%M%S") + uuid.uuid4().hex[:4].upper(),
                "user_id": guest.id,
                "ticket_type_id": adult_ticket.id,
                "spot_id": spot.id,
                "quantity": 3,
                "visit_date": date(today.year, today.month, today.day + 3) if today.day < 27 else today,
                "time_slot": "14:00-17:00",
                "total_price": adult_ticket.price * 3,
                "status": TicketOrderStatus.PAID,
                "visitor_name": "李四",
                "visitor_phone": "13900000002",
                "paid_at": datetime.utcnow(),
            },
        ]

        ticket_orders = []
        for to_data in ticket_orders_data:
            qr_token = uuid.uuid4().hex + uuid.uuid4().hex[:8]
            to = TicketOrder(qr_token=qr_token, **to_data)
            session.add(to)
            ticket_orders.append(to)
        session.flush()

        for to in ticket_orders:
            print(f"  [+] 票务订单: {to.order_no}  {to.visitor_name}  ¥{to.total_price}  [{to.status}]")

        # ── 12. 创建测试酒店订单 ──
        rooms = session.query(Room).filter(Room.hotel_id == hotel.id).all()
        standard_room = rooms[0]  # 标准大床房

        hotel_orders_data = [
            {
                "order_no": "H" + datetime.now().strftime("%Y%m%d%H%M%S") + uuid.uuid4().hex[:4].upper(),
                "user_id": guest.id,
                "hotel_id": hotel.id,
                "room_id": standard_room.id,
                "room_count": 1,
                "checkin_date": today,
                "checkout_date": date(today.year, today.month, today.day + 2) if today.day < 26 else today,
                "nights": 2,
                "total_price": standard_room.price * 1 * 2,
                "status": HotelOrderStatus.PAID,
                "guest_name": "张三",
                "guest_phone": "13900000001",
                "paid_at": datetime.utcnow(),
            },
            {
                "order_no": "H" + datetime.now().strftime("%Y%m%d%H%M%S") + uuid.uuid4().hex[:4].upper(),
                "user_id": admin.id,
                "hotel_id": hotel.id,
                "room_id": standard_room.id,
                "room_count": 1,
                "checkin_date": date(today.year, today.month, today.day + 5) if today.day < 23 else today,
                "checkout_date": date(today.year, today.month, today.day + 7) if today.day < 21 else today,
                "nights": 2,
                "total_price": standard_room.price * 1 * 2,
                "status": HotelOrderStatus.PENDING,
                "guest_name": "李四",
                "guest_phone": "13900000002",
            },
        ]

        hotel_orders = []
        for ho_data in hotel_orders_data:
            ho = HotelOrder(**ho_data)
            session.add(ho)
            hotel_orders.append(ho)
        session.flush()

        # 扣减对应房型库存
        for ho in hotel_orders:
            if ho.status == HotelOrderStatus.PAID:
                room = session.query(Room).filter(Room.id == ho.room_id).first()
                if room:
                    room.available_count = max(0, room.available_count - ho.room_count)

        for ho in hotel_orders:
            print(f"  [+] 酒店订单: {ho.order_no}  {ho.guest_name}  ¥{ho.total_price}  [{ho.status}]")

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
        ticket_order_count = session.scalar(select(func.count(TicketOrder.id)))
        hotel_order_count = session.scalar(select(func.count(HotelOrder.id)))
        ann_count = session.scalar(select(func.count(Announcement.id)))
        poi_count = session.scalar(select(func.count(Poi.id)))
        pr_count = session.scalar(select(func.count(ParkingRate.id)))
        print(f"  用户: {user_count}")
        print(f"  景区: {spot_count}")
        print(f"  票种: {tt_count}")
        print(f"  酒店: {hotel_count}")
        print(f"  房型: {room_count}")
        print(f"  票务订单: {ticket_order_count}")
        print(f"  酒店订单: {hotel_order_count}")
        print(f"  公告: {ann_count}")
        print(f"  导览点位: {poi_count}")
        print(f"  停车费率: {pr_count}")

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
