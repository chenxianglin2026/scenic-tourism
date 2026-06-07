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

        # 2. 获取票种列表
        types_resp = await client.get("/api/tickets/types?spot_id=1")
        assert types_resp.status_code == 200
        ticket_types = types_resp.json()
        assert len(ticket_types) > 0
        ticket_type_id = ticket_types[0]["id"]

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
