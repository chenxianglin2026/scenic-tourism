"""
景区智慧管理系统 - 种子数据脚本
创建测试数据: 3个景区 + 各配4票种 + 各配1酒店+2+房型 + 测试订单 + 停车记录
用法: python seed.py
"""
import os
import sys
import uuid
from datetime import datetime, date, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.config import settings
from app.db import (
    Base, User, ScenicSpot, TicketType, Hotel, Room,
    TicketOrder, TicketOrderStatus, HotelOrder, HotelOrderStatus, PaymentRecord,
    Announcement, Poi, ParkingRate, ParkingRecord
)
from app.api.auth import hash_password


def _future_date(days=0):
    """返回距今天 days 天的日期，兼容性处理"""
    return date.today() + timedelta(days=days)


def _past_date(days=0):
    """返回过去日期"""
    return date.today() - timedelta(days=days)


def _order_no(prefix="T"):
    return prefix + datetime.now().strftime("%Y%m%d%H%M%S") + uuid.uuid4().hex[:4].upper()


def seed():
    db_url = settings.db_sync_url
    print(f"数据库: {db_url}")
    engine = create_engine(db_url, echo=False)

    # 1. 重建表
    print("正在删除旧表...")
    Base.metadata.drop_all(engine)
    print("正在创建新表...")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        # ═══════════════════════════════════════════════
        # 2. 用户
        # ═══════════════════════════════════════════════
        admin = User(
            username="admin", phone="13800000001",
            hashed_password=hash_password("admin123"),
            role="admin", nickname="系统管理员", is_active=True,
        )
        session.add(admin)

        guest1 = User(
            username="guest", phone="13900000001",
            hashed_password=hash_password("guest123"),
            role="guest", nickname="张游客", is_active=True,
        )
        session.add(guest1)

        guest2 = User(
            username="guest2", phone="13900000002",
            hashed_password=hash_password("guest123"),
            role="guest", nickname="李游客", is_active=True,
        )
        session.add(guest2)

        guest3 = User(
            username="guest3", phone="13900000003",
            hashed_password=hash_password("guest123"),
            role="guest", nickname="王游客", is_active=True,
        )
        session.add(guest3)

        staff = User(
            username="staff", phone="13800000002",
            hashed_password=hash_password("staff123"),
            role="staff", nickname="核销员小李", is_active=True,
        )
        session.add(staff)

        session.flush()
        for u in [admin, guest1, guest2, guest3, staff]:
            print(f"  [+] 用户: {u.username} (role={u.role}, id={u.id})")

        all_guests = [guest1, guest2, guest3]

        # ── helpers ──
        ticket_orders_holder = []
        hotel_orders_holder = []
        parking_records_holder = []

        # ═══════════════════════════════════════════════
        # 3. 景区数据工厂
        # ═══════════════════════════════════════════════
        SPOTS = [
            {
                "name": "泰山风景名胜区",
                "address": "山东省泰安市泰山区红门路54号",
                "city": "泰安", "district": "泰山区",
                "phone": "0538-8222606",
                "description": "泰山，又名岱山、岱宗，为五岳之首，有'天下第一山'之称。"
                               "主峰玉皇顶海拔1545米，气势雄伟磅礴。泰山被古人视为'直通帝座'的天堂，"
                               "有'泰山安，四海皆安'的说法。1987年被列为世界文化与自然双重遗产。",
                "open_time": "06:00", "close_time": "18:00",
                "daily_limit": 10000, "rating": 4.8,
                "tickets": [
                    {"name": "成人票", "category": "standard", "price": 115.0,
                     "original_price": 150.0, "daily_stock": 5000,
                     "description": "18-59周岁成人全价票", "min_age": 18, "max_age": 59, "sort_order": 1},
                    {"name": "儿童票", "category": "child", "price": 57.0,
                     "original_price": 75.0, "daily_stock": 2000,
                     "description": "6-17周岁未成年人半价票，身高1.4米以下免票",
                     "min_age": 6, "max_age": 17, "sort_order": 2},
                    {"name": "老人票", "category": "senior", "price": 57.0,
                     "original_price": 75.0, "daily_stock": 2000,
                     "description": "60周岁及以上老年人半价票",
                     "min_age": 60, "max_age": None, "sort_order": 3},
                    {"name": "团体票（10人起）", "category": "group", "price": 90.0,
                     "original_price": 115.0, "daily_stock": 2000,
                     "description": "10人及以上团体优惠票", "min_age": None, "max_age": None, "sort_order": 4},
                ],
                "hotel": {
                    "name": "泰山云巢山庄",
                    "address": "山东省泰安市泰山区天外村路88号",
                    "city": "泰安", "district": "泰山区",
                    "phone": "0538-8228888",
                    "description": "坐落于泰山脚下，距天外村登山口仅200米，"
                                   "采用北方传统院落设计，青砖灰瓦古朴典雅。设有观景平台可远眺泰山雄姿。",
                    "rating": 4.6,
                    "rooms": [
                        {"name": "标准大床房", "room_type": "大床房", "price": 388.0,
                         "total_count": 30, "area": 28.0, "bed_type": "1.8m大床",
                         "max_guests": 2, "has_window": True, "has_wifi": True, "has_bathtub": False,
                         "description": "舒适大床房，大落地窗山景尽收眼底"},
                        {"name": "豪华双床房", "room_type": "双床房", "price": 488.0,
                         "total_count": 20, "area": 35.0, "bed_type": "1.5m双床",
                         "max_guests": 3, "has_window": True, "has_wifi": True, "has_bathtub": True,
                         "description": "宽敞双床房，独立浴缸，适合家庭出游"},
                        {"name": "景观套房", "room_type": "套房", "price": 888.0,
                         "total_count": 8, "area": 55.0, "bed_type": "2.0m大床",
                         "max_guests": 4, "has_window": True, "has_wifi": True, "has_bathtub": True,
                         "description": "豪华套房，独立客厅+卧室，180度泰山全景阳台"},
                    ],
                },
                "announcements": [
                    {"title": "端午节特惠活动通知",
                     "content": "端午节期间景区推出家庭套票优惠活动，两大一小仅需258元。同时举办龙舟文化展览、粽子DIY体验活动！",
                     "category": "event", "priority": 2},
                    {"title": "南天门索道维护公告",
                     "content": "南天门索道将于6月15日-17日暂停运营，期间游客可通过十八盘步行登山。",
                     "category": "maintenance", "priority": 1},
                    {"title": "夏季开放时间调整",
                     "content": "6月1日起夏季运营时间：开园05:30，闭园19:00。日出观赏请提前预约。",
                     "category": "notice", "priority": 1},
                    {"title": "文明旅游倡议书",
                     "content": "泰山是世界双遗产，请爱护环境、不丢垃圾、不刻画涂鸦。",
                     "category": "notice", "priority": 0},
                ],
                "pois": [
                    {"name": "红门入口", "category": "entrance",
                     "lat": 36.2110, "lng": 117.1280, "sort_order": 1,
                     "description": "泰山传统登山入口，始建于明代"},
                    {"name": "天外村入口", "category": "entrance",
                     "lat": 36.2060, "lng": 117.1100, "sort_order": 2,
                     "description": "乘坐景区大巴入口，可直达中天门"},
                    {"name": "中天门", "category": "viewpoint",
                     "lat": 36.2350, "lng": 117.1200, "sort_order": 3,
                     "description": "泰山半山腰，索道和徒步交汇处"},
                    {"name": "南天门", "category": "viewpoint",
                     "lat": 36.2500, "lng": 117.1250, "sort_order": 4,
                     "description": "泰山标志性建筑，登顶象征"},
                    {"name": "玉皇顶", "category": "viewpoint",
                     "lat": 36.2580, "lng": 117.1250, "sort_order": 5,
                     "description": "泰山主峰海拔1545米，绝佳日出观赏点"},
                    {"name": "日观峰", "category": "viewpoint",
                     "lat": 36.2550, "lng": 117.1270, "sort_order": 6,
                     "description": "观赏泰山日出的最佳地点"},
                    {"name": "红门游客中心", "category": "service",
                     "lat": 36.2115, "lng": 117.1275, "sort_order": 7,
                     "description": "提供咨询、寄存、医疗等服务"},
                    {"name": "1号停车场", "category": "parking",
                     "lat": 36.2105, "lng": 117.1270, "sort_order": 8,
                     "description": "红门入口停车场，500车位"},
                    {"name": "2号停车场", "category": "parking",
                     "lat": 36.2055, "lng": 117.1095, "sort_order": 9,
                     "description": "天外村入口停车场，300车位"},
                    {"name": "红门公厕", "category": "toilet",
                     "lat": 36.2112, "lng": 117.1272, "sort_order": 10},
                    {"name": "中天门公厕", "category": "toilet",
                     "lat": 36.2352, "lng": 117.1202, "sort_order": 11},
                ],
                "parking_rates": [
                    {"name": "红门停车场（小客车）", "vehicle_type": "car",
                     "first_hour_price": 5.0, "additional_hour_price": 3.0,
                     "daily_cap": 30.0, "free_minutes": 15,
                     "total_spots": 500, "open_time": "06:00", "close_time": "20:00"},
                    {"name": "天外村停车场（小客车）", "vehicle_type": "car",
                     "first_hour_price": 5.0, "additional_hour_price": 3.0,
                     "daily_cap": 30.0, "free_minutes": 15,
                     "total_spots": 300, "open_time": "06:00", "close_time": "20:00"},
                    {"name": "红门停车场（大巴）", "vehicle_type": "bus",
                     "first_hour_price": 10.0, "additional_hour_price": 6.0,
                     "daily_cap": 60.0, "free_minutes": 30,
                     "total_spots": 50, "open_time": "06:00", "close_time": "20:00"},
                ],
                # 票务订单: (user_idx, ticket_idx, qty, visit_offset, status, visitor_name, phone)
                "ticket_orders": [
                    (0, 0, 2, 0, TicketOrderStatus.PAID, "张三", "13900000001"),
                    (0, 1, 1, 0, TicketOrderStatus.VERIFIED, "张小宝", "13900000001"),
                    (1, 0, 3, 1, TicketOrderStatus.PAID, "李四", "13900000002"),
                    (1, 2, 1, 2, TicketOrderStatus.REFUNDED, "李大爷", "13900000002"),
                    (2, 3, 10, 3, TicketOrderStatus.PAID, "王导游", "13900000003"),
                ],
                # 酒店订单: (user_idx, room_idx, checkin_offset_days, nights, status)
                "hotel_orders": [
                    (0, 0, 0, 2, HotelOrderStatus.PAID),
                    (1, 1, 5, 1, HotelOrderStatus.CHECKED_IN),
                    (2, 2, -3, 2, HotelOrderStatus.COMPLETED),
                ],
                # 停车记录: (rate_idx, plate, status, pay_status)
                "parking_records": [
                    (0, "鲁J·12345", "completed", "paid"),
                    (0, "鲁J·67890", "completed", "paid"),
                    (1, "鲁J·A0001", "parking", "unpaid"),
                    (1, "鲁J·B0002", "completed", "paid"),
                    (2, "鲁J·C8888", "completed", "paid"),
                ],
            },
            # ── 西湖 ──
            {
                "name": "杭州西湖风景名胜区",
                "address": "浙江省杭州市西湖区龙井路1号",
                "city": "杭州", "district": "西湖区",
                "phone": "0571-87179617",
                "description": "西湖，位于浙江省杭州市西面，是中国大陆首批国家重点风景名胜区"
                               "和中国十大风景名胜之一。西湖三面环山，面积约6.39平方公里，"
                               "以'一山、二塔、三岛、三堤、五湖'为基本格局，"
                               "著名的西湖十景闻名中外。2011年被列为世界文化景观遗产。",
                "open_time": "00:00", "close_time": "23:59",
                "daily_limit": 50000, "rating": 4.9,
                "tickets": [
                    {"name": "成人票", "category": "standard", "price": 90.0,
                     "original_price": 100.0, "daily_stock": 15000,
                     "description": "西湖景区成人全价票（含雷峰塔、岳王庙等收费景点）",
                     "min_age": 18, "max_age": 59, "sort_order": 1},
                    {"name": "学生票", "category": "student", "price": 45.0,
                     "original_price": 50.0, "daily_stock": 8000,
                     "description": "全日制在校学生半价优惠票，需持有效学生证",
                     "min_age": 12, "max_age": 26, "sort_order": 2},
                    {"name": "西湖游船票", "category": "special", "price": 55.0,
                     "original_price": 70.0, "daily_stock": 3000,
                     "description": "湖滨码头往返三潭印月，含上岛门票",
                     "min_age": None, "max_age": None, "sort_order": 3},
                    {"name": "儿童/老人票", "category": "senior", "price": 45.0,
                     "original_price": 50.0, "daily_stock": 5000,
                     "description": "6-17周岁儿童或60岁以上老人半价",
                     "min_age": 6, "max_age": None, "sort_order": 4},
                ],
                "hotel": {
                    "name": "西湖国宾馆",
                    "address": "浙江省杭州市西湖区杨公堤18号",
                    "city": "杭州", "district": "西湖区",
                    "phone": "0571-87979889",
                    "description": "西湖国宾馆坐落在西湖核心景区杨公堤畔，三面临湖一面靠山，"
                                   "曾是清代皇家行宫。园林面积达36万平方米，亭台楼阁错落有致，"
                                   "被誉为'西湖第一名园'。",
                    "rating": 4.9,
                    "rooms": [
                        {"name": "湖景大床房", "room_type": "大床房", "price": 888.0,
                         "total_count": 40, "area": 32.0, "bed_type": "1.8m大床",
                         "max_guests": 2, "has_window": True, "has_wifi": True, "has_bathtub": True,
                         "description": "一线湖景大床房，推窗即见西湖，日出日落尽收眼底"},
                        {"name": "园林双床房", "room_type": "双床房", "price": 688.0,
                         "total_count": 25, "area": 30.0, "bed_type": "1.5m双床",
                         "max_guests": 2, "has_window": True, "has_wifi": True, "has_bathtub": False,
                         "description": "古典园林景观，鸟语花香，宁静雅致"},
                        {"name": "总统套房", "room_type": "套房", "price": 2888.0,
                         "total_count": 3, "area": 120.0, "bed_type": "2.0m大床",
                         "max_guests": 6, "has_window": True, "has_wifi": True, "has_bathtub": True,
                         "description": "顶级总统套房，私人花园+管家服务，名流政要下榻之选"},
                    ],
                },
                "announcements": [
                    {"title": "西湖音乐喷泉升级公告",
                     "content": "湖滨音乐喷泉将于下周进行系统升级，暂停表演一周，敬请谅解。",
                     "category": "maintenance", "priority": 1},
                    {"title": "荷花节即将开幕",
                     "content": "第二十届西湖荷花节将于6月20日在曲院风荷盛大开幕！",
                     "category": "event", "priority": 3},
                    {"title": "夜游西湖新增航线",
                     "content": "新增钱王祠-三潭印月夜游航线，每晚7点起航，可赏雷峰塔夜景。",
                     "category": "notice", "priority": 2},
                ],
                "pois": [
                    {"name": "湖滨入口", "category": "entrance",
                     "lat": 30.2560, "lng": 120.1650, "sort_order": 1,
                     "description": "西湖东侧主入口，近地铁龙翔桥站"},
                    {"name": "断桥残雪", "category": "viewpoint",
                     "lat": 30.2590, "lng": 120.1520, "sort_order": 2,
                     "description": "西湖十景之一，《白蛇传》传说发源地"},
                    {"name": "雷峰塔", "category": "viewpoint",
                     "lat": 30.2340, "lng": 120.1480, "sort_order": 3,
                     "description": "西湖标志性建筑，可登塔俯瞰西湖全景"},
                    {"name": "三潭印月", "category": "viewpoint",
                     "lat": 30.2400, "lng": 120.1420, "sort_order": 4,
                     "description": "西湖十景之首，一元人民币背面图案"},
                    {"name": "苏堤春晓", "category": "viewpoint",
                     "lat": 30.2480, "lng": 120.1400, "sort_order": 5,
                     "description": "苏轼所建，长约2.8公里，横贯西湖南北"},
                    {"name": "岳王庙", "category": "viewpoint",
                     "lat": 30.2540, "lng": 120.1370, "sort_order": 6,
                     "description": "纪念民族英雄岳飞，始建于南宋"},
                    {"name": "湖滨游客中心", "category": "service",
                     "lat": 30.2565, "lng": 120.1645, "sort_order": 7,
                     "description": "提供咨询、寄存、轮椅租赁等服务"},
                    {"name": "停车场A区", "category": "parking",
                     "lat": 30.2570, "lng": 120.1635, "sort_order": 8,
                     "description": "湖滨地下停车场，800车位"},
                    {"name": "湖滨公厕", "category": "toilet",
                     "lat": 30.2568, "lng": 120.1648, "sort_order": 9},
                    {"name": "苏堤公厕", "category": "toilet",
                     "lat": 30.2485, "lng": 120.1405, "sort_order": 10},
                ],
                "parking_rates": [
                    {"name": "湖滨地下停车场（小客车）", "vehicle_type": "car",
                     "first_hour_price": 10.0, "additional_hour_price": 5.0,
                     "daily_cap": 50.0, "free_minutes": 15,
                     "total_spots": 800, "open_time": "00:00", "close_time": "23:59"},
                    {"name": "西湖景区大巴停车场", "vehicle_type": "bus",
                     "first_hour_price": 20.0, "additional_hour_price": 10.0,
                     "daily_cap": 100.0, "free_minutes": 30,
                     "total_spots": 80, "open_time": "06:00", "close_time": "22:00"},
                ],
                "ticket_orders": [
                    (0, 0, 2, 0, TicketOrderStatus.PAID, "张三", "13900000001"),
                    (1, 2, 2, 0, TicketOrderStatus.VERIFIED, "李四", "13900000002"),
                    (2, 1, 1, 1, TicketOrderStatus.PAID, "王同学", "13900000003"),
                    (0, 3, 2, -2, TicketOrderStatus.REFUNDED, "张三", "13900000001"),
                ],
                "hotel_orders": [
                    (0, 1, 0, 1, HotelOrderStatus.PAID),
                    (1, 0, 3, 2, HotelOrderStatus.PENDING),
                    (2, 0, -5, 2, HotelOrderStatus.COMPLETED),
                ],
                "parking_records": [
                    (0, "浙A·D5678", "completed", "paid"),
                    (0, "浙A·E9012", "completed", "paid"),
                    (0, "浙A·F3456", "parking", "unpaid"),
                    (0, "沪B·G7890", "completed", "paid"),
                    (1, "苏A·H1234", "completed", "paid"),
                ],
            },
            # ── 黄山 ──
            {
                "name": "黄山风景区",
                "address": "安徽省黄山市黄山区汤口镇",
                "city": "黄山", "district": "黄山区",
                "phone": "0559-5561111",
                "description": "黄山，位于安徽省南部黄山市境内，是世界文化与自然双重遗产、"
                               "世界地质公园、国家5A级旅游景区。黄山以奇松、怪石、云海、温泉、"
                               "冬雪'五绝'著称于世，被誉为'天下第一奇山'。"
                               "徐霞客曾赞叹：'五岳归来不看山，黄山归来不看岳'。",
                "open_time": "06:30", "close_time": "17:00",
                "daily_limit": 8000, "rating": 4.9,
                "tickets": [
                    {"name": "成人票", "category": "standard", "price": 190.0,
                     "original_price": 230.0, "daily_stock": 4000,
                     "description": "黄山风景区成人全价票（含景区接驳车）",
                     "min_age": 18, "max_age": 59, "sort_order": 1},
                    {"name": "学生票", "category": "student", "price": 95.0,
                     "original_price": 190.0, "daily_stock": 2000,
                     "description": "全日制学生半价票，需持有效学生证",
                     "min_age": 12, "max_age": 26, "sort_order": 2},
                    {"name": "云谷索道票（上行）", "category": "special", "price": 80.0,
                     "original_price": 90.0, "daily_stock": 3000,
                     "description": "云谷寺-白鹅岭索道上行票，8分钟直达山顶",
                     "min_age": None, "max_age": None, "sort_order": 3},
                    {"name": "老人/儿童票", "category": "senior", "price": 95.0,
                     "original_price": 190.0, "daily_stock": 1500,
                     "description": "60岁以上老人或6-17岁儿童半价",
                     "min_age": 6, "max_age": None, "sort_order": 4},
                ],
                "hotel": {
                    "name": "黄山白云宾馆",
                    "address": "安徽省黄山市黄山区黄山风景区天海景区",
                    "city": "黄山", "district": "黄山区",
                    "phone": "0559-5582708",
                    "description": "黄山白云宾馆坐落在海拔1700米的黄山天海景区，"
                                   "毗邻光明顶，是黄山山上规模最大的四星级酒店。"
                                   "入住即可观云海日出、赏奇松怪石，体验'睡在云端的酒店'。",
                    "rating": 4.7,
                    "rooms": [
                        {"name": "山景标准间", "room_type": "标准间", "price": 680.0,
                         "total_count": 60, "area": 22.0, "bed_type": "1.2m双床",
                         "max_guests": 2, "has_window": True, "has_wifi": True, "has_bathtub": False,
                         "description": "温馨山景标准间，推窗可观莲花峰，含双人早餐"},
                        {"name": "云海观景房", "room_type": "大床房", "price": 1280.0,
                         "total_count": 20, "area": 35.0, "bed_type": "1.8m大床",
                         "max_guests": 2, "has_window": True, "has_wifi": True, "has_bathtub": True,
                         "description": "观云海日出的绝佳房型，落地窗正对光明顶，含双早+下午茶"},
                        {"name": "豪华套房", "room_type": "套房", "price": 2380.0,
                         "total_count": 5, "area": 65.0, "bed_type": "2.0m大床",
                         "max_guests": 4, "has_window": True, "has_wifi": True, "has_bathtub": True,
                         "description": "山顶顶级套房，独立客厅+观景阳台，赠送云海日出摄影服务"},
                    ],
                },
                "announcements": [
                    {"title": "西海大峡谷开放通知",
                     "content": "西海大峡谷已完成冬季维护，4月1日起正式对外开放，欢迎游客前来体验！",
                     "category": "notice", "priority": 2},
                    {"title": "云谷索道年度检修",
                     "content": "云谷索道将于每月第一个周一例行检修，检修日索道暂停运营半天（6:30-12:00）。",
                     "category": "maintenance", "priority": 1},
                    {"title": "黄山杜鹃花节",
                     "content": "5月黄山杜鹃花盛开，玉屏楼至光明顶沿途杜鹃花海美不胜收，摄影大赛同步进行中！",
                     "category": "event", "priority": 3},
                    {"title": "雷雨天气安全提示",
                     "content": "夏季黄山雷雨多发，请勿在山顶空旷处使用手机，避免在大树下避雨。",
                     "category": "emergency", "priority": 2},
                ],
                "pois": [
                    {"name": "南大门入口", "category": "entrance",
                     "lat": 30.0860, "lng": 118.1820, "sort_order": 1,
                     "description": "黄山南大门（汤口），主要登山入口"},
                    {"name": "云谷寺", "category": "entrance",
                     "lat": 30.1200, "lng": 118.1800, "sort_order": 2,
                     "description": "云谷索道下站，可乘索道或徒步上山"},
                    {"name": "光明顶", "category": "viewpoint",
                     "lat": 30.1420, "lng": 118.1650, "sort_order": 3,
                     "description": "黄山第二高峰海拔1860米，日出云海最佳观赏点"},
                    {"name": "莲花峰", "category": "viewpoint",
                     "lat": 30.1350, "lng": 118.1680, "sort_order": 4,
                     "description": "黄山最高峰海拔1864.8米，形似莲花得名"},
                    {"name": "迎客松", "category": "viewpoint",
                     "lat": 30.1280, "lng": 118.1720, "sort_order": 5,
                     "description": "黄山标志性景观，树龄逾800年，位于玉屏楼"},
                    {"name": "西海大峡谷", "category": "viewpoint",
                     "lat": 30.1450, "lng": 118.1580, "sort_order": 6,
                     "description": "黄山最精华的峡谷景区，怪石嶙峋步步惊心"},
                    {"name": "玉屏楼游客中心", "category": "service",
                     "lat": 30.1285, "lng": 118.1725, "sort_order": 7,
                     "description": "提供咨询、医疗救助、热水补给等服务"},
                    {"name": "南门停车场", "category": "parking",
                     "lat": 30.0870, "lng": 118.1810, "sort_order": 8,
                     "description": "汤口游客换乘中心停车场，1000车位"},
                    {"name": "光明顶公厕", "category": "toilet",
                     "lat": 30.1422, "lng": 118.1652, "sort_order": 9},
                ],
                "parking_rates": [
                    {"name": "汤口换乘中心停车场（小客车）", "vehicle_type": "car",
                     "first_hour_price": 8.0, "additional_hour_price": 4.0,
                     "daily_cap": 40.0, "free_minutes": 15,
                     "total_spots": 1000, "open_time": "06:00", "close_time": "20:00"},
                    {"name": "汤口大巴停车场", "vehicle_type": "bus",
                     "first_hour_price": 15.0, "additional_hour_price": 8.0,
                     "daily_cap": 80.0, "free_minutes": 30,
                     "total_spots": 60, "open_time": "06:00", "close_time": "20:00"},
                ],
                "ticket_orders": [
                    (0, 0, 2, 0, TicketOrderStatus.PAID, "张三", "13900000001"),
                    (1, 2, 2, 0, TicketOrderStatus.VERIFIED, "李四", "13900000002"),
                    (2, 1, 1, 2, TicketOrderStatus.PAID, "王同学", "13900000003"),
                    (0, 0, 1, -1, TicketOrderStatus.REFUNDED, "张三", "13900000001"),
                    (1, 3, 2, 3, TicketOrderStatus.PAID, "李大爷", "13900000002"),
                ],
                "hotel_orders": [
                    (0, 1, 1, 1, HotelOrderStatus.PAID),
                    (1, 0, -5, 2, HotelOrderStatus.COMPLETED),
                    (2, 0, 7, 2, HotelOrderStatus.PENDING),
                    (0, 2, -10, 1, HotelOrderStatus.COMPLETED),
                ],
                "parking_records": [
                    (0, "皖J·A1234", "completed", "paid"),
                    (0, "皖J·B5678", "completed", "paid"),
                    (0, "沪C·D9012", "parking", "unpaid"),
                    (0, "皖J·E3456", "completed", "paid"),
                    (1, "苏B·F7890", "completed", "paid"),
                    (1, "皖J·G0123", "completed", "paid"),
                ],
            },
        ]

        ticket_types_all = []  # flat list: [(spot_idx, TicketType), ...]
        hotels_all = []        # flat list: [(spot_idx, Hotel), ...]
        rooms_all = []         # flat list: [(spot_idx, hotel_idx, Room), ...]
        parking_rates_all = [] # flat list: [(spot_idx, ParkingRate), ...]

        for si, spot_cfg in enumerate(SPOTS):
            # ── 创建景区 ──
            spot = ScenicSpot(
                name=spot_cfg["name"], address=spot_cfg["address"],
                city=spot_cfg["city"], district=spot_cfg["district"],
                phone=spot_cfg["phone"], description=spot_cfg["description"],
                open_time=spot_cfg["open_time"], close_time=spot_cfg["close_time"],
                daily_limit=spot_cfg["daily_limit"], rating=spot_cfg["rating"],
                is_active=True,
            )
            session.add(spot)
            session.flush()
            print(f"\n{'='*60}")
            print(f"  🏔️  景区: {spot.name} (id={spot.id})")

            # ── 票种 ──
            spot_tickets = []
            for tt_data in spot_cfg["tickets"]:
                tt = TicketType(spot_id=spot.id, **tt_data, is_active=True)
                session.add(tt)
                spot_tickets.append(tt)
            session.flush()
            ticket_types_all.append(spot_tickets)
            for tt in spot_tickets:
                print(f"    🎫 票种: {tt.name}  ¥{tt.price} (库存:{tt.daily_stock})")

            # ── 酒店 ──
            h_cfg = spot_cfg["hotel"]
            hotel = Hotel(
                spot_id=spot.id, name=h_cfg["name"], address=h_cfg["address"],
                city=h_cfg["city"], district=h_cfg["district"],
                phone=h_cfg["phone"], description=h_cfg["description"],
                rating=h_cfg["rating"], is_active=True,
            )
            session.add(hotel)
            session.flush()
            hotels_all.append(hotel)
            print(f"    🏨 酒店: {hotel.name} (id={hotel.id})")

            # ── 房型 ──
            spot_rooms = []
            for r_data in h_cfg["rooms"]:
                room = Room(hotel_id=hotel.id, **r_data, is_active=True)
                session.add(room)
                spot_rooms.append(room)
            session.flush()
            rooms_all.append(spot_rooms)
            for r in spot_rooms:
                print(f"    🛏️  房型: {r.name}  ¥{r.price}/晚 ({r.total_count}间)")

            # ── 公告 ──
            for ann_data in spot_cfg["announcements"]:
                ann = Announcement(spot_id=spot.id, **ann_data, is_published=True)
                session.add(ann)
            session.flush()
            print(f"    📢 公告: {len(spot_cfg['announcements'])} 条")

            # ── POI ──
            for poi_data in spot_cfg["pois"]:
                poi_data_copy = dict(poi_data)
                poi = Poi(spot_id=spot.id, **poi_data_copy, is_active=True)
                session.add(poi)
            session.flush()
            print(f"    📍 导览点位: {len(spot_cfg['pois'])} 个")

            # ── 停车费率 ──
            spot_prs = []
            for pr_data in spot_cfg["parking_rates"]:
                pr = ParkingRate(spot_id=spot.id, **pr_data, is_active=True)
                session.add(pr)
                spot_prs.append(pr)
            session.flush()
            parking_rates_all.append(spot_prs)
            for pr_data in spot_cfg["parking_rates"]:
                print(f"    🅿️  停车费率: {pr_data['name']}  ¥{pr_data['first_hour_price']}/首小时")

            # ── 票务订单 ──
            spot_ticket_orders = []
            for to_cfg in spot_cfg["ticket_orders"]:
                u_idx, t_idx, qty, v_offset, status, vname, vphone = to_cfg
                user = all_guests[u_idx]
                tk = spot_tickets[t_idx]
                visit_date = _future_date(v_offset) if v_offset >= 0 else _past_date(abs(v_offset))
                to = TicketOrder(
                    order_no=_order_no("T"),
                    user_id=user.id,
                    ticket_type_id=tk.id,
                    spot_id=spot.id,
                    quantity=qty,
                    visit_date=visit_date,
                    time_slot="08:00-10:00",
                    total_price=tk.price * qty,
                    status=status,
                    visitor_name=vname,
                    visitor_phone=vphone,
                    paid_at=datetime.utcnow() if status in (TicketOrderStatus.PAID, TicketOrderStatus.VERIFIED, TicketOrderStatus.REFUNDED) else None,
                    qr_token=uuid.uuid4().hex + uuid.uuid4().hex[:8],
                )
                session.add(to)
                spot_ticket_orders.append(to)
            session.flush()
            ticket_orders_holder.extend(spot_ticket_orders)
            status_counts = {}
            for to in spot_ticket_orders:
                sc = status_counts.get(to.status, 0)
                status_counts[to.status] = sc + 1
            status_str = ", ".join(f"{k}:{v}" for k, v in status_counts.items())
            print(f"    🎟️  票务订单: {len(spot_ticket_orders)} 个 ({status_str})")

            # ── 酒店订单 ──
            spot_hotel_orders = []
            for ho_cfg in spot_cfg["hotel_orders"]:
                u_idx, r_idx, checkin_offset, nights, status = ho_cfg
                user = all_guests[u_idx]
                room = spot_rooms[r_idx]
                checkin = _future_date(checkin_offset) if checkin_offset >= 0 else _past_date(abs(checkin_offset))
                checkout = checkin + timedelta(days=nights)
                ho = HotelOrder(
                    order_no=_order_no("H"),
                    user_id=user.id,
                    hotel_id=hotel.id,
                    room_id=room.id,
                    room_count=1,
                    checkin_date=checkin,
                    checkout_date=checkout,
                    nights=nights,
                    total_price=room.price * 1 * nights,
                    status=status,
                    guest_name=user.nickname,
                    guest_phone=user.phone,
                    paid_at=datetime.utcnow() if status in (HotelOrderStatus.PAID, HotelOrderStatus.CHECKED_IN, HotelOrderStatus.COMPLETED) else None,
                )
                session.add(ho)
                spot_hotel_orders.append(ho)
                # 扣减库存 (已支付/已入住/已完成)
                if status in (HotelOrderStatus.PAID, HotelOrderStatus.CHECKED_IN, HotelOrderStatus.COMPLETED):
                    room.available_count = max(0, room.available_count - 1)
            session.flush()
            hotel_orders_holder.extend(spot_hotel_orders)
            ho_status_counts = {}
            for ho in spot_hotel_orders:
                sc = ho_status_counts.get(ho.status, 0)
                ho_status_counts[ho.status] = sc + 1
            ho_status_str = ", ".join(f"{k}:{v}" for k, v in ho_status_counts.items())
            print(f"    🏨 酒店订单: {len(spot_hotel_orders)} 个 ({ho_status_str})")

            # ── 停车记录 ──
            spot_parking_records = []
            for pr_cfg in spot_cfg["parking_records"]:
                r_idx, plate, p_status, pay_status = pr_cfg
                rate = spot_prs[r_idx]
                checkin = datetime.utcnow() - timedelta(hours=2, minutes=30)
                checkout = datetime.utcnow() if p_status == "completed" else None
                duration = 150 if p_status == "completed" else None  # 2.5小时
                total_fee = (
                    rate.first_hour_price + rate.additional_hour_price * 2
                    if p_status == "completed" else None
                )
                pr = ParkingRecord(
                    rate_id=rate.id,
                    user_id=all_guests[r_idx % len(all_guests)].id if p_status != "parking" else None,
                    plate_number=plate,
                    vehicle_type=rate.vehicle_type,
                    checkin_time=checkin,
                    checkout_time=checkout,
                    duration_minutes=duration,
                    total_fee=total_fee,
                    status=p_status,
                    pay_status=pay_status,
                    pay_method="wechat" if pay_status == "paid" else None,
                    paid_at=datetime.utcnow() if pay_status == "paid" else None,
                )
                session.add(pr)
                spot_parking_records.append(pr)
            session.flush()
            parking_records_holder.extend(spot_parking_records)
            pr_status_counts = {}
            for pr in spot_parking_records:
                sc = pr_status_counts.get(pr.status, 0)
                pr_status_counts[pr.status] = sc + 1
            pr_status_str = ", ".join(f"{k}:{v}" for k, v in pr_status_counts.items())
            print(f"    🚗 停车记录: {len(spot_parking_records)} 条 ({pr_status_str})")

        # ═══════════════════════════════════════════════
        # 支付记录 - 为每个已支付订单创建
        # ═══════════════════════════════════════════════
        pay_count = 0
        for to in ticket_orders_holder:
            if to.status in (TicketOrderStatus.PAID, TicketOrderStatus.VERIFIED):
                session.add(PaymentRecord(
                    order_no=to.order_no,
                    order_type="ticket",
                    transaction_id="TXN" + uuid.uuid4().hex[:12].upper(),
                    amount=to.total_price,
                    status="success",
                    pay_method="wechat_jsapi",
                    pay_time=datetime.utcnow(),
                ))
                pay_count += 1
        for ho in hotel_orders_holder:
            if ho.status in (HotelOrderStatus.PAID, HotelOrderStatus.CHECKED_IN, HotelOrderStatus.COMPLETED):
                session.add(PaymentRecord(
                    order_no=ho.order_no,
                    order_type="hotel",
                    transaction_id="TXN" + uuid.uuid4().hex[:12].upper(),
                    amount=ho.total_price,
                    status="success",
                    pay_method="wechat_jsapi",
                    pay_time=datetime.utcnow(),
                ))
                pay_count += 1
        session.flush()
        print(f"\n  💰 支付记录: {pay_count} 条")

        session.commit()
        print("\n✅ 种子数据写入完成！")

    # ═══════════════════════════════════════════════
    # 验证
    # ═══════════════════════════════════════════════
    print("\n" + "=" * 60)
    print("── 数据验证 ──")
    print("=" * 60)
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
        record_count = session.scalar(select(func.count(ParkingRecord.id)))
        pay_count = session.scalar(select(func.count(PaymentRecord.id)))

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
        print(f"  停车记录: {record_count}")
        print(f"  支付记录: {pay_count}")

        # 按状态统计票务订单
        print("\n  票务订单状态分布:")
        to_status = session.execute(
            select(TicketOrder.status, func.count(TicketOrder.id)).group_by(TicketOrder.status)
        ).all()
        for s, c in to_status:
            print(f"    {s}: {c}")

        print("\n  酒店订单状态分布:")
        ho_status = session.execute(
            select(HotelOrder.status, func.count(HotelOrder.id)).group_by(HotelOrder.status)
        ).all()
        for s, c in ho_status:
            print(f"    {s}: {c}")

        print("\n  停车记录状态分布:")
        pr_status = session.execute(
            select(ParkingRecord.status, func.count(ParkingRecord.id)).group_by(ParkingRecord.status)
        ).all()
        for s, c in pr_status:
            print(f"    {s}: {c}")

        # 逐景区详情
        spots = session.execute(select(ScenicSpot).order_by(ScenicSpot.id)).scalars().all()
        for sp in spots:
            tts = session.execute(select(TicketType).where(TicketType.spot_id == sp.id).order_by(TicketType.sort_order)).scalars().all()
            htl = session.scalar(select(Hotel).where(Hotel.spot_id == sp.id))
            rms = session.execute(select(Room).where(Room.hotel_id == htl.id)).scalars().all() if htl else []
            tos = session.execute(select(TicketOrder).where(TicketOrder.spot_id == sp.id)).scalars().all()
            hos = session.execute(select(HotelOrder).where(HotelOrder.hotel_id == htl.id)).scalars().all() if htl else []
            prs = session.execute(select(ParkingRate).where(ParkingRate.spot_id == sp.id)).scalars().all()
            records = session.execute(
                select(ParkingRecord).where(ParkingRecord.rate_id.in_([pr.id for pr in prs]))
            ).scalars().all() if prs else []
            anns = session.execute(select(Announcement).where(Announcement.spot_id == sp.id)).scalars().all()
            pois = session.execute(select(Poi).where(Poi.spot_id == sp.id)).scalars().all()

            print(f"\n  🏔️  {sp.name}:")
            print(f"    票种: {len(tts)} ({[t.name for t in tts]})")
            print(f"    酒店: {htl.name if htl else 'N/A'}")
            print(f"    房型: {len(rms)} ({[r.name for r in rms]})")
            print(f"    票务订单: {len(tos)}")
            print(f"    酒店订单: {len(hos)}")
            print(f"    停车费率: {len(prs)}")
            print(f"    停车记录: {len(records)}")
            print(f"    公告: {len(anns)}")
            print(f"    POI: {len(pois)}")

        # admin 验证
        admin_user = session.scalar(select(User).where(User.username == "admin"))
        print(f"\n  admin 密码验证: {'通过' if admin_user else '失败'} (role={admin_user.role if admin_user else 'N/A'})")

    print("\n🎉 全部验证完成！数据库就绪。")
    engine.dispose()


if __name__ == "__main__":
    seed()
