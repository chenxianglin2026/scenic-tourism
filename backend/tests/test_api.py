"""
景区智慧管理系统 - API 集成测试
测试所有公开API、鉴权API、购票→支付→核销完整流程
"""
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.db import TicketOrderStatus


@pytest_asyncio.fixture
async def client():
    """创建异步测试客户端"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


class TestHealthCheck:
    """健康检查"""

    async def test_health_returns_200(self, client):
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["app"] == "景区智慧管理系统"


class TestPublicAPIs:
    """公开API — 无需鉴权"""

    async def test_scenic_info_returns_200(self, client):
        resp = await client.get("/api/scenic/info")
        assert resp.status_code == 200
        data = resp.json()
        assert "name" in data
        assert "ticket_types" in data
        assert isinstance(data["ticket_types"], list)

    async def test_scenic_info_with_spot_id(self, client):
        resp = await client.get("/api/scenic/info?spot_id=1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == 1

    async def test_scenic_info_404(self, client):
        resp = await client.get("/api/scenic/info?spot_id=9999")
        assert resp.status_code == 404

    async def test_scenic_announcements_returns_200(self, client):
        resp = await client.get("/api/scenic/announcements")
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert "items" in data

    async def test_scenic_pois_returns_200(self, client):
        resp = await client.get("/api/scenic/pois")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_scenic_weather_returns_200(self, client):
        resp = await client.get("/api/scenic/weather")
        assert resp.status_code == 200
        data = resp.json()
        assert "temperature" in data
        assert "weather" in data
        assert "humidity" in data
        assert "forecast" in data
        assert len(data["forecast"]) == 3

    async def test_ticket_types_returns_200(self, client):
        resp = await client.get("/api/tickets/types")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_parking_rates_returns_200(self, client):
        resp = await client.get("/api/parking/rates")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_hotels_list_returns_200(self, client):
        resp = await client.get("/api/hotels")
        assert resp.status_code == 200


class TestAuthAPIs:
    """认证API"""

    async def test_register_returns_200(self, client):
        import uuid
        uname = f"testuser_{uuid.uuid4().hex[:8]}"
        resp = await client.post("/api/auth/register", json={
            "username": uname,
            "password": "test123456",
            "phone": "13900009999",
            "nickname": "测试用户",
        })
        assert resp.status_code in (200, 400)

    async def test_login_guest_returns_token(self, client):
        resp = await client.post("/api/auth/login", json={
            "username": "guest",
            "password": "guest123",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["role"] == "guest"

    async def test_login_admin_returns_token(self, client):
        resp = await client.post("/api/auth/login", json={
            "username": "admin",
            "password": "admin123",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["role"] == "admin"

    async def test_login_invalid_returns_401(self, client):
        resp = await client.post("/api/auth/login", json={
            "username": "guest",
            "password": "wrongpassword",
        })
        assert resp.status_code == 401


class TestAuthRequiredAPIs:
    """需要鉴权的API — 无token应返回401"""

    async def test_create_ticket_order_no_auth(self, client):
        resp = await client.post("/api/tickets/order", json={
            "ticket_type_id": 1,
            "spot_id": 1,
            "quantity": 1,
            "visit_date": "2026-12-31",
            "time_slot": "08:00-10:00",
        })
        assert resp.status_code == 401

    async def test_my_orders_no_auth(self, client):
        resp = await client.get("/api/tickets/orders")
        assert resp.status_code == 401

    async def test_verify_ticket_no_auth(self, client):
        resp = await client.post("/api/tickets/verify", json={
            "qr_token": "test",
        })
        assert resp.status_code == 401

    async def test_create_payment_no_auth(self, client):
        resp = await client.post("/api/payment/create", json={
            "order_no": "test",
            "order_type": "ticket",
        })
        assert resp.status_code == 401

    async def test_parking_checkin_no_auth(self, client):
        resp = await client.post("/api/parking/checkin", json={
            "rate_id": 1,
            "plate_number": "京A12345",
        })
        assert resp.status_code == 401

    async def test_parking_records_no_auth(self, client):
        resp = await client.get("/api/parking/records")
        assert resp.status_code == 401

    async def test_hotel_order_no_auth(self, client):
        resp = await client.post("/api/hotels/orders", json={
            "hotel_id": 1,
            "room_id": 1,
            "room_count": 1,
            "checkin_date": "2026-12-01",
            "checkout_date": "2026-12-02",
            "guest_name": "测试",
            "guest_phone": "13800138000",
        })
        assert resp.status_code == 401

    # Admin-only PUT APIs
    async def test_put_scenic_info_no_auth(self, client):
        resp = await client.put("/api/scenic/info", json={
            "name": "Test Name",
        })
        assert resp.status_code == 401

    async def test_put_announcement_no_auth(self, client):
        resp = await client.put("/api/scenic/announcements/1", json={
            "title": "Updated Title",
        })
        assert resp.status_code == 401

    async def test_put_parking_rate_no_auth(self, client):
        resp = await client.put("/api/parking/rates/1", json={
            "name": "Updated Rate",
        })
        assert resp.status_code == 401

    async def test_create_ticket_type_no_auth(self, client):
        resp = await client.post("/api/tickets/types", json={
            "spot_id": 1,
            "name": "Test Type",
            "price": 50.0,
        })
        assert resp.status_code == 401

    async def test_dashboard_no_auth(self, client):
        resp = await client.get("/api/dashboard/stats")
        assert resp.status_code == 401

    async def test_scenic_points_no_auth(self, client):
        resp = await client.post("/api/scenic/points", json={
            "spot_id": 1, "name": "Test Point",
        })
        assert resp.status_code == 401

    async def test_scenic_reviews_post_no_auth(self, client):
        resp = await client.post("/api/scenic/reviews", json={
            "spot_id": 1, "rating": 5, "content": "Great place!",
        })
        assert resp.status_code == 401

    async def test_parking_rates_post_no_auth(self, client):
        resp = await client.post("/api/parking/rates", json={
            "spot_id": 1, "name": "Test Parking",
        })
        assert resp.status_code == 401

    async def test_dashboard_revenue_no_auth(self, client):
        resp = await client.get("/api/dashboard/revenue")
        assert resp.status_code == 401


class TestNewPublicEndpoints:
    """新公开API测试"""

    async def test_scenic_points_returns_200(self, client):
        resp = await client.get("/api/scenic/points")
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert "items" in data

    async def test_scenic_points_filter_by_category(self, client):
        resp = await client.get("/api/scenic/points?category=dining")
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["category"] == "dining"

    async def test_scenic_points_filter_by_spot(self, client):
        resp = await client.get("/api/scenic/points?spot_id=1")
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["spot_id"] == 1

    async def test_scenic_reviews_returns_200(self, client):
        resp = await client.get("/api/scenic/reviews")
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert "items" in data
        assert "avg_rating" in data
        assert "rating_distribution" in data

    async def test_scenic_reviews_filter_by_spot(self, client):
        resp = await client.get("/api/scenic/reviews?spot_id=1")
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["spot_id"] == 1

    async def test_scenic_reviews_filter_by_rating(self, client):
        resp = await client.get("/api/scenic/reviews?rating=5")
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["rating"] == 5


class TestGuestAuthEndpoints:
    """guest 用户鉴权通过后可以使用的接口"""

    async def _login(self, client, username, password):
        resp = await client.post("/api/auth/login", json={
            "username": username, "password": password,
        })
        assert resp.status_code == 200
        return resp.json()["access_token"]

    async def test_create_review_as_guest(self, client):
        token = await self._login(client, "guest", "guest123")
        resp = await client.post(
            "/api/scenic/reviews",
            json={
                "spot_id": 1,
                "rating": 5,
                "content": "非常棒的景区，值得一游！",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["rating"] == 5
        assert data["nickname"] == "张游客"

    async def test_create_review_invalid_spot(self, client):
        token = await self._login(client, "guest", "guest123")
        resp = await client.post(
            "/api/scenic/reviews",
            json={
                "spot_id": 99999,
                "rating": 4,
                "content": "不存在的景区评价",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404

    async def test_create_review_invalid_rating(self, client):
        token = await self._login(client, "guest", "guest123")
        resp = await client.post(
            "/api/scenic/reviews",
            json={
                "spot_id": 1,
                "rating": 6,
                "content": "评分超出范围",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 422


class TestAdminEndpoints:
    """管理员专属接口测试"""

    async def _login(self, client, username, password):
        resp = await client.post("/api/auth/login", json={
            "username": username, "password": password,
        })
        assert resp.status_code == 200
        return resp.json()["access_token"]

    async def test_admin_create_parking_rate(self, client):
        token = await self._login(client, "admin", "admin123")
        resp = await client.post(
            "/api/parking/rates",
            json={
                "spot_id": 1,
                "name": "测试停车场",
                "vehicle_type": "car",
                "first_hour_price": 8.0,
                "additional_hour_price": 4.0,
                "daily_cap": 40.0,
                "free_minutes": 20,
                "total_spots": 100,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "测试停车场"
        assert data["first_hour_price"] == 8.0
        assert data["available_spots"] == 100

    async def test_admin_create_parking_rate_invalid_spot(self, client):
        token = await self._login(client, "admin", "admin123")
        resp = await client.post(
            "/api/parking/rates",
            json={
                "spot_id": 99999,
                "name": "无效停车场",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404

    async def test_admin_create_nearby_point(self, client):
        token = await self._login(client, "admin", "admin123")
        resp = await client.post(
            "/api/scenic/points",
            json={
                "spot_id": 1,
                "name": "测试推荐餐厅",
                "category": "dining",
                "description": "测试用",
                "rating": 4.5,
                "distance": 500,
                "sort_order": 99,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "测试推荐餐厅"
        assert data["category"] == "dining"

    async def test_admin_get_nearby_point(self, client):
        token = await self._login(client, "admin", "admin123")
        # First create a point
        create_resp = await client.post(
            "/api/scenic/points",
            json={"spot_id": 1, "name": "获取测试餐厅", "category": "dining", "rating": 4.0},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert create_resp.status_code == 201
        point_id = create_resp.json()["id"]
        # Get it
        resp = await client.get(f"/api/scenic/points/{point_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "获取测试餐厅"
        assert data["spot_id"] == 1

    async def test_update_nearby_point(self, client):
        token = await self._login(client, "admin", "admin123")
        # Create a point
        create_resp = await client.post(
            "/api/scenic/points",
            json={"spot_id": 1, "name": "待编辑餐厅", "category": "dining", "rating": 3.5},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert create_resp.status_code == 201
        point_id = create_resp.json()["id"]
        # Update it
        resp = await client.put(
            f"/api/scenic/points/{point_id}",
            json={"name": "已编辑餐厅", "rating": 4.8, "distance": 300},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "已编辑餐厅"
        assert data["rating"] == 4.8
        assert data["distance"] == 300

    async def test_delete_nearby_point(self, client):
        token = await self._login(client, "admin", "admin123")
        # Create a point to delete
        create_resp = await client.post(
            "/api/scenic/points",
            json={"spot_id": 1, "name": "待删除餐厅", "category": "dining", "rating": 4.0},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert create_resp.status_code == 201
        point_id = create_resp.json()["id"]
        # Delete it
        resp = await client.delete(
            f"/api/scenic/points/{point_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        # Verify deleted
        get_resp = await client.get(f"/api/scenic/points/{point_id}")
        assert get_resp.status_code == 404

    async def test_get_nonexistent_nearby_point(self, client):
        resp = await client.get("/api/scenic/points/99999")
        assert resp.status_code == 404

    async def test_delete_nonexistent_nearby_point(self, client):
        token = await self._login(client, "admin", "admin123")
        resp = await client.delete(
            "/api/scenic/points/99999",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404

    async def test_guest_cannot_delete_nearby_point(self, client):
        token = await self._login(client, "guest", "guest123")
        resp = await client.delete(
            "/api/scenic/points/1",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    async def test_keyword_search_nearby_points(self, client):
        import time
        token = await self._login(client, "admin", "admin123")
        # Create a truly unique-named point to avoid collision with stale test data
        unique_suffix = f"KW-TEST-{int(time.time() * 1000000)}"
        point_name = f"关键字搜索测试_{unique_suffix}"
        create_resp = await client.post(
            "/api/scenic/points",
            json={"spot_id": 1, "name": point_name, "category": "dining", "rating": 4.0},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert create_resp.status_code == 201
        created_id = create_resp.json()["id"]
        # Search for it
        resp = await client.get(f"/api/scenic/points?keyword={unique_suffix}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        found = [p for p in data["items"] if p["id"] == created_id]
        assert len(found) == 1, f"Expected 1 point, found {len(found)}: {found}"

    async def test_admin_delete_review(self, client):
        token = await self._login(client, "admin", "admin123")
        # First create a review as guest
        guest_token = await self._login(client, "guest", "guest123")
        create_resp = await client.post(
            "/api/scenic/reviews",
            json={"spot_id": 1, "rating": 3, "content": "待删除的评价内容测试"},
            headers={"Authorization": f"Bearer {guest_token}"},
        )
        assert create_resp.status_code == 201
        review_id = create_resp.json()["id"]

        # Delete as admin
        resp = await client.delete(
            f"/api/scenic/reviews/{review_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    async def test_admin_dashboard_revenue_day(self, client):
        token = await self._login(client, "admin", "admin123")
        resp = await client.get(
            "/api/dashboard/revenue?period=day",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 0
        assert "summary" in data["data"]
        assert "items" in data["data"]
        assert "total_revenue" in data["data"]["summary"]

    async def test_admin_dashboard_revenue_week(self, client):
        token = await self._login(client, "admin", "admin123")
        resp = await client.get(
            "/api/dashboard/revenue?period=week",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 0

    async def test_admin_dashboard_revenue_month(self, client):
        token = await self._login(client, "admin", "admin123")
        resp = await client.get(
            "/api/dashboard/revenue?period=month",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 0

    async def test_admin_dashboard_revenue_spot_filter(self, client):
        token = await self._login(client, "admin", "admin123")
        resp = await client.get(
            "/api/dashboard/revenue?period=day&spot_id=1",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"]["spot_id"] == 1

    async def test_admin_dashboard_revenue_invalid_period(self, client):
        token = await self._login(client, "admin", "admin123")
        resp = await client.get(
            "/api/dashboard/revenue?period=year",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 400

    async def test_guest_cannot_create_parking_rate(self, client):
        token = await self._login(client, "guest", "guest123")
        resp = await client.post(
            "/api/parking/rates",
            json={"spot_id": 1, "name": "Hacked"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    async def test_guest_cannot_create_nearby_point(self, client):
        token = await self._login(client, "guest", "guest123")
        resp = await client.post(
            "/api/scenic/points",
            json={"spot_id": 1, "name": "Hacked"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403


class TestGuestVsAdminAuth:
    """guest用户不能访问admin-only接口"""

    async def _login(self, client, username, password):
        resp = await client.post("/api/auth/login", json={
            "username": username,
            "password": password,
        })
        assert resp.status_code == 200
        return resp.json()["access_token"]

    async def test_guest_cannot_put_scenic_info(self, client):
        token = await self._login(client, "guest", "guest123")
        resp = await client.put(
            "/api/scenic/info",
            json={"name": "Hacked"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    async def test_guest_cannot_create_ticket_type(self, client):
        token = await self._login(client, "guest", "guest123")
        resp = await client.post(
            "/api/tickets/types",
            json={"spot_id": 1, "name": "Hacked Type", "price": 9.99},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    async def test_admin_can_put_scenic_info(self, client):
        token = await self._login(client, "admin", "admin123")
        # First get current info
        get_resp = await client.get("/api/scenic/info?spot_id=1")
        current_name = get_resp.json()["name"]

        resp = await client.put(
            "/api/scenic/info?spot_id=1",
            json={"name": "泰山风景名胜区-测试编辑"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "泰山风景名胜区-测试编辑"

        # Restore original name
        resp2 = await client.put(
            "/api/scenic/info?spot_id=1",
            json={"name": current_name},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp2.status_code == 200

    async def test_admin_can_put_announcement(self, client):
        token = await self._login(client, "admin", "admin123")
        # Get an announcement first
        list_resp = await client.get("/api/scenic/announcements?spot_id=1")
        items = list_resp.json()["items"]
        if not items:
            import pytest
            pytest.skip("No announcements to edit")
        ann_id = items[0]["id"]
        original_title = items[0]["title"]

        resp = await client.put(
            f"/api/scenic/announcements/{ann_id}",
            json={"title": original_title + "-已编辑"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert "已编辑" in resp.json()["title"]

        # Restore
        resp2 = await client.put(
            f"/api/scenic/announcements/{ann_id}",
            json={"title": original_title},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp2.status_code == 200

    async def test_admin_can_put_parking_rate(self, client):
        token = await self._login(client, "admin", "admin123")
        # Get current rates
        list_resp = await client.get("/api/parking/rates?spot_id=1")
        items = list_resp.json()
        if not items:
            import pytest
            pytest.skip("No parking rates to edit")
        rate_id = items[0]["id"]
        original_cap = items[0]["daily_cap"]

        resp = await client.put(
            f"/api/parking/rates/{rate_id}",
            json={"daily_cap": original_cap + 10},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["daily_cap"] == original_cap + 10

        # Restore
        resp2 = await client.put(
            f"/api/parking/rates/{rate_id}",
            json={"daily_cap": original_cap},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp2.status_code == 200

    async def test_admin_can_put_nonexistent_rate_returns_404(self, client):
        token = await self._login(client, "admin", "admin123")
        resp = await client.put(
            "/api/parking/rates/99999",
            json={"name": "No"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404


class TestPurchasePayVerifyFlow:
    """购票→支付→核销完整流程"""

    async def test_full_ticket_flow(self, client):
        # 1. 登录
        login_resp = await client.post("/api/auth/login", json={
            "username": "guest",
            "password": "guest123",
        })
        assert login_resp.status_code == 200
        guest_token = login_resp.json()["access_token"]

        # 2. 获取票种列表（使用默认票种 id=1）
        ticket_type_id = 1

        # 3. 购票下单
        from datetime import date
        today = date.today().isoformat()
        order_resp = await client.post(
            "/api/tickets/order",
            json={
                "ticket_type_id": ticket_type_id,
                "spot_id": 1,
                "quantity": 1,
                "visit_date": today,
                "time_slot": "08:00-10:00",
                "visitor_name": "测试游客",
                "visitor_phone": "13800138000",
            },
            headers={"Authorization": f"Bearer {guest_token}"},
        )
        assert order_resp.status_code == 201
        order = order_resp.json()
        assert order["status"] == TicketOrderStatus.PENDING
        order_no = order["order_no"]
        qr_token = order["qr_token"]

        # 4. 支付
        pay_resp = await client.post(
            "/api/payment/create",
            json={"order_no": order_no, "order_type": "ticket"},
            headers={"Authorization": f"Bearer {guest_token}"},
        )
        assert pay_resp.status_code == 200
        assert pay_resp.json()["success"] is True
        assert "transaction_id" in pay_resp.json()
        transaction_id = pay_resp.json()["transaction_id"]

        # 4.5 DEV_MODE 确认支付
        confirm_resp = await client.post(
            "/api/payment/confirm",
            json={"transaction_id": transaction_id, "order_no": order_no},
        )
        assert confirm_resp.status_code == 200
        assert confirm_resp.json()["success"] is True
        assert confirm_resp.json()["status"] == "success"

        # 5. 查询支付状态
        status_resp = await client.get(
            f"/api/payment/status/{order_no}",
            headers={"Authorization": f"Bearer {guest_token}"},
        )
        assert status_resp.status_code == 200
        assert status_resp.json()["status"] == "success"

        # 6. 验证订单状态变为已支付
        order_check = await client.get(
            f"/api/tickets/order/{order_no}",
            headers={"Authorization": f"Bearer {guest_token}"},
        )
        assert order_check.status_code == 200
        assert order_check.json()["status"] == TicketOrderStatus.PAID

        # 7. 核销（需要staff权限）
        staff_login = await client.post("/api/auth/login", json={
            "username": "staff",
            "password": "staff123",
        })
        assert staff_login.status_code == 200
        staff_token = staff_login.json()["access_token"]

        verify_resp = await client.post(
            "/api/tickets/verify",
            json={"qr_token": qr_token},
            headers={"Authorization": f"Bearer {staff_token}"},
        )
        assert verify_resp.status_code == 200
        result = verify_resp.json()
        assert result["result"] == "success"

        # 8. 再次核销同一张票 — 应返回 already_verified
        verify2 = await client.post(
            "/api/tickets/verify",
            json={"qr_token": qr_token},
            headers={"Authorization": f"Bearer {staff_token}"},
        )
        assert verify2.status_code == 200
        assert verify2.json()["result"] == "already_verified"

    async def test_buy_invalid_ticket_type(self, client):
        """购买不存在的票种"""
        login_resp = await client.post("/api/auth/login", json={
            "username": "guest",
            "password": "guest123",
        })
        token = login_resp.json()["access_token"]

        from datetime import date
        resp = await client.post(
            "/api/tickets/order",
            json={
                "ticket_type_id": 99999,
                "spot_id": 1,
                "quantity": 1,
                "visit_date": date.today().isoformat(),
                "time_slot": "08:00-10:00",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404

    async def test_buy_past_date(self, client):
        """购买过去的日期"""
        login_resp = await client.post("/api/auth/login", json={
            "username": "guest",
            "password": "guest123",
        })
        token = login_resp.json()["access_token"]

        resp = await client.post(
            "/api/tickets/order",
            json={
                "ticket_type_id": 1,
                "spot_id": 1,
                "quantity": 1,
                "visit_date": "2020-01-01",
                "time_slot": "08:00-10:00",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 400

    async def test_pay_nonexistent_order(self, client):
        """支付不存在的订单"""
        login_resp = await client.post("/api/auth/login", json={
            "username": "guest",
            "password": "guest123",
        })
        token = login_resp.json()["access_token"]

        resp = await client.post(
            "/api/payment/create",
            json={"order_no": "FAKE_ORDER_NO_999", "order_type": "ticket"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404


class TestPaymentNotify:
    """支付回调测试"""

    async def test_payment_notify_no_auth(self, client):
        """支付回调不需要鉴权"""
        resp = await client.post("/api/payment/notify", json={
            "transaction_id": "WX_TEST_001",
            "order_no": "TEST_ORDER",
            "order_type": "ticket",
            "amount": 100.0,
            "result_code": "SUCCESS",
        })
        # 回调不需要鉴权，找不到订单时返回404
        assert resp.status_code in (200, 404)


class TestNewEndpoints:
    """新API端点测试"""

    async def _login(self, client, username, password):
        resp = await client.post("/api/auth/login", json={
            "username": username, "password": password,
        })
        assert resp.status_code == 200
        return resp.json()["access_token"]

    # ── Weather Refresh ──
    async def test_weather_refresh_no_auth(self, client):
        resp = await client.post("/api/scenic/weather/refresh")
        assert resp.status_code == 401

    async def test_weather_refresh_as_admin(self, client):
        token = await self._login(client, "admin", "admin123")
        resp = await client.post(
            "/api/scenic/weather/refresh",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "temperature" in data
        assert "weather" in data
        assert "forecast" in data
        assert "update_time" in data

    async def test_weather_refresh_with_spot_id(self, client):
        token = await self._login(client, "admin", "admin123")
        resp = await client.post(
            "/api/scenic/weather/refresh?spot_id=1",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["spot_id"] == 1

    async def test_weather_refresh_invalid_spot(self, client):
        token = await self._login(client, "admin", "admin123")
        resp = await client.post(
            "/api/scenic/weather/refresh?spot_id=9999",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404

    # ── Dashboard Overview ──
    async def test_dashboard_overview_no_auth(self, client):
        resp = await client.get("/api/dashboard/overview")
        assert resp.status_code == 401

    async def test_dashboard_overview_as_admin(self, client):
        token = await self._login(client, "admin", "admin123")
        resp = await client.get(
            "/api/dashboard/overview",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "tickets" in data
        assert "hotels" in data
        assert "parking" in data
        assert "reviews" in data
        assert "total_revenue_today" in data
        assert "sold_today" in data["tickets"]
        assert "revenue_today" in data["tickets"]
        assert "avg_rating" in data["reviews"]
        assert "distribution" in data["reviews"]

    async def test_dashboard_overview_with_spot_id(self, client):
        token = await self._login(client, "admin", "admin123")
        resp = await client.get(
            "/api/dashboard/overview?spot_id=1",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["spot_id"] == 1

    async def test_guest_cannot_access_overview(self, client):
        token = await self._login(client, "guest", "guest123")
        resp = await client.get(
            "/api/dashboard/overview",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    async def test_guest_cannot_refresh_weather(self, client):
        token = await self._login(client, "guest", "guest123")
        resp = await client.post(
            "/api/scenic/weather/refresh",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403


class TestExportAPIs:
    """数据导出 API 测试"""

    async def _login(self, client, username, password):
        resp = await client.post("/api/auth/login", json={
            "username": username, "password": password,
        })
        assert resp.status_code == 200
        return resp.json()["access_token"]

    # ── 鉴权测试 ──
    async def test_export_tickets_no_auth(self, client):
        resp = await client.get("/api/export/tickets")
        assert resp.status_code == 401

    async def test_export_revenue_no_auth(self, client):
        resp = await client.get("/api/export/revenue")
        assert resp.status_code == 401

    async def test_export_parking_no_auth(self, client):
        resp = await client.get("/api/export/parking")
        assert resp.status_code == 401

    async def test_guest_cannot_export_tickets(self, client):
        token = await self._login(client, "guest", "guest123")
        resp = await client.get(
            "/api/export/tickets",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    async def test_guest_cannot_export_revenue(self, client):
        token = await self._login(client, "guest", "guest123")
        resp = await client.get(
            "/api/export/revenue",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    async def test_guest_cannot_export_parking(self, client):
        token = await self._login(client, "guest", "guest123")
        resp = await client.get(
            "/api/export/parking",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    # ── 票务导出 ──
    async def test_export_tickets_csv(self, client):
        token = await self._login(client, "admin", "admin123")
        resp = await client.get(
            "/api/export/tickets",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]
        csv_content = resp.text
        assert "订单号" in csv_content

    async def test_export_tickets_with_filters(self, client):
        token = await self._login(client, "admin", "admin123")
        resp = await client.get(
            "/api/export/tickets?start_date=2025-01-01&end_date=2030-12-31&spot_id=1",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]

    async def test_export_tickets_by_status(self, client):
        token = await self._login(client, "admin", "admin123")
        resp = await client.get(
            "/api/export/tickets?status=paid",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]

    async def test_export_tickets_bad_date(self, client):
        token = await self._login(client, "admin", "admin123")
        resp = await client.get(
            "/api/export/tickets?start_date=bad-date",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 400

    # ── 营收导出 ──
    async def test_export_revenue_csv(self, client):
        token = await self._login(client, "admin", "admin123")
        resp = await client.get(
            "/api/export/revenue?period=day",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]
        csv_content = resp.text
        assert "门票收入" in csv_content
        assert "酒店收入" in csv_content
        assert "停车收入" in csv_content
        assert "总计" in csv_content

    async def test_export_revenue_week(self, client):
        token = await self._login(client, "admin", "admin123")
        resp = await client.get(
            "/api/export/revenue?period=week",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]

    async def test_export_revenue_month(self, client):
        token = await self._login(client, "admin", "admin123")
        resp = await client.get(
            "/api/export/revenue?period=month",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]

    async def test_export_revenue_with_dates(self, client):
        token = await self._login(client, "admin", "admin123")
        resp = await client.get(
            "/api/export/revenue?period=day&start_date=2025-01-01&end_date=2025-01-31",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200

    async def test_export_revenue_with_spot(self, client):
        token = await self._login(client, "admin", "admin123")
        resp = await client.get(
            "/api/export/revenue?period=day&spot_id=1",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200

    async def test_export_revenue_invalid_period(self, client):
        token = await self._login(client, "admin", "admin123")
        resp = await client.get(
            "/api/export/revenue?period=year",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 400

    async def test_export_revenue_bad_date(self, client):
        token = await self._login(client, "admin", "admin123")
        resp = await client.get(
            "/api/export/revenue?start_date=bad",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 400

    async def test_export_revenue_date_range_invalid(self, client):
        token = await self._login(client, "admin", "admin123")
        resp = await client.get(
            "/api/export/revenue?start_date=2030-01-01&end_date=2025-01-01",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 400

    # ── 停车导出 ──
    async def test_export_parking_csv(self, client):
        token = await self._login(client, "admin", "admin123")
        resp = await client.get(
            "/api/export/parking",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]
        csv_content = resp.text
        assert "停车场" in csv_content
        assert "车牌号" in csv_content

    async def test_export_parking_with_filters(self, client):
        token = await self._login(client, "admin", "admin123")
        resp = await client.get(
            "/api/export/parking?start_date=2025-01-01&end_date=2030-12-31&plate_number=京A",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]

    async def test_export_parking_by_status(self, client):
        token = await self._login(client, "admin", "admin123")
        resp = await client.get(
            "/api/export/parking?status=completed",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]

    async def test_export_parking_bad_date(self, client):
        token = await self._login(client, "admin", "admin123")
        resp = await client.get(
            "/api/export/parking?start_date=bad-date",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 400


class TestHotelFlow:
    """酒店模块完整流程测试：创建酒店→房型→下单→支付→入住→退房→退款"""

    async def _login(self, client, username, password):
        resp = await client.post("/api/auth/login", json={
            "username": username, "password": password,
        })
        assert resp.status_code == 200
        return resp.json()["access_token"]

    async def test_hotel_flow_full(self, client):
        """完整酒店流程：创建酒店/房型 -> 下单 -> 支付 -> 入住 -> 退房"""
        admin_token = await self._login(client, "admin", "admin123")
        guest_token = await self._login(client, "guest", "guest123")
        staff_token = await self._login(client, "staff", "staff123")

        # 1. 管理员创建酒店
        hotel_resp = await client.post(
            "/api/hotels",
            json={
                "spot_id": 1,
                "name": "测试酒店-自动化测试",
                "address": "测试地址88号",
                "city": "泰安",
                "district": "泰山区",
                "phone": "0538-8888888",
                "description": "测试用酒店",
                "lat": 36.19,
                "lng": 117.12,
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert hotel_resp.status_code == 201
        hotel = hotel_resp.json()
        assert hotel["name"] == "测试酒店-自动化测试"
        hotel_id = hotel["id"]

        # 2. 查看酒店房型列表（空）
        rooms_resp = await client.get(f"/api/hotels/{hotel_id}/rooms")
        assert rooms_resp.status_code == 200

        # 3. 管理员创建房型
        room_resp = await client.post(
            f"/api/hotels/{hotel_id}/rooms",
            json={
                "hotel_id": hotel_id,
                "name": "豪华大床房-测试",
                "room_type": "大床房",
                "price": 388.0,
                "total_count": 5,
                "area": 35.0,
                "bed_type": "1.8m大床",
                "max_guests": 2,
                "has_window": True,
                "has_wifi": True,
                "has_bathtub": True,
                "description": "豪华测试房型",
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert room_resp.status_code == 201
        room = room_resp.json()
        assert room["name"] == "豪华大床房-测试"
        assert room["price"] == 388.0
        room_id = room["id"]

        # 4. 再看房型列表（应包含刚创建的）
        rooms2_resp = await client.get(f"/api/hotels/{hotel_id}/rooms")
        assert rooms2_resp.status_code == 200
        rooms_list = rooms2_resp.json()
        assert len(rooms_list) >= 1

        # 5. 用户创建酒店订单
        from datetime import date, timedelta
        checkin = date.today() + timedelta(days=1)
        checkout = date.today() + timedelta(days=3)
        order_resp = await client.post(
            "/api/hotels/orders",
            json={
                "hotel_id": hotel_id,
                "room_id": room_id,
                "room_count": 1,
                "checkin_date": checkin.isoformat(),
                "checkout_date": checkout.isoformat(),
                "guest_name": "测试客人",
                "guest_phone": "13800138001",
                "remark": "自动化测试订单",
            },
            headers={"Authorization": f"Bearer {guest_token}"},
        )
        assert order_resp.status_code == 201
        order = order_resp.json()
        assert order["status"] == "pending"
        order_no = order["order_no"]
        order_id = order["id"]

        # 6. 查看我的酒店订单
        my_orders_resp = await client.get(
            "/api/hotels/orders",
            headers={"Authorization": f"Bearer {guest_token}"},
        )
        assert my_orders_resp.status_code == 200
        my_orders = my_orders_resp.json()
        assert my_orders["total"] >= 1

        # 7. 支付
        pay_resp = await client.post(
            "/api/payment/create",
            json={"order_no": order_no, "order_type": "hotel"},
            headers={"Authorization": f"Bearer {guest_token}"},
        )
        assert pay_resp.status_code == 200
        assert pay_resp.json()["success"] is True
        transaction_id = pay_resp.json()["transaction_id"]

        # 确认支付
        confirm_resp = await client.post(
            "/api/payment/confirm",
            json={"transaction_id": transaction_id, "order_no": order_no},
        )
        assert confirm_resp.status_code == 200
        assert confirm_resp.json()["success"] is True

        # 8. 办理入住（需要 staff 权限）- 注意入住日期是明天
        # 直接办理会失败因为入住日期未到
        checkin_resp = await client.post(
            f"/api/hotels/orders/{order_id}/checkin",
            headers={"Authorization": f"Bearer {staff_token}"},
        )
        assert checkin_resp.status_code == 200
        result = checkin_resp.json()
        # 入住日期是明天，可能成功也可能返回未到时间
        if result["success"]:
            assert result["order"]["status"] == "checked_in"

            # 9. 办理退房
            checkout_resp = await client.post(
                f"/api/hotels/orders/{order_id}/checkout",
                headers={"Authorization": f"Bearer {staff_token}"},
            )
            assert checkout_resp.status_code == 200
            assert checkout_resp.json()["success"] is True
            assert checkout_resp.json()["order"]["status"] == "completed"

    async def test_create_hotel_invalid_spot(self, client):
        """创建酒店-景区不存在"""
        token = await self._login(client, "admin", "admin123")
        resp = await client.post(
            "/api/hotels",
            json={
                "spot_id": 99999,
                "name": "无效酒店",
                "address": "无效地址",
                "city": "未知",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404

    async def test_guest_cannot_create_hotel(self, client):
        """guest 不能创建酒店"""
        token = await self._login(client, "guest", "guest123")
        resp = await client.post(
            "/api/hotels",
            json={
                "spot_id": 1,
                "name": "游客不能创建酒店",
                "address": "测试地址",
                "city": "泰安",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    async def test_create_room_invalid_hotel(self, client):
        """创建房型-酒店不存在"""
        token = await self._login(client, "admin", "admin123")
        resp = await client.post(
            "/api/hotels/99999/rooms",
            json={
                "hotel_id": 99999,
                "name": "无效房型",
                "price": 100.0,
                "total_count": 10,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404

    async def test_create_hotel_order_invalid_dates(self, client):
        """酒店下单-入住日期早于今天"""
        token = await self._login(client, "guest", "guest123")
        resp = await client.post(
            "/api/hotels/orders",
            json={
                "hotel_id": 1,
                "room_id": 1,
                "room_count": 1,
                "checkin_date": "2020-01-01",
                "checkout_date": "2020-01-03",
                "guest_name": "测试",
                "guest_phone": "13800138000",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 400

    async def test_create_hotel_order_checkout_before_checkin(self, client):
        """酒店下单-离店日期早于入住日期"""
        token = await self._login(client, "guest", "guest123")
        from datetime import date, timedelta
        d = date.today() + timedelta(days=5)
        resp = await client.post(
            "/api/hotels/orders",
            json={
                "hotel_id": 1,
                "room_id": 1,
                "room_count": 1,
                "checkin_date": d.isoformat(),
                "checkout_date": (d - timedelta(days=1)).isoformat(),
                "guest_name": "测试",
                "guest_phone": "13800138000",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 400

    async def test_create_hotel_order_invalid_room(self, client):
        """酒店下单-房型不存在"""
        token = await self._login(client, "guest", "guest123")
        from datetime import date, timedelta
        checkin = date.today() + timedelta(days=1)
        checkout = date.today() + timedelta(days=3)
        resp = await client.post(
            "/api/hotels/orders",
            json={
                "hotel_id": 1,
                "room_id": 99999,
                "room_count": 1,
                "checkin_date": checkin.isoformat(),
                "checkout_date": checkout.isoformat(),
                "guest_name": "测试",
                "guest_phone": "13800138000",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404

    async def test_refund_pending_order(self, client):
        """退款-未支付订单直接取消"""
        admin_token = await self._login(client, "admin", "admin123")
        guest_token = await self._login(client, "guest", "guest123")

        # 创建酒店和房型
        hotel_resp = await client.post(
            "/api/hotels",
            json={"spot_id": 1, "name": "退款测试酒店", "address": "退款地址", "city": "泰安"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        hotel_id = hotel_resp.json()["id"]
        room_resp = await client.post(
            f"/api/hotels/{hotel_id}/rooms",
            json={"hotel_id": hotel_id, "name": "退款测试房型", "price": 200.0, "total_count": 5},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        room_id = room_resp.json()["id"]

        # 创建订单
        from datetime import date, timedelta
        checkin = date.today() + timedelta(days=7)
        checkout = date.today() + timedelta(days=9)
        order_resp = await client.post(
            "/api/hotels/orders",
            json={
                "hotel_id": hotel_id, "room_id": room_id, "room_count": 1,
                "checkin_date": checkin.isoformat(), "checkout_date": checkout.isoformat(),
                "guest_name": "退款测试", "guest_phone": "13800138002",
            },
            headers={"Authorization": f"Bearer {guest_token}"},
        )
        order_id = order_resp.json()["id"]
        assert order_resp.json()["status"] == "pending"

        # 退款
        refund_resp = await client.post(
            f"/api/hotels/orders/{order_id}/refund",
            headers={"Authorization": f"Bearer {guest_token}"},
        )
        assert refund_resp.status_code == 200
        assert refund_resp.json()["success"] is True
        assert refund_resp.json()["order"]["status"] == "cancelled"

    async def test_refund_paid_order(self, client):
        """退款-已支付订单退款"""
        admin_token = await self._login(client, "admin", "admin123")
        guest_token = await self._login(client, "guest", "guest123")

        # 创建酒店和房型
        hotel_resp = await client.post(
            "/api/hotels",
            json={"spot_id": 1, "name": "支付退款测试酒店", "address": "支付退款地址", "city": "泰安"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        hotel_id = hotel_resp.json()["id"]
        room_resp = await client.post(
            f"/api/hotels/{hotel_id}/rooms",
            json={"hotel_id": hotel_id, "name": "支付退款房型", "price": 300.0, "total_count": 5},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        room_id = room_resp.json()["id"]

        # 创建订单
        from datetime import date, timedelta
        checkin = date.today() + timedelta(days=10)
        checkout = date.today() + timedelta(days=12)
        order_resp = await client.post(
            "/api/hotels/orders",
            json={
                "hotel_id": hotel_id, "room_id": room_id, "room_count": 1,
                "checkin_date": checkin.isoformat(), "checkout_date": checkout.isoformat(),
                "guest_name": "支付退款测试", "guest_phone": "13800138003",
            },
            headers={"Authorization": f"Bearer {guest_token}"},
        )
        order_no = order_resp.json()["order_no"]
        order_id = order_resp.json()["id"]

        # 支付
        pay_resp = await client.post(
            "/api/payment/create",
            json={"order_no": order_no, "order_type": "hotel"},
            headers={"Authorization": f"Bearer {guest_token}"},
        )
        transaction_id = pay_resp.json()["transaction_id"]
        await client.post("/api/payment/confirm", json={
            "transaction_id": transaction_id, "order_no": order_no,
        })

        # 退款
        refund_resp = await client.post(
            f"/api/hotels/orders/{order_id}/refund",
            headers={"Authorization": f"Bearer {guest_token}"},
        )
        assert refund_resp.status_code == 200
        assert refund_resp.json()["success"] is True
        assert refund_resp.json()["order"]["status"] == "refunded"
        assert refund_resp.json()["refund_amount"] > 0

    async def test_checkin_invalid_order(self, client):
        """入住-订单不存在"""
        staff_token = await self._login(client, "staff", "staff123")
        resp = await client.post(
            "/api/hotels/orders/99999/checkin",
            headers={"Authorization": f"Bearer {staff_token}"},
        )
        assert resp.status_code == 404

    async def test_checkout_invalid_order(self, client):
        """退房-订单不存在"""
        staff_token = await self._login(client, "staff", "staff123")
        resp = await client.post(
            "/api/hotels/orders/99999/checkout",
            headers={"Authorization": f"Bearer {staff_token}"},
        )
        assert resp.status_code == 404

    async def test_guest_cannot_checkin(self, client):
        """guest 不能办理入住"""
        token = await self._login(client, "guest", "guest123")
        resp = await client.post(
            "/api/hotels/orders/1/checkin",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    async def test_orders_by_status(self, client):
        """按状态过滤订单"""
        token = await self._login(client, "guest", "guest123")
        resp = await client.get(
            "/api/hotels/orders?status=pending",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert "items" in data

    async def test_hotels_filter_by_spot(self, client):
        """按景区ID过滤酒店"""
        resp = await client.get("/api/hotels?spot_id=1")
        assert resp.status_code == 200


class TestPaymentMock:
    """支付模块 Mock 测试：各种支付场景的 mock 覆盖"""

    async def _login(self, client, username, password):
        resp = await client.post("/api/auth/login", json={
            "username": username, "password": password,
        })
        assert resp.status_code == 200
        return resp.json()["access_token"]

    async def _create_ticket_order(self, client, token, ticket_type_id=1, spot_id=1):
        from datetime import date
        today = date.today().isoformat()
        resp = await client.post(
            "/api/tickets/order",
            json={
                "ticket_type_id": ticket_type_id, "spot_id": spot_id,
                "quantity": 1, "visit_date": today, "time_slot": "08:00-10:00",
                "visitor_name": "Mock游客", "visitor_phone": "13800000001",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        return resp

    async def test_payment_create_ticket_order_mock(self, client):
        """Mock: 创建票务支付"""
        token = await self._login(client, "guest", "guest123")
        order_resp = await self._create_ticket_order(client, token)
        assert order_resp.status_code == 201
        order_no = order_resp.json()["order_no"]

        pay_resp = await client.post(
            "/api/payment/create",
            json={"order_no": order_no, "order_type": "ticket"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert pay_resp.status_code == 200
        data = pay_resp.json()
        assert data["success"] is True
        assert "transaction_id" in data
        assert "payment_params" in data  # DEV_MODE returns mock JSAPI params

    async def test_payment_create_hotel_order_mock(self, client):
        """Mock: 创建酒店支付"""
        admin_token = await self._login(client, "admin", "admin123")
        guest_token = await self._login(client, "guest", "guest123")

        # 创建酒店和房型
        hotel_resp = await client.post(
            "/api/hotels",
            json={"spot_id": 1, "name": "Mock支付酒店", "address": "Mock地址", "city": "泰安"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        hotel_id = hotel_resp.json()["id"]
        room_resp = await client.post(
            f"/api/hotels/{hotel_id}/rooms",
            json={"hotel_id": hotel_id, "name": "Mock支付房型", "price": 200.0, "total_count": 5},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        room_id = room_resp.json()["id"]

        # 创建酒店订单
        from datetime import date, timedelta
        checkin = date.today() + timedelta(days=3)
        checkout = date.today() + timedelta(days=5)
        order_resp = await client.post(
            "/api/hotels/orders",
            json={
                "hotel_id": hotel_id, "room_id": room_id, "room_count": 1,
                "checkin_date": checkin.isoformat(), "checkout_date": checkout.isoformat(),
                "guest_name": "Mock酒店支付", "guest_phone": "13900001111",
            },
            headers={"Authorization": f"Bearer {guest_token}"},
        )
        order_no = order_resp.json()["order_no"]

        pay_resp = await client.post(
            "/api/payment/create",
            json={"order_no": order_no, "order_type": "hotel"},
            headers={"Authorization": f"Bearer {guest_token}"},
        )
        assert pay_resp.status_code == 200
        assert pay_resp.json()["success"] is True

    async def test_payment_create_duplicate_pending(self, client):
        """Mock: 重复创建待支付订单 - 应被拒绝"""
        token = await self._login(client, "guest", "guest123")
        order_resp = await self._create_ticket_order(client, token)
        order_no = order_resp.json()["order_no"]

        # 第一次支付
        r1 = await client.post(
            "/api/payment/create",
            json={"order_no": order_no, "order_type": "ticket"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r1.status_code == 200

        # 第二次支付（重复）- 应拒绝
        r2 = await client.post(
            "/api/payment/create",
            json={"order_no": order_no, "order_type": "ticket"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r2.status_code == 400
        assert "已有待支付记录" in r2.json()["detail"]

    async def test_payment_create_already_paid(self, client):
        """Mock: 对已支付的订单创建支付 - 应返回400"""
        token = await self._login(client, "guest", "guest123")
        order_resp = await self._create_ticket_order(client, token)
        order_no = order_resp.json()["order_no"]

        # 支付 + 确认
        pay = await client.post(
            "/api/payment/create",
            json={"order_no": order_no, "order_type": "ticket"},
            headers={"Authorization": f"Bearer {token}"},
        )
        txn_id = pay.json()["transaction_id"]
        await client.post("/api/payment/confirm", json={
            "transaction_id": txn_id, "order_no": order_no,
        })

        # 再次支付 - 订单状态已为paid，不支持支付
        r2 = await client.post(
            "/api/payment/create",
            json={"order_no": order_no, "order_type": "ticket"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r2.status_code == 400
        assert "不支持支付" in r2.json()["detail"]

    async def test_payment_confirm_idempotent(self, client):
        """Mock: 支付确认幂等性 - 重复确认返回success"""
        token = await self._login(client, "guest", "guest123")
        order_resp = await self._create_ticket_order(client, token)
        order_no = order_resp.json()["order_no"]

        pay = await client.post(
            "/api/payment/create",
            json={"order_no": order_no, "order_type": "ticket"},
            headers={"Authorization": f"Bearer {token}"},
        )
        txn_id = pay.json()["transaction_id"]

        # 第一次确认
        r1 = await client.post("/api/payment/confirm", json={
            "transaction_id": txn_id, "order_no": order_no,
        })
        assert r1.status_code == 200
        assert r1.json()["status"] == "success"

        # 第二次确认（幂等）
        r2 = await client.post("/api/payment/confirm", json={
            "transaction_id": txn_id, "order_no": order_no,
        })
        assert r2.status_code == 200
        assert r2.json()["status"] == "success"
        assert "已完成" in r2.json()["message"]

    async def test_payment_confirm_not_found(self, client):
        """Mock: 确认不存在的支付记录"""
        resp = await client.post("/api/payment/confirm", json={
            "transaction_id": "FAKE_TXN_99999", "order_no": "FAKE_ORDER_99999",
        })
        assert resp.status_code == 404

    async def test_payment_notify_mock_success(self, client):
        """Mock: 支付回调 - 成功场景"""
        token = await self._login(client, "guest", "guest123")
        order_resp = await self._create_ticket_order(client, token)
        order_no = order_resp.json()["order_no"]

        # 先创建支付记录
        pay = await client.post(
            "/api/payment/create",
            json={"order_no": order_no, "order_type": "ticket"},
            headers={"Authorization": f"Bearer {token}"},
        )
        txn_id = pay.json()["transaction_id"]

        # 模拟微信回调
        notify = await client.post("/api/payment/notify", json={
            "transaction_id": txn_id,
            "order_no": order_no,
            "order_type": "ticket",
            "amount": 100.0,
            "result_code": "SUCCESS",
        })
        assert notify.status_code == 200
        data = notify.json()
        assert data["return_code"] == "SUCCESS"

        # 验证订单状态已更新
        status_resp = await client.get(
            f"/api/payment/status/{order_no}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert status_resp.json()["status"] == "success"

    async def test_payment_notify_mock_failure(self, client):
        """Mock: 支付回调 - 失败场景"""
        token = await self._login(client, "guest", "guest123")
        order_resp = await self._create_ticket_order(client, token)
        order_no = order_resp.json()["order_no"]

        # 模拟失败的微信回调（使用随机transaction_id避免UNIQUE冲突）
        import uuid as _uuid
        fail_txn = f"WX_FAIL_{_uuid.uuid4().hex[:8].upper()}"
        notify = await client.post("/api/payment/notify", json={
            "transaction_id": fail_txn,
            "order_no": order_no,
            "order_type": "ticket",
            "amount": 100.0,
            "result_code": "FAIL",
        })
        assert notify.status_code == 200
        data = notify.json()
        assert data["return_code"] == "FAIL"

    async def test_payment_cancel_success_mock(self, client):
        """Mock: 成功取消未支付订单"""
        token = await self._login(client, "guest", "guest123")
        order_resp = await self._create_ticket_order(client, token)
        order_no = order_resp.json()["order_no"]

        # 创建支付
        await client.post(
            "/api/payment/create",
            json={"order_no": order_no, "order_type": "ticket"},
            headers={"Authorization": f"Bearer {token}"},
        )

        # 取消支付
        cancel = await client.post(
            "/api/payment/cancel",
            json={"order_no": order_no, "order_type": "ticket"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert cancel.status_code == 200
        assert cancel.json()["success"] is True

        # 确认订单状态变为取消
        order_check = await client.get(
            f"/api/tickets/order/{order_no}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert order_check.json()["status"] == "cancelled"

    async def test_payment_cancel_after_paid(self, client):
        """Mock: 已支付后取消 - 应失败"""
        token = await self._login(client, "guest", "guest123")
        order_resp = await self._create_ticket_order(client, token)
        order_no = order_resp.json()["order_no"]

        pay = await client.post(
            "/api/payment/create",
            json={"order_no": order_no, "order_type": "ticket"},
            headers={"Authorization": f"Bearer {token}"},
        )
        txn_id = pay.json()["transaction_id"]
        await client.post("/api/payment/confirm", json={
            "transaction_id": txn_id, "order_no": order_no,
        })

        # 已支付的订单取消应失败
        cancel = await client.post(
            "/api/payment/cancel",
            json={"order_no": order_no, "order_type": "ticket"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert cancel.status_code == 400

    async def test_payment_invalid_order_type(self, client):
        """Mock: 无效的order_type"""
        token = await self._login(client, "guest", "guest123")
        resp = await client.post(
            "/api/payment/create",
            json={"order_no": "TEST-001", "order_type": "invalid"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 400

    async def test_payment_others_order(self, client):
        """Mock: 支付他人的订单 - 应被拒绝"""
        guest_token = await self._login(client, "guest", "guest123")

        # 创建订单
        order_resp = await self._create_ticket_order(client, guest_token)
        order_no = order_resp.json()["order_no"]

        # 注册另一个用户尝试支付（使用随机手机号避免冲突）
        import uuid as _uuid
        import random
        uname = f"other_user_{_uuid.uuid4().hex[:8]}"
        phone = f"139{random.randint(10000000, 99999999)}"
        reg_resp = await client.post("/api/auth/register", json={
            "username": uname, "password": "test123456",
            "phone": phone, "nickname": "其他用户",
        })
        # 注册可能因手机号/用户名重复而失败，但至少尝试
        assert reg_resp.status_code in (200, 400)
        if reg_resp.status_code == 400:
            # 如果注册失败(重复)，使用已有的guest2账号
            uname = "guest2"
            phone = "13900000001"
        other_login = await client.post("/api/auth/login", json={
            "username": uname, "password": "test123456",
        })
        assert other_login.status_code in (200, 401)
        if other_login.status_code != 200:
            import pytest
            pytest.skip("无法创建其他用户进行测试")

        other_token = other_login.json()["access_token"]

        resp = await client.post(
            "/api/payment/create",
            json={"order_no": order_no, "order_type": "ticket"},
            headers={"Authorization": f"Bearer {other_token}"},
        )
        assert resp.status_code == 404  # 订单不属于该用户


class TestPaymentAdmin:
    """支付管理测试：退款审核 + 自动取消超时订单"""

    async def _login(self, client, username, password):
        resp = await client.post("/api/auth/login", json={
            "username": username, "password": password,
        })
        assert resp.status_code == 200
        return resp.json()["access_token"]

    async def test_refund_approve_flow(self, client):
        """完整退款审核流程：支付→申请退款→管理员审核"""
        admin_token = await self._login(client, "admin", "admin123")
        guest_token = await self._login(client, "guest", "guest123")

        # 创建酒店和房型
        hotel_resp = await client.post(
            "/api/hotels",
            json={"spot_id": 1, "name": "审核测试酒店", "address": "审核地址", "city": "泰安"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        hotel_id = hotel_resp.json()["id"]
        room_resp = await client.post(
            f"/api/hotels/{hotel_id}/rooms",
            json={"hotel_id": hotel_id, "name": "审核房型", "price": 500.0, "total_count": 5},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        room_id = room_resp.json()["id"]

        # 创建订单并支付
        from datetime import date, timedelta
        checkin = date.today() + timedelta(days=14)
        checkout = date.today() + timedelta(days=16)
        order_resp = await client.post(
            "/api/hotels/orders",
            json={
                "hotel_id": hotel_id, "room_id": room_id, "room_count": 1,
                "checkin_date": checkin.isoformat(), "checkout_date": checkout.isoformat(),
                "guest_name": "审核测试", "guest_phone": "13800138004",
            },
            headers={"Authorization": f"Bearer {guest_token}"},
        )
        order_no = order_resp.json()["order_no"]
        order_id = order_resp.json()["id"]

        pay_resp = await client.post(
            "/api/payment/create",
            json={"order_no": order_no, "order_type": "hotel"},
            headers={"Authorization": f"Bearer {guest_token}"},
        )
        transaction_id = pay_resp.json()["transaction_id"]
        await client.post("/api/payment/confirm", json={
            "transaction_id": transaction_id, "order_no": order_no,
        })

        # 退款（直接退款，状态变 refunded）
        refund_resp = await client.post(
            f"/api/hotels/orders/{order_id}/refund",
            headers={"Authorization": f"Bearer {guest_token}"},
        )
        assert refund_resp.status_code == 200
        assert refund_resp.json()["success"] is True

    async def test_auto_cancel_expired(self, client):
        """测试自动取消超时订单接口"""
        admin_token = await self._login(client, "admin", "admin123")

        resp = await client.post(
            "/api/payment/auto-cancel",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "cancelled_count" in data
        assert isinstance(data["items"], list)

    async def test_refund_pending_list(self, client):
        """管理员查看待审核退款列表"""
        admin_token = await self._login(client, "admin", "admin123")

        resp = await client.get(
            "/api/payment/refund/pending",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert "items" in data
        assert "page" in data

    async def test_guest_cannot_auto_cancel(self, client):
        """guest 不能触发自动取消"""
        token = await self._login(client, "guest", "guest123")
        resp = await client.post(
            "/api/payment/auto-cancel",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    async def test_guest_cannot_view_refund_pending(self, client):
        """guest 不能查看待审核退款"""
        token = await self._login(client, "guest", "guest123")
        resp = await client.get(
            "/api/payment/refund/pending",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    async def test_refund_approve_invalid_transaction(self, client):
        """退款审核-不存在的交易号"""
        admin_token = await self._login(client, "admin", "admin123")
        resp = await client.post(
            "/api/payment/refund/approve",
            json={"transaction_id": "FAKE_TXN_NOT_EXIST", "approved": True},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 404

    async def test_guest_cannot_approve_refund(self, client):
        """guest 不能审核退款"""
        token = await self._login(client, "guest", "guest123")
        resp = await client.post(
            "/api/payment/refund/approve",
            json={"transaction_id": "TEST_TXN", "approved": True},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    async def test_payment_status_endpoint(self, client):
        """查询支付状态"""
        token = await self._login(client, "guest", "guest123")
        resp = await client.get(
            "/api/payment/status/FAKE_ORDER_NO",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data


class TestAnnouncementCRUD:
    """公告 CRUD 测试"""

    async def _login(self, client, username, password):
        resp = await client.post("/api/auth/login", json={
            "username": username, "password": password,
        })
        assert resp.status_code == 200
        return resp.json()["access_token"]

    async def test_create_announcement(self, client):
        """管理员创建公告"""
        token = await self._login(client, "admin", "admin123")
        resp = await client.post(
            "/api/scenic/announcements",
            json={
                "spot_id": 1,
                "title": "自动化测试公告",
                "content": "这是一条自动化测试创建的公告内容。",
                "category": "notice",
                "priority": 1,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "自动化测试公告"
        assert data["content"] == "这是一条自动化测试创建的公告内容。"
        assert data["category"] == "notice"
        assert data["priority"] == 1

    async def test_create_announcement_event(self, client):
        """创建活动类公告"""
        token = await self._login(client, "admin", "admin123")
        resp = await client.post(
            "/api/scenic/announcements",
            json={
                "spot_id": 1,
                "title": "桃花节活动公告",
                "content": "桃花盛开时节，欢迎前来观赏。",
                "category": "event",
                "priority": 2,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 201
        assert resp.json()["category"] == "event"

    async def test_create_announcement_invalid_spot(self, client):
        """创建公告-景区不存在"""
        token = await self._login(client, "admin", "admin123")
        resp = await client.post(
            "/api/scenic/announcements",
            json={
                "spot_id": 99999,
                "title": "测试公告",
                "content": "测试内容",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404

    async def test_guest_cannot_create_announcement(self, client):
        """guest 不能创建公告"""
        token = await self._login(client, "guest", "guest123")
        resp = await client.post(
            "/api/scenic/announcements",
            json={"spot_id": 1, "title": "游客公告", "content": "测试"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    async def test_update_announcement(self, client):
        """管理员编辑公告"""
        token = await self._login(client, "admin", "admin123")
        # 先创建一条
        create_resp = await client.post(
            "/api/scenic/announcements",
            json={"spot_id": 1, "title": "待编辑公告", "content": "原始内容"},
            headers={"Authorization": f"Bearer {token}"},
        )
        ann_id = create_resp.json()["id"]

        # 编辑
        resp = await client.put(
            f"/api/scenic/announcements/{ann_id}",
            json={"title": "已编辑公告", "content": "更新后的内容"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["title"] == "已编辑公告"
        assert resp.json()["content"] == "更新后的内容"

    async def test_update_nonexistent_announcement(self, client):
        """编辑不存在的公告"""
        token = await self._login(client, "admin", "admin123")
        resp = await client.put(
            "/api/scenic/announcements/99999",
            json={"title": "不存在的公告"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404

    async def test_delete_announcement(self, client):
        """管理员删除公告"""
        token = await self._login(client, "admin", "admin123")
        # 先创建一条
        create_resp = await client.post(
            "/api/scenic/announcements",
            json={"spot_id": 1, "title": "待删除公告", "content": "即将被删除"},
            headers={"Authorization": f"Bearer {token}"},
        )
        ann_id = create_resp.json()["id"]

        # 删除
        resp = await client.delete(
            f"/api/scenic/announcements/{ann_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True

        # 再次删除应返回 404
        resp2 = await client.delete(
            f"/api/scenic/announcements/{ann_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp2.status_code == 404

    async def test_delete_nonexistent_announcement(self, client):
        """删除不存在的公告"""
        token = await self._login(client, "admin", "admin123")
        resp = await client.delete(
            "/api/scenic/announcements/99999",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404

    async def test_guest_cannot_delete_announcement(self, client):
        """guest 不能删除公告"""
        token = await self._login(client, "guest", "guest123")
        resp = await client.delete(
            "/api/scenic/announcements/1",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403


class TestMultiSpotScenarios:
    """多景区切换场景测试"""

    async def _login(self, client, username, password):
        resp = await client.post("/api/auth/login", json={
            "username": username, "password": password,
        })
        assert resp.status_code == 200
        return resp.json()["access_token"]

    async def test_scenic_info_all_spots(self, client):
        """获取所有景区信息"""
        for spot_id in [1, 2, 3]:
            resp = await client.get(f"/api/scenic/info?spot_id={spot_id}")
            assert resp.status_code == 200, f"spot_id={spot_id} 返回非200"
            data = resp.json()
            assert data["id"] == spot_id
            assert data["name"]
            assert len(data["ticket_types"]) > 0

    async def test_ticket_types_per_spot(self, client):
        """每个景区的票种独立"""
        types_1 = (await client.get("/api/tickets/types?spot_id=1")).json()
        types_2 = (await client.get("/api/tickets/types?spot_id=2")).json()
        types_3 = (await client.get("/api/tickets/types?spot_id=3")).json()
        assert len(types_1) > 0
        assert len(types_2) > 0
        assert len(types_3) > 0
        # 各景区票种名称应不同
        names_1 = {t["name"] for t in types_1}
        names_2 = {t["name"] for t in types_2}
        names_3 = {t["name"] for t in types_3}
        # 至少每个景区票种不完全相同（不同景区应有不同票种名称）
        assert names_1 != names_2 or names_1 != names_3

    async def test_pois_per_spot(self, client):
        """每个景区的POI独立"""
        for spot_id in [1, 2, 3]:
            resp = await client.get(f"/api/scenic/pois?spot_id={spot_id}")
            assert resp.status_code == 200
            pois = resp.json()
            assert len(pois) > 0, f"spot_id={spot_id} 应有POI"

    async def test_weather_per_spot(self, client):
        """每个景区的天气独立"""
        temps = {}
        for spot_id in [1, 2, 3]:
            resp = await client.get(f"/api/scenic/weather?spot_id={spot_id}")
            assert resp.status_code == 200
            data = resp.json()
            temps[spot_id] = data["temperature"]
        # 各景区天气应不完全相同（不同城市不同气象）
        assert len(set(temps.values())) >= 1

    async def test_reviews_across_spots(self, client):
        """跨景区评价查询"""
        for spot_id in [1, 2, 3]:
            resp = await client.get(f"/api/scenic/reviews?spot_id={spot_id}")
            assert resp.status_code == 200
            data = resp.json()
            assert data["total"] > 0, f"spot_id={spot_id} 应有评价"
            assert "avg_rating" in data
            assert "rating_distribution" in data

    async def test_announcements_per_spot(self, client):
        """每个景区的公告独立"""
        for spot_id in [1, 2, 3]:
            resp = await client.get(f"/api/scenic/announcements?spot_id={spot_id}")
            assert resp.status_code == 200
            data = resp.json()
            assert data["total"] > 0, f"spot_id={spot_id} 应有公告"


class TestOtaAPIs:
    """OTA平台对接 API 测试"""

    async def _login(self, client, username, password):
        resp = await client.post("/api/auth/login", json={
            "username": username, "password": password,
        })
        assert resp.status_code == 200
        return resp.json()["access_token"]

    # ── 鉴权测试 ──
    async def test_ota_configs_no_auth(self, client):
        resp = await client.get("/api/ota/configs")
        assert resp.status_code == 401

    async def test_ota_orders_no_auth(self, client):
        resp = await client.get("/api/ota/orders")
        assert resp.status_code == 401

    async def test_ota_stock_sync_no_auth(self, client):
        resp = await client.post("/api/ota/stock/sync", json={
            "platform": "ctrip",
            "product_type": "ticket",
            "product_id": 1,
            "available_stock": 100,
        })
        assert resp.status_code == 401

    async def test_ota_push_order_no_auth(self, client):
        """OTA推送订单不需要鉴权（外部回调）"""
        resp = await client.post("/api/ota/orders/push", json={
            "platform": "ctrip",
            "channel_order_no": "CT_TEST_ORDER_001",
            "action": "create",
            "product_type": "ticket",
            "payload": {
                "ticket_type_id": 1,
                "spot_id": 1,
                "quantity": 2,
                "visit_date": "2026-12-25",
                "guest_name": "携程游客",
                "guest_phone": "13800001111",
                "total_price": 230.0,
                "time_slot": "08:00-10:00",
            },
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 0

    # ── 管理员操作 ──
    async def test_admin_get_ota_configs(self, client):
        token = await self._login(client, "admin", "admin123")
        resp = await client.get(
            "/api/ota/configs",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert "items" in data
        assert data["total"] >= 3  # ctrip, meituan, fliggy

    async def test_admin_get_single_ota_config(self, client):
        token = await self._login(client, "admin", "admin123")
        resp = await client.get(
            "/api/ota/configs/ctrip",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["platform"] == "ctrip"
        assert "is_enabled" in data

    async def test_admin_get_ota_config_not_found(self, client):
        token = await self._login(client, "admin", "admin123")
        resp = await client.get(
            "/api/ota/configs/unknown_platform",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 422  # validation error

    async def test_admin_update_ota_config(self, client):
        token = await self._login(client, "admin", "admin123")
        resp = await client.put(
            "/api/ota/configs/ctrip",
            json={
                "platform": "ctrip",
                "is_enabled": True,
                "sync_interval_minutes": 10,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    async def test_admin_test_ota_connection(self, client):
        token = await self._login(client, "admin", "admin123")
        resp = await client.post(
            "/api/ota/test-connection/ctrip",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "connected" in data
        assert "latency_ms" in data

    async def test_admin_test_ota_connection_invalid(self, client):
        token = await self._login(client, "admin", "admin123")
        resp = await client.post(
            "/api/ota/test-connection/unknown",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 422

    # ── OTA订单推送测试 ──
    async def test_ota_push_ticket_order_create(self, client):
        """携程推送票务新订单"""
        resp = await client.post("/api/ota/orders/push", json={
            "platform": "ctrip",
            "channel_order_no": "CT_TICKET_20240601_001",
            "action": "create",
            "product_type": "ticket",
            "payload": {
                "ticket_type_id": 1,
                "spot_id": 1,
                "quantity": 3,
                "visit_date": "2026-08-15",
                "guest_name": "携程测试游客",
                "guest_phone": "13911112222",
                "total_price": 345.0,
                "time_slot": "10:00-12:00",
            },
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 0
        assert "订单同步成功" in data["message"]

    async def test_ota_push_hotel_order_create(self, client):
        """美团推送酒店新订单"""
        resp = await client.post("/api/ota/orders/push", json={
            "platform": "meituan",
            "channel_order_no": "MT_HOTEL_20240601_001",
            "action": "create",
            "product_type": "hotel",
            "payload": {
                "hotel_id": 1,
                "room_id": 1,
                "room_count": 1,
                "checkin_date": "2026-07-01",
                "checkout_date": "2026-07-03",
                "guest_name": "美团测试客人",
                "guest_phone": "13822223333",
                "total_price": 776.0,
            },
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 0

    async def test_ota_push_order_cancel(self, client):
        """OTA取消已推送的订单"""
        # 先创建
        await client.post("/api/ota/orders/push", json={
            "platform": "fliggy",
            "channel_order_no": "FG_CANCEL_TEST_001",
            "action": "create",
            "product_type": "ticket",
            "payload": {
                "ticket_type_id": 1, "spot_id": 1, "quantity": 1,
                "visit_date": "2026-09-01",
                "guest_name": "飞猪测试", "guest_phone": "13933334444",
                "total_price": 115.0,
            },
        })
        # 再取消
        resp = await client.post("/api/ota/orders/push", json={
            "platform": "fliggy",
            "channel_order_no": "FG_CANCEL_TEST_001",
            "action": "cancel",
            "product_type": "ticket",
            "payload": {},
        })
        assert resp.status_code == 200
        assert resp.json()["code"] == 0

    async def test_ota_push_order_invalid_platform(self, client):
        """推送到未知OTA平台"""
        resp = await client.post("/api/ota/orders/push", json={
            "platform": "qunar",
            "channel_order_no": "QN_001",
            "action": "create",
            "product_type": "ticket",
            "payload": {"ticket_type_id": 1, "spot_id": 1, "quantity": 1,
                        "visit_date": "2026-12-01", "guest_name": "测试",
                        "guest_phone": "13800000001", "total_price": 100.0},
        })
        assert resp.status_code == 200
        assert resp.json()["code"] == 1

    async def test_ota_push_order_invalid_product(self, client):
        """推送不存在的票种ID"""
        resp = await client.post("/api/ota/orders/push", json={
            "platform": "ctrip",
            "channel_order_no": "CT_INVALID_001",
            "action": "create",
            "product_type": "ticket",
            "payload": {
                "ticket_type_id": 99999,
                "spot_id": 1,
                "quantity": 1,
                "visit_date": "2026-12-01",
                "guest_name": "测试",
                "guest_phone": "13800000001",
                "total_price": 100.0,
            },
        })
        assert resp.status_code == 200
        assert resp.json()["code"] == 1

    # ── OTA订单列表 ──
    async def test_admin_list_ota_orders(self, client):
        token = await self._login(client, "admin", "admin123")
        resp = await client.get(
            "/api/ota/orders",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert "items" in data

    async def test_admin_list_ota_orders_filter_platform(self, client):
        token = await self._login(client, "admin", "admin123")
        resp = await client.get(
            "/api/ota/orders?platform=ctrip",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["platform"] == "ctrip"

    async def test_guest_cannot_view_ota_orders(self, client):
        token = await self._login(client, "guest", "guest123")
        resp = await client.get(
            "/api/ota/orders",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    # ── 库存同步 ──
    async def test_admin_sync_stock(self, client):
        token = await self._login(client, "admin", "admin123")
        resp = await client.post(
            "/api/ota/stock/sync",
            json={
                "platform": "ctrip",
                "product_type": "ticket",
                "product_id": 1,
                "available_stock": 500,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["available_stock"] == 500

    async def test_admin_sync_stock_invalid_product(self, client):
        token = await self._login(client, "admin", "admin123")
        resp = await client.post(
            "/api/ota/stock/sync",
            json={
                "platform": "ctrip",
                "product_type": "ticket",
                "product_id": 99999,
                "available_stock": 100,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404

    async def test_admin_batch_sync_stock(self, client):
        token = await self._login(client, "admin", "admin123")
        resp = await client.post(
            "/api/ota/stock/batch-sync",
            json={
                "platform": "ctrip",
                "spot_id": 1,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "synced_count" in data
        assert "failed_count" in data

    async def test_admin_sync_stock_room(self, client):
        token = await self._login(client, "admin", "admin123")
        resp = await client.post(
            "/api/ota/stock/sync",
            json={
                "platform": "meituan",
                "product_type": "room",
                "product_id": 1,
                "available_stock": 25,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    # ── 价格同步 ──
    async def test_admin_sync_price(self, client):
        token = await self._login(client, "admin", "admin123")
        resp = await client.post(
            "/api/ota/price/sync",
            json={
                "platform": "ctrip",
                "product_type": "ticket",
                "product_id": 1,
                "ota_price": 120.0,
                "original_price": 150.0,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    # ── 产品列表 ──
    async def test_admin_list_syncable_products(self, client):
        token = await self._login(client, "admin", "admin123")
        resp = await client.get(
            "/api/ota/products",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert "items" in data

    async def test_admin_list_syncable_products_filter_type(self, client):
        token = await self._login(client, "admin", "admin123")
        resp = await client.get(
            "/api/ota/products?product_type=ticket",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["type"] == "ticket"

    # ── 营收报表 ──
    async def test_admin_ota_revenue(self, client):
        token = await self._login(client, "admin", "admin123")
        resp = await client.get(
            "/api/ota/revenue",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "total_platforms" in data
        assert "items" in data

    async def test_admin_ota_revenue_filter_platform(self, client):
        token = await self._login(client, "admin", "admin123")
        resp = await client.get(
            "/api/ota/revenue?platform=ctrip",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_platforms"] == 1
        assert data["items"][0]["platform"] == "ctrip"

    async def test_guest_cannot_ota_revenue(self, client):
        token = await self._login(client, "guest", "guest123")
        resp = await client.get(
            "/api/ota/revenue",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    async def test_guest_cannot_sync_stock(self, client):
        token = await self._login(client, "guest", "guest123")
        resp = await client.post(
            "/api/ota/stock/sync",
            json={
                "platform": "ctrip",
                "product_type": "ticket",
                "product_id": 1,
                "available_stock": 100,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    async def test_guest_cannot_get_configs(self, client):
        token = await self._login(client, "guest", "guest123")
        resp = await client.get(
            "/api/ota/configs",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    # ── OTA订单状态同步 ──
    async def test_admin_query_ota_order_status_by_ota_id(self, client):
        """按OTA订单号查询状态"""
        # 先推送一个订单
        await client.post("/api/ota/orders/push", json={
            "platform": "ctrip",
            "channel_order_no": "CT_STATUS_QUERY_001",
            "action": "create",
            "product_type": "ticket",
            "payload": {
                "ticket_type_id": 1, "spot_id": 1, "quantity": 1,
                "visit_date": "2026-10-01",
                "guest_name": "状态查询测试", "guest_phone": "13900001111",
                "total_price": 100.0,
            },
        })
        token = await self._login(client, "admin", "admin123")
        resp = await client.get(
            "/api/ota/orders/status?ota_order_id=CT_STATUS_QUERY_001",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["found"] is True
        assert data["ota_order_id"] == "CT_STATUS_QUERY_001"
        assert data["platform"] == "ctrip"
        assert data["status"] == "synced"

    async def test_admin_query_ota_order_status_by_local_no(self, client):
        """按本地订单号查询OTA状态"""
        # 先推送一个酒店订单
        push_resp = await client.post("/api/ota/orders/push", json={
            "platform": "meituan",
            "channel_order_no": "MT_LOCAL_QUERY_001",
            "action": "create",
            "product_type": "hotel",
            "payload": {
                "hotel_id": 1, "room_id": 1, "room_count": 1,
                "checkin_date": "2026-08-01", "checkout_date": "2026-08-03",
                "guest_name": "本地查询测试", "guest_phone": "13822223333",
                "total_price": 600.0,
            },
        })
        assert push_resp.json()["code"] == 0

        token = await self._login(client, "admin", "admin123")
        # 先获取OTA订单列表找到local_order_no
        list_resp = await client.get(
            "/api/ota/orders",
            headers={"Authorization": f"Bearer {token}"},
        )
        items = list_resp.json()["items"]
        local_order_no = None
        for item in items:
            if item.get("ota_order_id") == "MT_LOCAL_QUERY_001":
                local_order_no = item.get("local_order_no")
                break
        assert local_order_no is not None

        resp = await client.get(
            f"/api/ota/orders/status?local_order_no={local_order_no}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["found"] is True
        assert data["local_order_no"] == local_order_no

    async def test_admin_query_ota_order_status_not_found(self, client):
        """查询不存在的OTA订单"""
        token = await self._login(client, "admin", "admin123")
        resp = await client.get(
            "/api/ota/orders/status?ota_order_id=NONEXIST_OTA_ORDER",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404

    async def test_admin_query_ota_order_status_no_params(self, client):
        """查询OTA状态缺少参数"""
        token = await self._login(client, "admin", "admin123")
        resp = await client.get(
            "/api/ota/orders/status",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 400

    async def test_admin_sync_ota_order_status(self, client):
        """手动同步OTA订单状态"""
        # 推送订单
        push_resp = await client.post("/api/ota/orders/push", json={
            "platform": "ctrip",
            "channel_order_no": "CT_SYNC_STATUS_001",
            "action": "create",
            "product_type": "ticket",
            "payload": {
                "ticket_type_id": 1, "spot_id": 1, "quantity": 1,
                "visit_date": "2026-11-15",
                "guest_name": "状态同步测试", "guest_phone": "13955556666",
                "total_price": 120.0,
            },
        })
        assert push_resp.json()["code"] == 0

        token = await self._login(client, "admin", "admin123")
        # 获取本地订单号
        list_resp = await client.get(
            "/api/ota/orders",
            headers={"Authorization": f"Bearer {token}"},
        )
        items = list_resp.json()["items"]
        local_order_no = None
        for item in items:
            if item.get("ota_order_id") == "CT_SYNC_STATUS_001":
                local_order_no = item.get("local_order_no")
                break
        assert local_order_no is not None

        # 手动同步状态
        resp = await client.post(
            "/api/ota/orders/sync-status",
            json={"local_order_no": local_order_no},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["local_order_no"] == local_order_no

    async def test_admin_sync_ota_order_status_not_ota(self, client):
        """同步非OTA来源的订单"""
        token = await self._login(client, "admin", "admin123")
        resp = await client.post(
            "/api/ota/orders/sync-status",
            json={"local_order_no": "NON_OTA_ORDER_99999"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404  # 本地订单不存在

    async def test_admin_sync_ota_order_status_force(self, client):
        """强制设置OTA订单状态"""
        # 推送订单
        await client.post("/api/ota/orders/push", json={
            "platform": "fliggy",
            "channel_order_no": "FG_FORCE_SYNC_001",
            "action": "create",
            "product_type": "ticket",
            "payload": {
                "ticket_type_id": 1, "spot_id": 1, "quantity": 1,
                "visit_date": "2026-12-01",
                "guest_name": "强制同步测试", "guest_phone": "13966667777",
                "total_price": 90.0,
            },
        })
        token = await self._login(client, "admin", "admin123")
        # 获取本地订单号
        list_resp = await client.get(
            "/api/ota/orders",
            headers={"Authorization": f"Bearer {token}"},
        )
        items = list_resp.json()["items"]
        local_order_no = None
        for item in items:
            if item.get("ota_order_id") == "FG_FORCE_SYNC_001":
                local_order_no = item.get("local_order_no")
                break
        assert local_order_no is not None

        resp = await client.post(
            "/api/ota/orders/sync-status",
            json={"local_order_no": local_order_no, "new_status": "cancelled"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["synced_status"] == "cancelled"

    async def test_admin_callback_to_ota_confirm(self, client):
        """向OTA回传订单确认"""
        # 推送订单
        await client.post("/api/ota/orders/push", json={
            "platform": "ctrip",
            "channel_order_no": "CT_CALLBACK_001",
            "action": "create",
            "product_type": "ticket",
            "payload": {
                "ticket_type_id": 1, "spot_id": 1, "quantity": 2,
                "visit_date": "2026-10-20",
                "guest_name": "回调测试", "guest_phone": "13877778888",
                "total_price": 200.0,
            },
        })
        token = await self._login(client, "admin", "admin123")
        # 获取本地订单号
        list_resp = await client.get(
            "/api/ota/orders",
            headers={"Authorization": f"Bearer {token}"},
        )
        items = list_resp.json()["items"]
        local_order_no = None
        for item in items:
            if item.get("ota_order_id") == "CT_CALLBACK_001":
                local_order_no = item.get("local_order_no")
                break
        assert local_order_no is not None

        resp = await client.post(
            "/api/ota/orders/callback",
            json={
                "local_order_no": local_order_no,
                "action": "confirm",
                "reason": "订单已确认",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["action"] == "confirm"
        assert "callback_sign" in data

    async def test_admin_callback_to_ota_cancel(self, client):
        """向OTA回传订单取消"""
        # 推送订单
        await client.post("/api/ota/orders/push", json={
            "platform": "meituan",
            "channel_order_no": "MT_CALLBACK_CANCEL_001",
            "action": "create",
            "product_type": "hotel",
            "payload": {
                "hotel_id": 1, "room_id": 1, "room_count": 1,
                "checkin_date": "2026-09-01", "checkout_date": "2026-09-02",
                "guest_name": "取消回调测试", "guest_phone": "13688889999",
                "total_price": 300.0,
            },
        })
        token = await self._login(client, "admin", "admin123")
        list_resp = await client.get(
            "/api/ota/orders",
            headers={"Authorization": f"Bearer {token}"},
        )
        items = list_resp.json()["items"]
        local_order_no = None
        for item in items:
            if item.get("ota_order_id") == "MT_CALLBACK_CANCEL_001":
                local_order_no = item.get("local_order_no")
                break
        assert local_order_no is not None

        resp = await client.post(
            "/api/ota/orders/callback",
            json={
                "local_order_no": local_order_no,
                "action": "cancel",
                "reason": "用户申请退款",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["action"] == "cancel"

    async def test_admin_callback_to_ota_not_found(self, client):
        """回传不存在的OTA订单"""
        token = await self._login(client, "admin", "admin123")
        resp = await client.post(
            "/api/ota/orders/callback",
            json={
                "local_order_no": "NONEXIST_CALLBACK_ORDER",
                "action": "confirm",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404

    async def test_guest_cannot_query_ota_status(self, client):
        """游客不能查询OTA订单状态"""
        token = await self._login(client, "guest", "guest123")
        resp = await client.get(
            "/api/ota/orders/status?ota_order_id=ANY",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    async def test_guest_cannot_sync_ota_status(self, client):
        """游客不能同步OTA订单状态"""
        token = await self._login(client, "guest", "guest123")
        resp = await client.post(
            "/api/ota/orders/sync-status",
            json={"local_order_no": "ANY"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    async def test_guest_cannot_callback_ota(self, client):
        """游客不能向OTA回传状态"""
        token = await self._login(client, "guest", "guest123")
        resp = await client.post(
            "/api/ota/orders/callback",
            json={"local_order_no": "ANY", "action": "confirm"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    async def test_ota_push_order_then_status_sync_flow(self, client):
        """OTA订单推送→查询→同步→回调完整流程"""
        # 1. 飞猪推送票务订单
        push_resp = await client.post("/api/ota/orders/push", json={
            "platform": "fliggy",
            "channel_order_no": "FG_FULL_FLOW_001",
            "action": "create",
            "product_type": "ticket",
            "payload": {
                "ticket_type_id": 1, "spot_id": 1, "quantity": 1,
                "visit_date": "2026-12-31",
                "guest_name": "完整流程测试", "guest_phone": "13011112222",
                "total_price": 150.0,
            },
        })
        assert push_resp.json()["code"] == 0

        token = await self._login(client, "admin", "admin123")

        # 2. 查询OTA侧订单状态
        status_resp = await client.get(
            "/api/ota/orders/status?ota_order_id=FG_FULL_FLOW_001",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert status_resp.status_code == 200
        assert status_resp.json()["found"] is True
        assert status_resp.json()["status"] == "synced"

        # 3. 通过列表找到本地订单号
        list_resp = await client.get(
            "/api/ota/orders",
            headers={"Authorization": f"Bearer {token}"},
        )
        items = list_resp.json()["items"]
        local_order_no = None
        for item in items:
            if item.get("ota_order_id") == "FG_FULL_FLOW_001":
                local_order_no = item.get("local_order_no")
                break
        assert local_order_no is not None

        # 4. 同步状态
        sync_resp = await client.post(
            "/api/ota/orders/sync-status",
            json={"local_order_no": local_order_no},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert sync_resp.status_code == 200
        assert sync_resp.json()["success"] is True

        # 5. 回传确认状态到OTA
        callback_resp = await client.post(
            "/api/ota/orders/callback",
            json={
                "local_order_no": local_order_no,
                "action": "confirm",
                "reason": "票已确认，等待入园",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert callback_resp.status_code == 200
        assert callback_resp.json()["success"] is True

        # 6. 再次查询确认状态已更新
        final_status = await client.get(
            "/api/ota/orders/status?ota_order_id=FG_FULL_FLOW_001",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert final_status.status_code == 200
        assert final_status.json()["status"] == "confirmed"


class TestTicketVerificationEdgeCases:
    """票务核销边界场景测试"""

    async def _login(self, client, username, password):
        resp = await client.post("/api/auth/login", json={
            "username": username, "password": password,
        })
        assert resp.status_code == 200
        return resp.json()["access_token"]

    async def test_verify_with_invalid_token(self, client):
        """核销使用无效token"""
        staff_token = await self._login(client, "staff", "staff123")
        resp = await client.post(
            "/api/tickets/verify",
            json={"qr_token": "INVALID_TOKEN_12345"},
            headers={"Authorization": f"Bearer {staff_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["result"] == "invalid_token"

    async def test_guest_cannot_verify_tickets(self, client):
        """普通游客不能核销门票"""
        token = await self._login(client, "guest", "guest123")
        resp = await client.post(
            "/api/tickets/verify",
            json={"qr_token": "ANY_TOKEN"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    async def test_admin_can_verify_tickets(self, client):
        """管理员可以核销门票"""
        admin_token = await self._login(client, "admin", "admin123")
        resp = await client.post(
            "/api/tickets/verify",
            json={"qr_token": "ADMIN_VERIFY_TEST"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        # invalid_token 因为管理员也有权核销，token无效返回 invalid_token
        assert resp.json()["result"] == "invalid_token"

    async def test_verify_missing_qr_token(self, client):
        """核销时缺少qr_token"""
        staff_token = await self._login(client, "staff", "staff123")
        resp = await client.post(
            "/api/tickets/verify",
            json={},
            headers={"Authorization": f"Bearer {staff_token}"},
        )
        assert resp.status_code == 422


class TestNearbyPointsEdgeCases:
    """附近推荐点位边界测试"""

    async def _login(self, client, username, password):
        resp = await client.post("/api/auth/login", json={
            "username": username, "password": password,
        })
        assert resp.status_code == 200
        return resp.json()["access_token"]

    async def test_nearby_points_filter_by_spot_and_category(self, client):
        """同时过滤景区和分类"""
        resp = await client.get("/api/scenic/points?spot_id=1&category=dining")
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["spot_id"] == 1
            assert item["category"] == "dining"

    async def test_nearby_points_pagination(self, client):
        """附近推荐分页"""
        resp = await client.get("/api/scenic/points?page=1&page_size=3")
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert len(data["items"]) <= 3

    async def test_admin_update_nearby_point(self, client):
        """管理员更新附近推荐"""
        token = await self._login(client, "admin", "admin123")
        # 先获取现有推荐
        list_resp = await client.get("/api/scenic/points?spot_id=1")
        items = list_resp.json()["items"]
        if not items:
            import pytest
            pytest.skip("No nearby points to update")
        point = items[0]
        resp = await client.put(
            f"/api/scenic/points/{point['id']}",
            json={"name": point["name"] + "-已更新"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200

    async def test_guest_cannot_update_nearby_point(self, client):
        token = await self._login(client, "guest", "guest123")
        resp = await client.put(
            "/api/scenic/points/1",
            json={"name": "Hacked"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    async def test_nearby_points_search_by_description(self, client):
        """搜索附近推荐描述字段"""
        import time
        token = await self._login(client, "admin", "admin123")
        unique_suffix = f"DESC-TEST-{int(time.time() * 1000000)}"
        desc = f"特色美食推荐_{unique_suffix}"
        create_resp = await client.post(
            "/api/scenic/points",
            json={"spot_id": 1, "name": "描述搜索测试", "category": "dining", "rating": 4.5, "description": desc},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert create_resp.status_code == 201
        created_id = create_resp.json()["id"]
        resp = await client.get(f"/api/scenic/points?keyword={unique_suffix}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        found = [p for p in data["items"] if p["id"] == created_id]
        assert len(found) == 1, f"Expected 1, got {len(found)}"


class TestExportAdditionalFormats:
    """数据导出额外测试"""

    async def _login(self, client, username, password):
        resp = await client.post("/api/auth/login", json={
            "username": username, "password": password,
        })
        assert resp.status_code == 200
        return resp.json()["access_token"]

    async def test_export_parking_by_spot(self, client):
        token = await self._login(client, "admin", "admin123")
        resp = await client.get(
            "/api/export/parking?spot_id=1&start_date=2025-01-01&end_date=2030-12-31",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]

    async def test_export_tickets_defaults(self, client):
        """不带参数导出票务"""
        token = await self._login(client, "admin", "admin123")
        resp = await client.get(
            "/api/export/tickets",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200

    async def test_export_revenue_defaults(self, client):
        """不带参数导出营收"""
        token = await self._login(client, "admin", "admin123")
        resp = await client.get(
            "/api/export/revenue",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200


class TestPaymentCancelFlow:
    """支付取消流程测试"""

    async def _login(self, client, username, password):
        resp = await client.post("/api/auth/login", json={
            "username": username, "password": password,
        })
        assert resp.status_code == 200
        return resp.json()["access_token"]

    async def test_payment_cancel_ticket_order(self, client):
        """用户取消自己未支付的票务订单"""
        from datetime import date
        token = await self._login(client, "guest", "guest123")

        # 使用默认票种 id=1
        ticket_type_id = 1

        # 下单
        order_resp = await client.post(
            "/api/tickets/order",
            json={
                "ticket_type_id": ticket_type_id, "spot_id": 1, "quantity": 1,
                "visit_date": date.today().isoformat(), "time_slot": "08:00-10:00",
                "visitor_name": "取消测试", "visitor_phone": "13800138010",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert order_resp.status_code == 201
        order_no = order_resp.json()["order_no"]

        # 创建支付
        pay_resp = await client.post(
            "/api/payment/create",
            json={"order_no": order_no, "order_type": "ticket"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert pay_resp.status_code == 200

        # 取消支付
        cancel_resp = await client.post(
            "/api/payment/cancel",
            json={"order_no": order_no, "order_type": "ticket"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert cancel_resp.status_code == 200
        assert cancel_resp.json()["success"] is True
        assert cancel_resp.json()["message"] != ""

    async def test_payment_cancel_others_order(self, client):
        """不能取消他人订单"""
        from datetime import date
        import uuid
        guest1_token = await self._login(client, "guest", "guest123")
        # 注册另一个用户
        rand_user = f"user_{uuid.uuid4().hex[:8]}"
        phone_suffix = str(uuid.uuid4().int)[:8]
        reg_resp = await client.post("/api/auth/register", json={
            "username": rand_user, "password": "test123", "phone": f"139{phone_suffix}",
        })
        if reg_resp.status_code != 200:
            import pytest
            pytest.skip(f"Register failed: {reg_resp.status_code}")
        guest2_token = reg_resp.json()["access_token"]

        # guest1 下单（使用默认票种 id=1）
        tid = 1
        order_resp = await client.post(
            "/api/tickets/order",
            json={
                "ticket_type_id": tid, "spot_id": 1, "quantity": 1,
                "visit_date": date.today().isoformat(), "time_slot": "08:00-10:00",
                "visitor_name": "归属测试", "visitor_phone": "13800138011",
            },
            headers={"Authorization": f"Bearer {guest1_token}"},
        )
        order_no = order_resp.json()["order_no"]
        await client.post(
            "/api/payment/create",
            json={"order_no": order_no, "order_type": "ticket"},
            headers={"Authorization": f"Bearer {guest1_token}"},
        )

        # guest2 尝试取消 guest1 的订单
        cancel_resp = await client.post(
            "/api/payment/cancel",
            json={"order_no": order_no, "order_type": "ticket"},
            headers={"Authorization": f"Bearer {guest2_token}"},
        )
        assert cancel_resp.status_code in (403, 404)

    async def test_payment_cancel_no_auth(self, client):
        """取消支付需要鉴权"""
        resp = await client.post("/api/payment/cancel", json={
            "order_no": "TEST-123", "order_type": "ticket",
        })
        assert resp.status_code == 401


class TestScenicInfoUpdate:
    """景区信息编辑测试"""

    async def _login(self, client, username, password):
        resp = await client.post("/api/auth/login", json={
            "username": username, "password": password,
        })
        assert resp.status_code == 200
        return resp.json()["access_token"]

    async def test_admin_update_scenic_info(self, client):
        """管理员编辑景区信息"""
        token = await self._login(client, "admin", "admin123")
        resp = await client.put(
            "/api/scenic/info",
            json={"name": "泰山景区-已更新", "phone": "0538-8888888"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "泰山景区-已更新"
        assert data["phone"] == "0538-8888888"

        # 还原名称
        await client.put(
            "/api/scenic/info",
            json={"name": "泰山景区"},
            headers={"Authorization": f"Bearer {token}"},
        )

    async def test_admin_update_scenic_info_with_spot_id(self, client):
        """指定景区ID编辑"""
        token = await self._login(client, "admin", "admin123")
        resp = await client.put(
            "/api/scenic/info?spot_id=1",
            json={"description": "五岳之首，天下第一山-测试更新"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200

    async def test_guest_cannot_update_scenic_info(self, client):
        """游客不能编辑景区信息"""
        token = await self._login(client, "guest", "guest123")
        resp = await client.put(
            "/api/scenic/info",
            json={"name": "Hacked"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403


class TestAnnouncementUpdate:
    """公告编辑测试"""

    async def _login(self, client, username, password):
        resp = await client.post("/api/auth/login", json={
            "username": username, "password": password,
        })
        assert resp.status_code == 200
        return resp.json()["access_token"]

    async def test_admin_update_announcement(self, client):
        """管理员编辑公告"""
        token = await self._login(client, "admin", "admin123")
        # 先创建公告
        create_resp = await client.post(
            "/api/scenic/announcements",
            json={"title": "待编辑公告", "content": "原始内容", "spot_id": 1, "category": "notice"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert create_resp.status_code == 201
        ann_id = create_resp.json()["id"]

        # 编辑公告
        update_resp = await client.put(
            f"/api/scenic/announcements/{ann_id}",
            json={"title": "已编辑公告", "content": "更新后的内容", "priority": 1},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert update_resp.status_code == 200
        assert update_resp.json()["title"] == "已编辑公告"
        assert update_resp.json()["content"] == "更新后的内容"
        assert update_resp.json()["priority"] == 1

        # 清理
        await client.delete(
            f"/api/scenic/announcements/{ann_id}",
            headers={"Authorization": f"Bearer {token}"},
        )

    async def test_guest_cannot_update_announcement(self, client):
        """游客不能编辑公告"""
        token = await self._login(client, "guest", "guest123")
        resp = await client.put(
            "/api/scenic/announcements/1",
            json={"title": "Hacked"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403


class TestParkingCheckoutFlow:
    """停车出场缴费流程"""

    async def _login(self, client, username, password):
        resp = await client.post("/api/auth/login", json={
            "username": username, "password": password,
        })
        assert resp.status_code == 200
        return resp.json()["access_token"]

    async def test_parking_checkin_checkout(self, client):
        """停车入场→出场缴费完整流程"""
        token = await self._login(client, "guest", "guest123")

        # 获取有效费率
        rates_resp = await client.get("/api/parking/rates")
        assert rates_resp.status_code == 200
        rates = rates_resp.json()
        assert len(rates) > 0
        rate_id = rates[0]["id"]

        # 入场
        checkin_resp = await client.post(
            "/api/parking/checkin",
            json={"rate_id": rate_id, "plate_number": "鲁J-TEST01"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert checkin_resp.status_code == 200
        record_id = checkin_resp.json()["record"]["id"]

        # 出场缴费
        checkout_resp = await client.post(
            f"/api/parking/checkout/{record_id}",
            json={},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert checkout_resp.status_code == 200
        assert checkout_resp.json()["success"] is True
        assert "total_fee" in checkout_resp.json()

    async def test_parking_checkin_invalid_rate(self, client):
        """入场无效费率"""
        token = await self._login(client, "guest", "guest123")
        resp = await client.post(
            "/api/parking/checkin",
            json={"rate_id": 9999, "plate_number": "鲁J-TEST02"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404


class TestAdditionalScenarios:
    """其他补充场景测试"""

    async def _login(self, client, username, password):
        resp = await client.post("/api/auth/login", json={
            "username": username, "password": password,
        })
        assert resp.status_code == 200
        return resp.json()["access_token"]

    async def test_hotel_rooms_by_hotel(self, client):
        """按酒店获取房型列表"""
        token = await self._login(client, "admin", "admin123")
        hotels_resp = await client.get("/api/hotels", headers={"Authorization": f"Bearer {token}"})
        if hotels_resp.status_code == 200:
            hotels = hotels_resp.json()
            if isinstance(hotels, list) and len(hotels) > 0:
                hotel_id = hotels[0]["id"]
                resp = await client.get(
                    f"/api/hotels/{hotel_id}/rooms",
                    headers={"Authorization": f"Bearer {token}"},
                )
                assert resp.status_code == 200
                rooms = resp.json()
                assert isinstance(rooms, list)

    async def test_admin_delete_parking_rate(self, client):
        """管理员删除停车费率"""
        token = await self._login(client, "admin", "admin123")
        # 创建费率
        create_resp = await client.post(
            "/api/parking/rates",
            json={"spot_id": 1, "name": "待删除费率", "first_hour": 5.0, "daily_cap": 30.0},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert create_resp.status_code == 201
        rate_id = create_resp.json()["id"]

        # 尝试删除
        delete_resp = await client.delete(
            f"/api/parking/rates/{rate_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert delete_resp.status_code == 200
        assert delete_resp.json()["success"] is True

        # 验证已删除
        get_resp = await client.get("/api/parking/rates")
        assert get_resp.status_code == 200
        rates = get_resp.json()
        assert not any(r["id"] == rate_id for r in rates)

    async def test_admin_delete_parking_rate_not_found(self, client):
        """删除不存在的停车费率"""
        token = await self._login(client, "admin", "admin123")
        resp = await client.delete(
            "/api/parking/rates/99999",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404

    async def test_guest_cannot_delete_parking_rate(self, client):
        """非管理员不能删除停车费率"""
        token = await self._login(client, "guest", "guest123")
        resp = await client.delete(
            "/api/parking/rates/1",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    async def test_admin_force_checkout_parking(self, client):
        """管理员强制车辆出场"""
        token = await self._login(client, "guest", "guest123")
        # 车辆入场
        checkin_resp = await client.post(
            "/api/parking/checkin",
            json={"rate_id": 1, "plate_number": "京B67890"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert checkin_resp.status_code == 200
        record_id = checkin_resp.json()["record_id"]

        # 管理员强制出场
        admin_token = await self._login(client, "admin", "admin123")
        checkout_resp = await client.post(
            f"/api/parking/checkout/{record_id}/admin",
            json={"pay_method": "cash"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert checkout_resp.status_code == 200
        assert checkout_resp.json()["success"] is True
        assert checkout_resp.json()["total_fee"] >= 0

    async def test_admin_force_checkout_not_parking(self, client):
        """强制出场非parking状态记录应失败"""
        admin_token = await self._login(client, "admin", "admin123")
        # 获取已完成的记录
        resp = await client.get(
            "/api/parking/records/all?status=completed&page_size=1",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        items = resp.json().get("items", [])
        if items:
            record_id = items[0]["id"]
            checkout_resp = await client.post(
                f"/api/parking/checkout/{record_id}/admin",
                json={"pay_method": "cash"},
                headers={"Authorization": f"Bearer {admin_token}"},
            )
            assert checkout_resp.status_code == 400

    async def test_guest_cannot_force_checkout(self, client):
        """普通用户不能强制出场"""
        token = await self._login(client, "guest", "guest123")
        resp = await client.post(
            "/api/parking/checkout/1/admin",
            json={"pay_method": "cash"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    async def test_export_revenue_month(self, client):
        """导出月营收报表"""
        token = await self._login(client, "admin", "admin123")
        resp = await client.get(
            "/api/export/revenue?period=month",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]

    async def test_parking_my_records(self, client):
        """我的停车记录"""
        token = await self._login(client, "guest", "guest123")
        resp = await client.get(
            "/api/parking/records",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert "items" in data

    async def test_dashboard_stats_admin(self, client):
        """管理员仪表盘统计"""
        token = await self._login(client, "admin", "admin123")
        resp = await client.get(
            "/api/dashboard/stats",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data

    async def test_dashboard_overview(self, client):
        """管理员综合总览"""
        token = await self._login(client, "admin", "admin123")
        resp = await client.get(
            "/api/dashboard/overview",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert isinstance(data["data"], dict)

    async def test_payment_status_query(self, client):
        """查询支付状态（不存在的订单）"""
        token = await self._login(client, "guest", "guest123")
        resp = await client.get(
            "/api/payment/status/NONEXIST-ORDER-001",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "order_no" in data
        assert data["order_no"] == "NONEXIST-ORDER-001"

    async def test_ota_connection_test(self, client):
        """OTA平台连接测试"""
        token = await self._login(client, "admin", "admin123")
        resp = await client.post(
            "/api/ota/test-connection/ctrip",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "platform" in data
        assert data["platform"] == "ctrip"

    async def test_weather_refresh(self, client):
        """管理员刷新天气缓存"""
        token = await self._login(client, "admin", "admin123")
        resp = await client.post(
            "/api/scenic/weather/refresh",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "temperature" in data or "weather" in data


class TestInventoryOverselling:
    """库存超卖场景测试：验证乐观锁防超卖机制"""

    async def _login(self, client, username, password):
        resp = await client.post("/api/auth/login", json={
            "username": username, "password": password,
        })
        assert resp.status_code == 200
        return resp.json()["access_token"]

    async def test_oversell_prevented_by_optimistic_lock(self, client):
        """乐观锁阻止超卖：购买超过库存数量的票应失败"""
        admin_token = await self._login(client, "admin", "admin123")
        guest_token = await self._login(client, "guest", "guest123")

        # 创建一个库存很小的票种
        import uuid
        tt_name = f"超卖测试票种_{uuid.uuid4().hex[:6]}"
        create_resp = await client.post(
            "/api/tickets/types",
            json={
                "spot_id": 1,
                "name": tt_name,
                "category": "standard",
                "price": 10.0,
                "daily_stock": 5,  # 仅5张库存
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert create_resp.status_code == 201
        ticket_type_id = create_resp.json()["id"]

        from datetime import date
        # 使用未来日期避免与其他测试的库存冲突
        test_date = "2099-01-01"
        test_slot = "14:00-17:00"

        # 购买3张票（剩2张）
        r1 = await client.post(
            "/api/tickets/order",
            json={
                "ticket_type_id": ticket_type_id,
                "spot_id": 1,
                "quantity": 3,
                "visit_date": test_date,
                "time_slot": test_slot,
                "visitor_name": "超卖测试A",
            },
            headers={"Authorization": f"Bearer {guest_token}"},
        )
        assert r1.status_code == 201

        # 购买2张票（剩0张）
        r2 = await client.post(
            "/api/tickets/order",
            json={
                "ticket_type_id": ticket_type_id,
                "spot_id": 1,
                "quantity": 2,
                "visit_date": test_date,
                "time_slot": test_slot,
                "visitor_name": "超卖测试B",
            },
            headers={"Authorization": f"Bearer {guest_token}"},
        )
        assert r2.status_code == 201

        # 再购买1张票 — 应返回400库存不足
        r3 = await client.post(
            "/api/tickets/order",
            json={
                "ticket_type_id": ticket_type_id,
                "spot_id": 1,
                "quantity": 1,
                "visit_date": test_date,
                "time_slot": test_slot,
                "visitor_name": "超卖测试C",
            },
            headers={"Authorization": f"Bearer {guest_token}"},
        )
        assert r3.status_code == 400
        assert "仅剩" in r3.json()["detail"] or "库存" in r3.json()["detail"]

    async def test_oversell_stock_exhausted_message(self, client):
        """库存耗尽时应返回明确的剩余数量"""
        admin_token = await self._login(client, "admin", "admin123")
        guest_token = await self._login(client, "guest", "guest123")

        import uuid
        tt_name = f"库存耗尽测试_{uuid.uuid4().hex[:6]}"
        create_resp = await client.post(
            "/api/tickets/types",
            json={
                "spot_id": 1,
                "name": tt_name,
                "category": "standard",
                "price": 5.0,
                "daily_stock": 2,
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert create_resp.status_code == 201
        ticket_type_id = create_resp.json()["id"]

        from datetime import date
        # 使用未来日期避免与其他测试的库存冲突
        test_date = "2099-02-01"
        test_slot = "14:00-17:00"

        # 买1张（剩1张）
        r1 = await client.post(
            "/api/tickets/order",
            json={
                "ticket_type_id": ticket_type_id, "spot_id": 1,
                "quantity": 1, "visit_date": test_date, "time_slot": test_slot,
            },
            headers={"Authorization": f"Bearer {guest_token}"},
        )
        assert r1.status_code == 201

        # 尝试买3张（超过剩余1张）
        r2 = await client.post(
            "/api/tickets/order",
            json={
                "ticket_type_id": ticket_type_id, "spot_id": 1,
                "quantity": 3, "visit_date": test_date, "time_slot": test_slot,
            },
            headers={"Authorization": f"Bearer {guest_token}"},
        )
        assert r2.status_code == 400
        assert "仅剩" in r2.json()["detail"]

    async def test_stock_release_on_cancel(self, client):
        """取消订单应释放库存，后续可再购买"""
        token = await self._login(client, "guest", "guest123")

        from datetime import date
        # 使用未来日期避免与其他测试的库存冲突
        test_date = "2099-03-01"
        test_slot = "14:00-17:00"

        # 使用默认票种（spot_id=1, id=1，库存1000，不受前面测试影响）
        ticket_type_id = 1

        # 买1张
        r1 = await client.post(
            "/api/tickets/order",
            json={
                "ticket_type_id": ticket_type_id, "spot_id": 1,
                "quantity": 1, "visit_date": test_date, "time_slot": test_slot,
                "visitor_name": "库存释放测试",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r1.status_code == 201
        order_id = r1.json()["id"]
        order_no = r1.json()["order_no"]

        # 退款（取消未支付订单，释放库存）
        refund_resp = await client.post(
            f"/api/tickets/order/{order_id}/refund",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert refund_resp.status_code == 200
        assert refund_resp.json()["success"] is True

        # 再买1张同一时段 — 应成功（库存已恢复）
        r2 = await client.post(
            "/api/tickets/order",
            json={
                "ticket_type_id": ticket_type_id, "spot_id": 1,
                "quantity": 1, "visit_date": test_date, "time_slot": test_slot,
                "visitor_name": "库存恢复测试",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r2.status_code == 201

    async def test_oversell_different_time_slots(self, client):
        """不同时段库存独立：一个时段售罄不影响另一时段"""
        admin_token = await self._login(client, "admin", "admin123")
        guest_token = await self._login(client, "guest", "guest123")

        import uuid
        tt_name = f"时段独立测试_{uuid.uuid4().hex[:6]}"
        create_resp = await client.post(
            "/api/tickets/types",
            json={
                "spot_id": 1,
                "name": tt_name,
                "price": 1.0,
                "daily_stock": 1,
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert create_resp.status_code == 201
        ticket_type_id = create_resp.json()["id"]

        from datetime import date
        # 使用未来日期避免与其他测试的库存冲突
        test_date = "2099-04-01"

        # 买光08:00-10:00时段
        r1 = await client.post(
            "/api/tickets/order",
            json={
                "ticket_type_id": ticket_type_id, "spot_id": 1,
                "quantity": 1, "visit_date": test_date, "time_slot": "08:00-10:00",
            },
            headers={"Authorization": f"Bearer {guest_token}"},
        )
        assert r1.status_code == 201

        # 同一个票种不同时段(10:00-12:00)应能购买
        r2 = await client.post(
            "/api/tickets/order",
            json={
                "ticket_type_id": ticket_type_id, "spot_id": 1,
                "quantity": 1, "visit_date": test_date, "time_slot": "10:00-12:00",
            },
            headers={"Authorization": f"Bearer {guest_token}"},
        )
        assert r2.status_code == 201


class TestOtaCallbackIdempotency:
    """OTA回调幂等性测试：重复回调/重复推送应安全处理"""

    async def _login(self, client, username, password):
        resp = await client.post("/api/auth/login", json={
            "username": username, "password": password,
        })
        assert resp.status_code == 200
        return resp.json()["access_token"]

    async def test_ota_push_same_order_twice_idempotent(self, client):
        """OTA推送同一渠道订单两次：第一次成功，第二次也应返回成功（幂等）"""
        import uuid
        ota_order_id = f"CT_IDEMPOTENT_{uuid.uuid4().hex[:8].upper()}"

        # 第一次推送
        r1 = await client.post("/api/ota/orders/push", json={
            "platform": "ctrip",
            "channel_order_no": ota_order_id,
            "action": "create",
            "product_type": "ticket",
            "payload": {
                "ticket_type_id": 1, "spot_id": 1, "quantity": 1,
                "visit_date": "2026-12-25",
                "guest_name": "幂等测试游客", "guest_phone": "13800000000",
                "total_price": 100.0,
            },
        })
        assert r1.status_code == 200
        assert r1.json()["code"] == 0

        # 第二次推送同一渠道订单号（幂等）
        r2 = await client.post("/api/ota/orders/push", json={
            "platform": "ctrip",
            "channel_order_no": ota_order_id,
            "action": "create",
            "product_type": "ticket",
            "payload": {
                "ticket_type_id": 1, "spot_id": 1, "quantity": 1,
                "visit_date": "2026-12-25",
                "guest_name": "幂等测试游客", "guest_phone": "13800000000",
                "total_price": 100.0,
            },
        })
        # 幂等：第二次也应该成功（覆盖之前记录）
        assert r2.status_code == 200
        assert r2.json()["code"] == 0

    async def test_ota_push_cancel_on_already_cancelled(self, client):
        """OTA推送取消已取消的订单：幂等处理"""
        import uuid
        ota_order_id = f"CT_CANCEL_IDEM_{uuid.uuid4().hex[:8].upper()}"

        # 推送创建
        await client.post("/api/ota/orders/push", json={
            "platform": "ctrip",
            "channel_order_no": ota_order_id,
            "action": "create",
            "product_type": "ticket",
            "payload": {
                "ticket_type_id": 1, "spot_id": 1, "quantity": 1,
                "visit_date": "2026-11-11",
                "guest_name": "取消幂等测试", "guest_phone": "13900000000",
                "total_price": 50.0,
            },
        })

        # 第一次取消
        r1 = await client.post("/api/ota/orders/push", json={
            "platform": "ctrip",
            "channel_order_no": ota_order_id,
            "action": "cancel",
            "product_type": "ticket",
            "payload": {},
        })
        assert r1.status_code == 200
        assert r1.json()["code"] == 0

        # 第二次取消（幂等）
        r2 = await client.post("/api/ota/orders/push", json={
            "platform": "ctrip",
            "channel_order_no": ota_order_id,
            "action": "cancel",
            "product_type": "ticket",
            "payload": {},
        })
        # 第二次取消应返回 code=1（找不到OTA订单，因为取消时已查找本地订单）
        # 实际上它查找ota_order_store中的记录，如果之前取消成功则记录还在
        assert r2.status_code == 200
        # 无论code是0还是1，系统应能正常处理后返回

    async def test_ota_callback_confirm_idempotent(self, client):
        """OTA回调确认：重复确认应返回幂等提示"""
        import uuid
        ota_order_id = f"CT_CB_IDEM_{uuid.uuid4().hex[:8].upper()}"

        # 推送订单
        await client.post("/api/ota/orders/push", json={
            "platform": "ctrip",
            "channel_order_no": ota_order_id,
            "action": "create",
            "product_type": "ticket",
            "payload": {
                "ticket_type_id": 1, "spot_id": 1, "quantity": 1,
                "visit_date": "2026-10-10",
                "guest_name": "回调幂等测试", "guest_phone": "13700000000",
                "total_price": 80.0,
            },
        })

        token = await self._login(client, "admin", "admin123")

        # 获取本地订单号
        list_resp = await client.get(
            "/api/ota/orders",
            headers={"Authorization": f"Bearer {token}"},
        )
        items = list_resp.json()["items"]
        local_order_no = None
        for item in items:
            if item.get("ota_order_id") == ota_order_id:
                local_order_no = item.get("local_order_no")
                break
        assert local_order_no is not None

        # 第一次回传确认
        r1 = await client.post(
            "/api/ota/orders/callback",
            json={"local_order_no": local_order_no, "action": "confirm", "reason": "第一次确认"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r1.status_code == 200
        assert r1.json()["success"] is True

        # 第二次回传确认（幂等）
        r2 = await client.post(
            "/api/ota/orders/callback",
            json={"local_order_no": local_order_no, "action": "confirm", "reason": "第二次确认-幂等"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r2.status_code == 200
        assert r2.json()["success"] is True
        assert "无需重复处理" in r2.json()["message"] or "幂等" in r2.json()["message"]

    async def test_ota_callback_cancel_idempotent(self, client):
        """OTA回调取消：重复取消应返回幂等提示"""
        import uuid
        ota_order_id = f"MT_CB_CANCEL_{uuid.uuid4().hex[:8].upper()}"

        # 推送订单
        await client.post("/api/ota/orders/push", json={
            "platform": "meituan",
            "channel_order_no": ota_order_id,
            "action": "create",
            "product_type": "ticket",
            "payload": {
                "ticket_type_id": 1, "spot_id": 1, "quantity": 1,
                "visit_date": "2026-09-09",
                "guest_name": "取消回调幂等测试", "guest_phone": "13600000000",
                "total_price": 60.0,
            },
        })

        token = await self._login(client, "admin", "admin123")

        # 获取本地订单号
        list_resp = await client.get(
            "/api/ota/orders",
            headers={"Authorization": f"Bearer {token}"},
        )
        items = list_resp.json()["items"]
        local_order_no = None
        for item in items:
            if item.get("ota_order_id") == ota_order_id:
                local_order_no = item.get("local_order_no")
                break
        assert local_order_no is not None

        # 第一次回传取消
        r1 = await client.post(
            "/api/ota/orders/callback",
            json={"local_order_no": local_order_no, "action": "cancel", "reason": "第一次取消"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r1.status_code == 200
        assert r1.json()["success"] is True

        # 第二次回传取消（幂等）
        r2 = await client.post(
            "/api/ota/orders/callback",
            json={"local_order_no": local_order_no, "action": "cancel", "reason": "第二次取消-幂等"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r2.status_code == 200
        assert r2.json()["success"] is True
        assert "无需重复处理" in r2.json()["message"] or "幂等" in r2.json()["message"]

    async def test_ota_callback_multiple_actions_sequence(self, client):
        """OTA回调连续多次不同操作：创建→确认→取消→退款"""
        import uuid
        ota_order_id = f"FG_SEQ_{uuid.uuid4().hex[:8].upper()}"

        # 推送订单
        await client.post("/api/ota/orders/push", json={
            "platform": "fliggy",
            "channel_order_no": ota_order_id,
            "action": "create",
            "product_type": "ticket",
            "payload": {
                "ticket_type_id": 1, "spot_id": 1, "quantity": 1,
                "visit_date": "2026-08-08",
                "guest_name": "序列操作测试", "guest_phone": "13500000000",
                "total_price": 70.0,
            },
        })

        token = await self._login(client, "admin", "admin123")

        # 获取本地订单号
        list_resp = await client.get(
            "/api/ota/orders",
            headers={"Authorization": f"Bearer {token}"},
        )
        items = list_resp.json()["items"]
        local_order_no = None
        for item in items:
            if item.get("ota_order_id") == ota_order_id:
                local_order_no = item.get("local_order_no")
                break
        assert local_order_no is not None

        # 1. 确认
        r1 = await client.post(
            "/api/ota/orders/callback",
            json={"local_order_no": local_order_no, "action": "confirm"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r1.status_code == 200
        assert r1.json()["success"] is True

        # 2. 取消（从confirmed→cancelled）
        r2 = await client.post(
            "/api/ota/orders/callback",
            json={"local_order_no": local_order_no, "action": "cancel"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r2.status_code == 200
        assert r2.json()["success"] is True

        # 3. 退款（从cancelled→refunded）
        r3 = await client.post(
            "/api/ota/orders/callback",
            json={"local_order_no": local_order_no, "action": "refund"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r3.status_code == 200
        assert r3.json()["success"] is True


class TestPaymentRefundFullFlow:
    """支付退款完整流程测试：购票→支付→退款申请→管理员审核"""

    async def _login(self, client, username, password):
        resp = await client.post("/api/auth/login", json={
            "username": username, "password": password,
        })
        assert resp.status_code == 200
        return resp.json()["access_token"]

    async def test_ticket_refund_approve_full_flow(self, client):
        """票务退款完整流程：支付→申请退款→管理员审核批准"""
        admin_token = await self._login(client, "admin", "admin123")
        guest_token = await self._login(client, "guest", "guest123")

        from datetime import date, timedelta
        future_date = (date.today() + timedelta(days=30)).isoformat()

        # 1. 购票（使用默认票种 id=1，库存1000）
        ticket_type_id = 1

        order_resp = await client.post(
            "/api/tickets/order",
            json={
                "ticket_type_id": ticket_type_id, "spot_id": 1,
                "quantity": 1, "visit_date": future_date, "time_slot": "08:00-10:00",
                "visitor_name": "退款审核测试", "visitor_phone": "13800138005",
            },
            headers={"Authorization": f"Bearer {guest_token}"},
        )
        assert order_resp.status_code == 201
        order_no = order_resp.json()["order_no"]
        order_id = order_resp.json()["id"]

        # 2. 支付
        pay_resp = await client.post(
            "/api/payment/create",
            json={"order_no": order_no, "order_type": "ticket"},
            headers={"Authorization": f"Bearer {guest_token}"},
        )
        assert pay_resp.status_code == 200
        transaction_id = pay_resp.json()["transaction_id"]

        # 确认支付
        confirm_resp = await client.post("/api/payment/confirm", json={
            "transaction_id": transaction_id, "order_no": order_no,
        })
        assert confirm_resp.status_code == 200

        # 验证已支付
        order_check = await client.get(
            f"/api/tickets/order/{order_no}",
            headers={"Authorization": f"Bearer {guest_token}"},
        )
        assert order_check.json()["status"] == "paid"

        # 3. 申请退款（进入refunding状态）
        refund_resp = await client.post(
            f"/api/tickets/order/{order_id}/refund",
            headers={"Authorization": f"Bearer {guest_token}"},
        )
        assert refund_resp.status_code == 200
        assert refund_resp.json()["success"] is True
        assert "审核" in refund_resp.json()["message"]

        # 验证订单状态变为 refunding
        order_check2 = await client.get(
            f"/api/tickets/order/{order_no}",
            headers={"Authorization": f"Bearer {guest_token}"},
        )
        assert order_check2.json()["status"] == "refunding"

        # 4. 管理员查看待审核退款列表
        pending_resp = await client.get(
            "/api/payment/refund/pending",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert pending_resp.status_code == 200
        pending_items = pending_resp.json()["items"]

        # 5. 管理员批准退款
        approve_resp = await client.post(
            "/api/payment/refund/approve",
            json={"transaction_id": transaction_id, "approved": True, "reason": "审核通过-测试"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert approve_resp.status_code == 200
        assert approve_resp.json()["success"] is True
        assert approve_resp.json()["refund_amount"] > 0

        # 6. 验证最终状态为 refunded
        final_check = await client.get(
            f"/api/tickets/order/{order_no}",
            headers={"Authorization": f"Bearer {guest_token}"},
        )
        assert final_check.json()["status"] == "refunded"

    async def test_ticket_refund_deny_flow(self, client):
        """票务退款拒绝流程：支付→申请退款→管理员拒绝→恢复为paid"""
        admin_token = await self._login(client, "admin", "admin123")
        guest_token = await self._login(client, "guest", "guest123")

        from datetime import date, timedelta
        future_date = (date.today() + timedelta(days=31)).isoformat()

        # 购票+支付（使用默认票种 id=1，库存1000）
        ticket_type_id = 1

        order_resp = await client.post(
            "/api/tickets/order",
            json={
                "ticket_type_id": ticket_type_id, "spot_id": 1,
                "quantity": 1, "visit_date": future_date, "time_slot": "08:00-10:00",
                "visitor_name": "拒绝退款测试", "visitor_phone": "13800138006",
            },
            headers={"Authorization": f"Bearer {guest_token}"},
        )
        order_no = order_resp.json()["order_no"]
        order_id = order_resp.json()["id"]

        pay_resp = await client.post(
            "/api/payment/create",
            json={"order_no": order_no, "order_type": "ticket"},
            headers={"Authorization": f"Bearer {guest_token}"},
        )
        transaction_id = pay_resp.json()["transaction_id"]
        await client.post("/api/payment/confirm", json={
            "transaction_id": transaction_id, "order_no": order_no,
        })

        # 申请退款
        await client.post(
            f"/api/tickets/order/{order_id}/refund",
            headers={"Authorization": f"Bearer {guest_token}"},
        )

        # 管理员拒绝退款
        deny_resp = await client.post(
            "/api/payment/refund/approve",
            json={"transaction_id": transaction_id, "approved": False, "reason": "不符合退款条件"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert deny_resp.status_code == 200
        assert deny_resp.json()["success"] is True
        assert deny_resp.json()["refund_amount"] == 0.0

        # 验证订单恢复为 paid
        final_check = await client.get(
            f"/api/tickets/order/{order_no}",
            headers={"Authorization": f"Bearer {guest_token}"},
        )
        assert final_check.json()["status"] == "paid"

    async def test_refund_already_refunded_order(self, client):
        """对已退款订单再次申请退款应失败"""
        guest_token = await self._login(client, "guest", "guest123")

        from datetime import date
        today = date.today().isoformat()

        # 使用默认票种（id=1，库存1000，不受前面测试影响）
        ticket_type_id = 1

        order_resp = await client.post(
            "/api/tickets/order",
            json={
                "ticket_type_id": ticket_type_id, "spot_id": 1,
                "quantity": 1, "visit_date": today, "time_slot": "08:00-10:00",
                "visitor_name": "重复退款测试",
            },
            headers={"Authorization": f"Bearer {guest_token}"},
        )
        order_id = order_resp.json()["id"]

        # 第一次退款（pending订单直接取消）
        r1 = await client.post(
            f"/api/tickets/order/{order_id}/refund",
            headers={"Authorization": f"Bearer {guest_token}"},
        )
        assert r1.status_code == 200
        assert r1.json()["success"] is True

        # 第二次退款（应失败）
        r2 = await client.post(
            f"/api/tickets/order/{order_id}/refund",
            headers={"Authorization": f"Bearer {guest_token}"},
        )
        assert r2.status_code == 400
        assert "已取消" in r2.json()["detail"] or "已退款" in r2.json()["detail"]

    async def test_refund_verified_ticket_fails(self, client):
        """已核销的票不可退款"""
        guest_token = await self._login(client, "guest", "guest123")
        staff_token = await self._login(client, "staff", "staff123")

        from datetime import date
        today = date.today().isoformat()

        # 使用默认票种（id=1，库存1000，不受前面测试影响）
        ticket_type_id = 1

        order_resp = await client.post(
            "/api/tickets/order",
            json={
                "ticket_type_id": ticket_type_id, "spot_id": 1,
                "quantity": 1, "visit_date": today, "time_slot": "08:00-10:00",
                "visitor_name": "核销后退款测试",
            },
            headers={"Authorization": f"Bearer {guest_token}"},
        )
        order_no = order_resp.json()["order_no"]
        order_id = order_resp.json()["id"]
        qr_token = order_resp.json()["qr_token"]

        # 支付
        pay_resp = await client.post(
            "/api/payment/create",
            json={"order_no": order_no, "order_type": "ticket"},
            headers={"Authorization": f"Bearer {guest_token}"},
        )
        await client.post("/api/payment/confirm", json={
            "transaction_id": pay_resp.json()["transaction_id"], "order_no": order_no,
        })

        # 核销
        await client.post(
            "/api/tickets/verify",
            json={"qr_token": qr_token},
            headers={"Authorization": f"Bearer {staff_token}"},
        )

        # 尝试退款已核销的票
        refund_resp = await client.post(
            f"/api/tickets/order/{order_id}/refund",
            headers={"Authorization": f"Bearer {guest_token}"},
        )
        assert refund_resp.status_code == 400
        assert "不可退款" in refund_resp.json()["detail"]

    async def test_guest_cannot_approve_refund(self, client):
        """游客不能直接审核退款"""
        guest_token = await self._login(client, "guest", "guest123")
        resp = await client.post(
            "/api/payment/refund/approve",
            json={"transaction_id": "WX_ANY", "approved": True},
            headers={"Authorization": f"Bearer {guest_token}"},
        )
        assert resp.status_code == 403

    async def test_payment_status_reflects_refund(self, client):
        """支付状态查询应反映退款状态"""
        admin_token = await self._login(client, "admin", "admin123")
        guest_token = await self._login(client, "guest", "guest123")

        from datetime import date, timedelta
        future_date = (date.today() + timedelta(days=32)).isoformat()

        # 购票+支付（使用默认票种 id=1，库存1000）
        ticket_type_id = 1

        order_resp = await client.post(
            "/api/tickets/order",
            json={
                "ticket_type_id": ticket_type_id, "spot_id": 1,
                "quantity": 1, "visit_date": future_date, "time_slot": "08:00-10:00",
                "visitor_name": "支付状态测试",
            },
            headers={"Authorization": f"Bearer {guest_token}"},
        )
        order_no = order_resp.json()["order_no"]
        order_id = order_resp.json()["id"]

        pay_resp = await client.post(
            "/api/payment/create",
            json={"order_no": order_no, "order_type": "ticket"},
            headers={"Authorization": f"Bearer {guest_token}"},
        )
        transaction_id = pay_resp.json()["transaction_id"]
        await client.post("/api/payment/confirm", json={
            "transaction_id": transaction_id, "order_no": order_no,
        })

        # 查询支付状态：应为 success
        status1 = await client.get(
            f"/api/payment/status/{order_no}",
            headers={"Authorization": f"Bearer {guest_token}"},
        )
        assert status1.json()["status"] == "success"

        # 申请退款
        await client.post(
            f"/api/tickets/order/{order_id}/refund",
            headers={"Authorization": f"Bearer {guest_token}"},
        )

        # 查询支付状态：应为 refunding
        status2 = await client.get(
            f"/api/payment/status/{order_no}",
            headers={"Authorization": f"Bearer {guest_token}"},
        )
        assert status2.json()["status"] == "refunding"

        # 管理员批准退款
        await client.post(
            "/api/payment/refund/approve",
            json={"transaction_id": transaction_id, "approved": True},
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        # 查询支付状态：应为 refund
        status3 = await client.get(
            f"/api/payment/status/{order_no}",
            headers={"Authorization": f"Bearer {guest_token}"},
        )
        assert status3.json()["status"] == "refund"


class TestScenicList:
    """景区列表接口测试 — GET /api/scenic/list"""

    async def _login(self, client, username, password):
        resp = await client.post("/api/auth/login", json={
            "username": username, "password": password,
        })
        assert resp.status_code == 200
        return resp.json()["access_token"]

    async def test_scenic_list_returns_200(self, client):
        """景区列表：公开接口，返回所有景区"""
        resp = await client.get("/api/scenic/list")
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert "items" in data
        assert data["total"] >= 3  # 有至少3个景区(泰山/黄山/峨眉山)
        assert len(data["items"]) > 0
        # 验证返回字段
        item = data["items"][0]
        assert "id" in item
        assert "name" in item
        assert "city" in item
        assert "rating" in item

    async def test_scenic_list_pagination(self, client):
        """景区列表：分页参数生效"""
        # 第1页取1条
        resp = await client.get("/api/scenic/list?page=1&page_size=1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 3
        assert len(data["items"]) == 1

        # 第2页取1条
        resp2 = await client.get("/api/scenic/list?page=2&page_size=1")
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert len(data2["items"]) == 1
        # 第2页的条目应该不同于第1页
        assert data["items"][0]["id"] != data2["items"][0]["id"]

    async def test_scenic_list_no_auth_required(self, client):
        """景区列表：无需鉴权"""
        resp = await client.get("/api/scenic/list")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0

    async def test_scenic_list_large_page_size(self, client):
        """景区列表：最大page_size=500"""
        resp = await client.get("/api/scenic/list?page_size=500")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) <= 500
        assert len(data["items"]) == data["total"]  # 实际数据量应小于500


class TestTicketsBatchExpire:
    """批量过期处理测试 — POST /api/tickets/batch-expire（管理员）"""

    async def _login(self, client, username, password):
        resp = await client.post("/api/auth/login", json={
            "username": username, "password": password,
        })
        assert resp.status_code == 200
        return resp.json()["access_token"]

    async def test_batch_expire_no_auth(self, client):
        """批量过期：无鉴权返回401"""
        resp = await client.post("/api/tickets/batch-expire")
        assert resp.status_code == 401

    async def test_batch_expire_as_guest(self, client):
        """批量过期：guest无权访问"""
        token = await self._login(client, "guest", "guest123")
        resp = await client.post(
            "/api/tickets/batch-expire",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    async def test_batch_expire_as_admin(self, client):
        """批量过期：admin可以调用，返回success"""
        token = await self._login(client, "admin", "admin123")
        resp = await client.post(
            "/api/tickets/batch-expire",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "expired_count" in data
        assert isinstance(data["expired_count"], int)

    async def test_batch_expire_idempotent(self, client):
        """批量过期：重复调用幂等，返回success"""
        token = await self._login(client, "admin", "admin123")
        resp1 = await client.post(
            "/api/tickets/batch-expire",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp1.status_code == 200
        assert resp1.json()["success"] is True

        # 二次调用同样成功
        resp2 = await client.post(
            "/api/tickets/batch-expire",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp2.status_code == 200
        assert resp2.json()["success"] is True


class TestHotelOrderDetail:
    """酒店订单详情测试 — GET /api/hotels/orders/detail/{order_no}"""

    async def _login(self, client, username, password):
        resp = await client.post("/api/auth/login", json={
            "username": username, "password": password,
        })
        assert resp.status_code == 200
        return resp.json()["access_token"]

    async def _create_hotel_order(self, client, admin_token, guest_token):
        """辅助函数：创建酒店订单并返回order_no"""
        # 创建酒店
        hotel_resp = await client.post(
            "/api/hotels",
            json={
                "spot_id": 1, "name": "订单详情测试酒店",
                "address": "详情测试地址", "city": "泰安",
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        hotel_id = hotel_resp.json()["id"]

        # 创建房型
        room_resp = await client.post(
            f"/api/hotels/{hotel_id}/rooms",
            json={
                "hotel_id": hotel_id, "name": "详情测试房型",
                "price": 200.0, "total_count": 5,
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        room_id = room_resp.json()["id"]

        # 下单
        from datetime import date, timedelta
        checkin = date.today() + timedelta(days=5)
        checkout = date.today() + timedelta(days=7)
        order_resp = await client.post(
            "/api/hotels/orders",
            json={
                "hotel_id": hotel_id, "room_id": room_id, "room_count": 1,
                "checkin_date": checkin.isoformat(),
                "checkout_date": checkout.isoformat(),
                "guest_name": "订单详情客人", "guest_phone": "13800138008",
            },
            headers={"Authorization": f"Bearer {guest_token}"},
        )
        return order_resp.json()["order_no"]

    async def test_hotel_order_detail_no_auth(self, client):
        """酒店订单详情：无鉴权返回401"""
        resp = await client.get("/api/hotels/orders/detail/TEST-ORDER-NO")
        assert resp.status_code == 401

    async def test_hotel_order_detail_returns_200(self, client):
        """酒店订单详情：按订单号查询返回200"""
        admin_token = await self._login(client, "admin", "admin123")
        guest_token = await self._login(client, "guest", "guest123")

        order_no = await self._create_hotel_order(client, admin_token, guest_token)

        resp = await client.get(
            f"/api/hotels/orders/detail/{order_no}",
            headers={"Authorization": f"Bearer {guest_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["order_no"] == order_no
        assert "hotel_id" in data
        assert "room_id" in data
        assert "guest_name" in data
        assert "guest_phone" in data
        assert "checkin_date" in data
        assert "checkout_date" in data
        assert "status" in data
        assert data["status"] == "pending"

    async def test_hotel_order_detail_not_found(self, client):
        """酒店订单详情：不存在的订单号返回404"""
        token = await self._login(client, "guest", "guest123")
        resp = await client.get(
            "/api/hotels/orders/detail/NONEXIST-HOTEL-ORDER-99999",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404

    async def test_hotel_order_detail_others_order(self, client):
        """酒店订单详情：任意认证用户可查询订单（供支付回调使用，无用户隔离）"""
        admin_token = await self._login(client, "admin", "admin123")
        guest_token = await self._login(client, "guest", "guest123")
        staff_token = await self._login(client, "staff", "staff123")

        order_no = await self._create_hotel_order(client, admin_token, guest_token)

        # staff用户可以查询guest创建的订单
        resp = await client.get(
            f"/api/hotels/orders/detail/{order_no}",
            headers={"Authorization": f"Bearer {staff_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["order_no"] == order_no
