#!/usr/bin/env python3
"""Comprehensive API Endpoint Verification"""
import json
import urllib.request
import urllib.error

BASE = "http://127.0.0.1:8000"

def call(method, path, data=None, token=None):
    url = f"{BASE}{path}"
    body = json.dumps(data).encode() if data else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    r = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        resp = urllib.request.urlopen(r)
        return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode())
        except:
            return e.code, {"error": str(e)}
    except Exception as e:
        return -1, {"error": str(e)}

# Get tokens
print("=== Getting auth tokens ===")
_, guest = call("POST", "/api/auth/login", {"username":"guest","password":"guest123"})
_, admin = call("POST", "/api/auth/login", {"username":"admin","password":"admin123"})
_, staff = call("POST", "/api/auth/login", {"username":"staff","password":"staff123"})
guest_t = guest["access_token"]
admin_t = admin["access_token"]
staff_t = staff["access_token"]
print(f"guest={guest['role']}, admin={admin['role']}, staff={staff['role']}\n")

# Define all endpoints with expected behavior
endpoints = [
    # (method, path, auth_level, data, expected_no_auth, expected_guest, expected_admin)
    # === System ===
    ("GET", "/health", "公开", None, 200, 200, 200),
    ("GET", "/", "公开", None, 200, 200, 200),
    
    # === Auth ===
    ("POST", "/api/auth/register", "公开", {"username":"e2e_test","password":"test123","phone":"13900000000","nickname":"E2E"}, 200, None, None),
    ("POST", "/api/auth/login", "公开", {"username":"guest","password":"guest123"}, 200, None, None),
    ("GET", "/api/auth/me", "鉴权", None, 401, 200, 200),
    
    # === Tickets ===
    ("GET", "/api/tickets/types", "公开", None, 200, 200, 200),
    ("POST", "/api/tickets/types", "管理员", {"spot_id":1,"name":"E2E_Test","price":99}, 401, 403, 201),
    ("POST", "/api/tickets/order", "鉴权", {"ticket_type_id":1,"spot_id":1,"quantity":1,"visit_date":"2026-12-31","time_slot":"08:00-10:00"}, 401, 201, None),
    ("GET", "/api/tickets/orders", "鉴权", None, 401, 200, None),
    ("POST", "/api/tickets/verify", "工作人员", {"qr_token":"fake"}, 401, 403, None),
    
    # === Scenic ===
    ("GET", "/api/scenic/info", "公开", None, 200, 200, 200),
    ("GET", "/api/scenic/announcements", "公开", None, 200, 200, 200),
    ("GET", "/api/scenic/pois", "公开", None, 200, 200, 200),
    ("GET", "/api/scenic/weather", "公开", None, 200, 200, 200),
    ("PUT", "/api/scenic/info", "管理员", {"name":"Test"}, 401, 403, 200),
    
    # === Parking ===
    ("GET", "/api/parking/rates", "公开", None, 200, 200, 200),
    ("PUT", "/api/parking/rates/1", "管理员", {"name":"Test"}, 401, 403, 200),
    ("POST", "/api/parking/checkin", "鉴权", {"rate_id":1,"plate_number":"京A11111"}, 401, 200, None),
    ("GET", "/api/parking/records", "鉴权", None, 401, 200, None),
    ("GET", "/api/parking/records/all", "管理员", None, 401, 403, 200),
    
    # === Payment ===
    ("POST", "/api/payment/create", "鉴权", {"order_no":"test","order_type":"ticket"}, 401, 404, None),
    ("POST", "/api/payment/notify", "公开(回调)", {"transaction_id":"test","order_no":"test","order_type":"ticket","amount":1,"result_code":"SUCCESS"}, 404, None, None),
    ("GET", "/api/payment/status/NONEXIST", "鉴权", None, 401, 200, None),
    
    # === Hotels ===
    ("GET", "/api/hotels", "公开", None, 200, 200, 200),
    ("POST", "/api/hotels", "管理员", {"spot_id":1,"name":"E2E Hotel","address":"Test","city":"Test"}, 401, 403, 201),
    ("GET", "/api/hotels/1/rooms", "公开", None, 200, 200, 200),
    ("POST", "/api/hotels/orders", "鉴权", {"hotel_id":1,"room_id":1,"room_count":1,"checkin_date":"2026-12-20","checkout_date":"2026-12-21","guest_name":"Test","guest_phone":"13800138000"}, 401, 201, None),
    ("GET", "/api/hotels/orders", "鉴权", None, 401, 200, None),
    
    # === Dashboard ===
    ("GET", "/api/dashboard/stats", "管理员", None, 401, 403, 200),
]

passed = 0
failed = 0
issues = []

print(f"{'#':>3} {'Method':6} {'Path':<40} {'Level':8} {'NoAuth':>7} {'Guest':>7} {'Admin':>7} {'Result'}")
print("-" * 110)

for i, (method, path, level, data, exp_noauth, exp_guest, exp_admin) in enumerate(endpoints, 1):
    # Test without auth
    s_noauth, _ = call(method, path, data)
    ok_noauth = "✅" if s_noauth == exp_noauth else "❌"
    
    # Test with guest token
    s_guest = "-"
    ok_guest = "  -   "
    if exp_guest is not None:
        s_guest, _ = call(method, path, data, guest_t)
        ok_guest = "✅" if s_guest == exp_guest else "❌"
    
    # Test with admin token
    s_admin = "-"
    ok_admin = "  -   "
    if exp_admin is not None:
        s_admin, _ = call(method, path, data, admin_t)
        ok_admin = "✅" if s_admin == exp_admin else "❌"
    
    line_ok = True
    detail = ""
    if exp_noauth is not None and s_noauth != exp_noauth:
        line_ok = False
        detail += f" NoAuth:{s_noauth}!={exp_noauth}"
    if exp_guest is not None and s_guest != exp_guest:
        line_ok = False
        detail += f" Guest:{s_guest}!={exp_guest}"
    if exp_admin is not None and s_admin != exp_admin:
        line_ok = False
        detail += f" Admin:{s_admin}!={exp_admin}"
    
    if line_ok:
        passed += 1
        status = "✅"
    else:
        failed += 1
        status = "❌"
        issues.append(f"  {i}. {method} {path} ({level}): {detail}")
    
    print(f"{i:>3} {method:6} {path:<40} {level:8} {s_noauth:>3}{ok_noauth} {s_guest:>3}{ok_guest} {s_admin:>3}{ok_admin} {status}")

print("-" * 110)
print(f"\n总计: {passed} 通过, {failed} 失败")

if issues:
    print("\n⚠️  问题列表:")
    for issue in issues:
        print(issue)
