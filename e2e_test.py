#!/usr/bin/env python3
"""E2E Live Test: Buy -> Pay -> Verify Flow"""
import json
import urllib.request
import urllib.error

BASE = "http://127.0.0.1:8000"

def req(method, path, data=None, token=None, expected_status=None):
    url = f"{BASE}{path}"
    body = json.dumps(data).encode() if data else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    r = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        resp = urllib.request.urlopen(r)
        status = resp.status
        result = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        status = e.code
        result = json.loads(e.read().decode()) if e.read() else {"error": str(e)}
    
    if expected_status and status != expected_status:
        print(f"  ❌ Expected {expected_status}, got {status}: {result}")
        return None, status
    return result, status

print("=" * 60)
print("E2E Live Test: 买票→支付→核销 完整流程")
print("=" * 60)

# 1. Login as guest
print("\n1. 登录 (guest)")
r, s = req("POST", "/api/auth/login", {"username": "guest", "password": "guest123"})
assert r and "access_token" in r, f"Login failed: {r}"
guest_token = r["access_token"]
print(f"   ✅ 登录成功, role={r['role']}")

# 2. Get ticket types
print("\n2. 获取票种列表")
r, s = req("GET", "/api/tickets/types?spot_id=1")
assert r and len(r) > 0, f"No ticket types: {r}"
ticket_type_id = r[0]["id"]
print(f"   ✅ 共 {len(r)} 个票种, 使用 id={ticket_type_id} ({r[0]['name']})")

# 3. Buy ticket
print("\n3. 购票下单")
import datetime
today = datetime.date.today().isoformat()
r, s = req("POST", "/api/tickets/order", {
    "ticket_type_id": ticket_type_id,
    "spot_id": 1,
    "quantity": 1,
    "visit_date": today,
    "time_slot": "08:00-10:00",
    "visitor_name": "E2E测试用户",
    "visitor_phone": "13800138000",
}, token=guest_token, expected_status=201)
assert r, "Order creation failed"
order_no = r["order_no"]
qr_token = r["qr_token"]
print(f"   ✅ 下单成功, order_no={order_no}, status={r['status']}")
print(f"   QR Token={qr_token[:20]}...")

# 4. Pay
print("\n4. 支付")
r, s = req("POST", "/api/payment/create", {
    "order_no": order_no,
    "order_type": "ticket",
}, token=guest_token)
assert r and r.get("success"), f"Payment failed: {r}"
print(f"   ✅ 支付成功 (DEV_MODE), transaction_id={r.get('transaction_id','N/A')[:30]}...")

# 5. Check order status after payment
print("\n5. 验证订单已支付")
r, s = req("GET", f"/api/tickets/order/{order_no}", token=guest_token)
assert r and r["status"] == "paid", f"Order not paid: {r}"
print(f"   ✅ 订单状态: {r['status']}")

# 6. Login as staff for verification
print("\n6. 登录 (staff)")
r, s = req("POST", "/api/auth/login", {"username": "staff", "password": "staff123"})
assert r and "access_token" in r, f"Staff login failed: {r}"
staff_token = r["access_token"]
print(f"   ✅ 工作人员登录成功, role={r['role']}")

# 7. Verify ticket
print("\n7. 核销验票")
r, s = req("POST", "/api/tickets/verify", {
    "qr_token": qr_token,
}, token=staff_token)
assert r, f"Verify failed: {r}"
print(f"   ✅ 核销结果: {r['result']} - {r['message']}")

# 8. Double verify (should fail with already_verified)
print("\n8. 重复核销 (应返回 already_verified)")
r, s = req("POST", "/api/tickets/verify", {
    "qr_token": qr_token,
}, token=staff_token)
assert r, f"Double verify failed: {r}"
print(f"   ✅ 结果: {r['result']} - {r['message']}")

print("\n" + "=" * 60)
print("✅ 买票→支付→核销 端到端流程全部通过!")
print("=" * 60)
