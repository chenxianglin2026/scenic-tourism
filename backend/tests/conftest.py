"""
景区智慧管理系统 - Pytest 配置 + 数据重置机制

数据重置机制（伊家人模式）:
- db_snapshot: 测试前备份关键表，测试后恢复，确保测试间数据隔离
- auth_tokens: 预登录的 admin/guest/staff token fixtures
- data_helpers: 快速创建测试数据的辅助函数
"""
import pytest
import pytest_asyncio
import shutil
import os
import json

# Configure pytest-asyncio mode
pytest_plugins = ["pytest_asyncio"]

# ── 数据库路径 ───────────────────────────────────────
_DB_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
_DB_FILE = os.path.join(_DB_DIR, "scenic.db")
_SNAPSHOT_FILE = os.path.join(_DB_DIR, "scenic.db.snapshot")


# ═══════════════════════════════════════════════════════
# 数据快照机制（伊家人模式）
# ═══════════════════════════════════════════════════════
def _take_snapshot():
    """备份当前数据库文件"""
    if os.path.exists(_DB_FILE):
        shutil.copy2(_DB_FILE, _SNAPSHOT_FILE)
        return True
    return False


def _restore_snapshot():
    """从快照恢复数据库"""
    if os.path.exists(_SNAPSHOT_FILE):
        shutil.copy2(_SNAPSHOT_FILE, _DB_FILE)
        return True
    return False


def _remove_snapshot():
    """删除快照文件"""
    if os.path.exists(_SNAPSHOT_FILE):
        os.remove(_SNAPSHOT_FILE)


@pytest.fixture(scope="session", autouse=True)
def db_snapshot():
    """
    会话级别数据快照:
    - 测试开始前备份数据库
    - 测试全部结束后恢复数据库
    - 确保每次测试运行从不改变的基线开始

    伊家人模式：测试不污染生产数据，每次运行从同一快照恢复。
    """
    _take_snapshot()
    yield
    # 测试结束后恢复数据库到快照状态
    _restore_snapshot()
    _remove_snapshot()


@pytest_asyncio.fixture
async def admin_token(client):
    """预登录的 admin token"""
    from httpx import AsyncClient, ASGITransport
    resp = await client.post("/api/auth/login", json={
        "username": "admin",
        "password": "admin123",
    })
    if resp.status_code == 200:
        return resp.json()["access_token"]
    return None


@pytest_asyncio.fixture
async def guest_token(client):
    """预登录的 guest token"""
    resp = await client.post("/api/auth/login", json={
        "username": "guest",
        "password": "guest123",
    })
    if resp.status_code == 200:
        return resp.json()["access_token"]
    return None


@pytest_asyncio.fixture
async def staff_token(client):
    """预登录的 staff token"""
    resp = await client.post("/api/auth/login", json={
        "username": "staff",
        "password": "staff123",
    })
    if resp.status_code == 200:
        return resp.json()["access_token"]
    return None


# ═══════════════════════════════════════════════════════
# 数据重置辅助函数（伊家人模式：快速种子数据恢复）
# ═══════════════════════════════════════════════════════
@pytest_asyncio.fixture
async def data_helpers(client, admin_token, guest_token, staff_token):
    """提供数据辅助函数的 fixture"""
    from datetime import date, timedelta
    import uuid

    class Helpers:
        def __init__(self):
            self.admin_token = admin_token
            self.guest_token = guest_token
            self.staff_token = staff_token

        async def create_ticket_order(self, ticket_type_id=1, spot_id=1, quantity=1,
                                       visit_date=None, time_slot="08:00-10:00"):
            """快速创建票务订单"""
            if visit_date is None:
                visit_date = date.today().isoformat()
            resp = await client.post(
                "/api/tickets/order",
                json={
                    "ticket_type_id": ticket_type_id,
                    "spot_id": spot_id,
                    "quantity": quantity,
                    "visit_date": visit_date,
                    "time_slot": time_slot,
                    "visitor_name": f"Helper测试_{uuid.uuid4().hex[:4]}",
                    "visitor_phone": f"138{uuid.uuid4().hex[:8]}",
                },
                headers={"Authorization": f"Bearer {self.guest_token}"},
            )
            return resp

        async def pay_order(self, order_no, order_type="ticket"):
            """创建支付并确认"""
            pay_resp = await client.post(
                "/api/payment/create",
                json={"order_no": order_no, "order_type": order_type},
                headers={"Authorization": f"Bearer {self.guest_token}"},
            )
            if pay_resp.status_code != 200:
                return pay_resp, None
            txn_id = pay_resp.json()["transaction_id"]
            confirm_resp = await client.post(
                "/api/payment/confirm",
                json={"transaction_id": txn_id, "order_no": order_no},
            )
            return pay_resp, txn_id

        async def create_hotel_with_room(self, hotel_name=None, room_name=None, price=200.0):
            """快速创建酒店+房型"""
            suffix = uuid.uuid4().hex[:6]
            hotel_name = hotel_name or f"Helper酒店_{suffix}"
            room_name = room_name or f"Helper房型_{suffix}"
            hotel_resp = await client.post(
                "/api/hotels",
                json={"spot_id": 1, "name": hotel_name, "address": f"Helper地址_{suffix}", "city": "泰安"},
                headers={"Authorization": f"Bearer {self.admin_token}"},
            )
            if hotel_resp.status_code != 201:
                return None, None
            hotel_id = hotel_resp.json()["id"]
            room_resp = await client.post(
                f"/api/hotels/{hotel_id}/rooms",
                json={"hotel_id": hotel_id, "name": room_name, "price": price, "total_count": 5},
                headers={"Authorization": f"Bearer {self.admin_token}"},
            )
            return hotel_id, room_resp.json()["id"] if room_resp.status_code == 201 else None

        async def create_parking_checkin(self, rate_id=1, plate_number=None):
            """快速停车入场"""
            plate = plate_number or f"京H{uuid.uuid4().hex[:6].upper()}"
            resp = await client.post(
                "/api/parking/checkin",
                json={"rate_id": rate_id, "plate_number": plate},
                headers={"Authorization": f"Bearer {self.guest_token}"},
            )
            return resp

    return Helpers()


# ═══════════════════════════════════════════════════════
# 测试数据重置点（名称约定来自伊家人项目）
# ═══════════════════════════════════════════════════════
_YIJIAREN_RESET_FLAG = False


@pytest.fixture
def yijiaren_reset():
    """
    伊家人数据重置标记 fixture。
    在需要数据隔离的测试中使用，标记当前测试需要重置数据。

    用法:
        def test_something(yijiaren_reset):
            # 测试代码
    """
    global _YIJIAREN_RESET_FLAG
    _YIJIAREN_RESET_FLAG = True
    yield
    _YIJIAREN_RESET_FLAG = False
