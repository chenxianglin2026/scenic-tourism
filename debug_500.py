#!/usr/bin/env python3
"""Debug 500 errors"""
import json, urllib.request, urllib.error

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
        body = e.read().decode()
        print(f"  HTTP {e.code}: {body[:500]}")
        return e.code, body
    except Exception as e:
        return -1, str(e)

# Login
_, admin = call("POST", "/api/auth/login", {"username":"admin","password":"admin123"})
_, guest = call("POST", "/api/auth/login", {"username":"guest","password":"guest123"})
admin_t = admin["access_token"]
guest_t = guest["access_token"]

print("=== Debug 1: POST /api/hotels (admin creates hotel) ===")
s, r = call("POST", "/api/hotels", {"spot_id":1,"name":"E2E Hotel","address":"Test Addr","city":"Test City"}, admin_t)
print(f"Status: {s}")
if isinstance(r, dict):
    print(f"Response keys: {list(r.keys())}")
else:
    print(f"Response: {r[:500]}")

print("\n=== Debug 2: GET /api/hotels/orders (guest) ===")
s, r = call("GET", "/api/hotels/orders", None, guest_t)
print(f"Status: {s}")
if isinstance(r, dict):
    print(f"Response keys: {list(r.keys())}")
    if "total" in r:
        print(f"Total: {r['total']}, Items count: {len(r.get('items', []))}")
else:
    print(f"Response: {r[:500]}")

print("\n=== Debug 3: Test that hotels.list works ===")
s, r = call("GET", "/api/hotels")
print(f"Status: {s}")
if isinstance(r, list):
    print(f"Hotels count: {len(r)}")
    if r:
        print(f"First hotel: {r[0].get('name')}, has rooms: {'rooms' in r[0]}")
elif isinstance(r, dict):
    print(f"Keys: {list(r.keys())}")
