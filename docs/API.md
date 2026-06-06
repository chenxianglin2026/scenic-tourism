# 景区智慧管理系统 API 文档

> 总计 49 个端点 | 基础地址: `http://127.0.0.1:8000` | OpenAPI: `/docs`

---

## 1. 认证模块 (Auth) — 3 个端点

### 1.1 用户注册
```
POST /api/auth/register
鉴权: 无
```

**请求参数:**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| username | string | 是 | 用户名, 2-50字符 |
| password | string | 是 | 密码, 6-128字符 |
| phone | string | 否 | 手机号, 1[3-9]开头 |
| nickname | string | 否 | 昵称 |

**响应示例:**
```json
{
  "access_token": "eyJhbGciOi...",
  "token_type": "bearer",
  "user_id": 1,
  "username": "zhangsan",
  "role": "guest",
  "nickname": "张三"
}
```

---

### 1.2 用户登录
```
POST /api/auth/login
鉴权: 无
```

**请求参数:**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| username | string | 是 | 用户名 |
| password | string | 是 | 密码 |

**响应示例:**
```json
{
  "access_token": "eyJhbGciOi...",
  "token_type": "bearer",
  "user_id": 1,
  "username": "admin",
  "role": "admin",
  "nickname": "系统管理员"
}
```

---

### 1.3 获取当前用户信息
```
GET /api/auth/me
鉴权: Bearer Token (登录用户)
```

**响应示例:**
```json
{
  "id": 1,
  "username": "admin",
  "phone": "13800138000",
  "role": "admin",
  "nickname": "系统管理员",
  "avatar_url": null,
  "is_active": true
}
```

---

## 2. 景区信息模块 (Scenic) — 14 个端点

### 2.1 获取景区完整信息
```
GET /api/scenic/info
鉴权: 无
```

**请求参数:**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| spot_id | int | 否 | 景区ID，不传返回第一个 |

**响应示例:**
```json
{
  "id": 1,
  "name": "西湖风景名胜区",
  "address": "杭州市西湖区龙井路1号",
  "city": "杭州",
  "district": "西湖区",
  "phone": "0571-88886666",
  "description": "杭州西湖，人间天堂",
  "cover_image": null,
  "images": "[\"img1.jpg\",\"img2.jpg\"]",
  "lat": 30.2375,
  "lng": 120.1398,
  "open_time": "08:00",
  "close_time": "17:30",
  "daily_limit": 50000,
  "rating": 4.8,
  "is_active": true,
  "ticket_types": [
    {
      "id": 1,
      "name": "成人票",
      "category": "standard",
      "price": 80.0,
      "original_price": 100.0,
      "daily_stock": 30000,
      "description": "适用于18-60周岁的成人",
      "min_age": 18,
      "max_age": 60
    }
  ],
  "latest_announcements": [
    {
      "id": 1,
      "title": "五一期间限流通知",
      "content": "五一期间每日限流5万人...",
      "category": "notice",
      "priority": 2,
      "published_at": "2026-04-25T10:00:00",
      "expires_at": "2026-05-05T23:59:59"
    }
  ]
}
```

---

### 2.2 公告列表
```
GET /api/scenic/announcements
鉴权: 无
```

**请求参数:**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| spot_id | int | 否 | 景区ID |
| category | string | 否 | notice/event/maintenance/emergency |
| page | int | 否 | 页码, 默认1 |
| page_size | int | 否 | 每页条数, 默认20, 最大100 |

**响应示例:**
```json
{
  "total": 10,
  "items": [
    {
      "id": 1,
      "spot_id": 1,
      "title": "五一期间限流通知",
      "content": "五一期间每日限流5万人...",
      "category": "notice",
      "priority": 2,
      "is_published": true,
      "published_at": "2026-04-25T10:00:00",
      "expires_at": "2026-05-05T23:59:59",
      "created_at": "2026-04-25T09:30:00"
    }
  ]
}
```

---

### 2.3 创建公告
```
POST /api/scenic/announcements
鉴权: admin
```

**请求参数:**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| spot_id | int | 是 | 景区ID |
| title | string | 是 | 标题, 1-200字符 |
| content | string | 是 | 内容 |
| category | string | 否 | notice/event/maintenance/emergency, 默认notice |
| priority | int | 否 | 0-低 1-中 2-高, 默认0 |
| expires_at | datetime | 否 | 过期时间 |

**响应示例:**
```json
{
  "id": 2,
  "spot_id": 1,
  "title": "新公告",
  "content": "内容...",
  "category": "notice",
  "priority": 0,
  "is_published": true,
  "published_at": "2026-06-06T12:00:00",
  "expires_at": null,
  "created_at": "2026-06-06T12:00:00"
}
```

---

### 2.4 编辑公告
```
PUT /api/scenic/announcements/{announcement_id}
鉴权: admin
```

**请求参数 (全部可选):**
| 参数 | 类型 | 说明 |
|------|------|------|
| title | string | 标题 |
| content | string | 内容 |
| category | string | 分类 |
| priority | int | 优先级 |
| is_published | bool | 是否发布 |
| expires_at | datetime | 过期时间 |

---

### 2.5 删除公告
```
DELETE /api/scenic/announcements/{announcement_id}
鉴权: admin
```

**响应示例:**
```json
{"success": true, "message": "公告已删除"}
```

---

### 2.6 导览点位列表 (POI)
```
GET /api/scenic/pois
鉴权: 无
```

**请求参数:**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| spot_id | int | 否 | 景区ID |
| category | string | 否 | 点位分类 |

**响应示例:**
```json
[
  {
    "id": 1,
    "spot_id": 1,
    "name": "断桥残雪",
    "category": "景点",
    "description": "西湖十景之一",
    "lat": 30.2536,
    "lng": 120.1453,
    "images": null,
    "audio_url": null,
    "sort_order": 1,
    "is_active": true
  }
]
```

---

### 2.7 编辑景区信息
```
PUT /api/scenic/info
鉴权: admin
```

**请求参数 (全部可选):**
| 参数 | 类型 | 说明 |
|------|------|------|
| name | string | 景区名称 |
| address | string | 地址 |
| city | string | 城市 |
| district | string | 区县 |
| phone | string | 电话 |
| description | string | 介绍 |
| cover_image | string | 封面图 |
| images | string | 图片JSON |
| lat | float | 纬度 |
| lng | float | 经度 |
| open_time | string | 开放时间 |
| close_time | string | 关闭时间 |
| daily_limit | int | 日限流 |
| rating | float | 评分0-5 |
| is_active | bool | 启用 |

**响应示例:** 同 2.1 景区信息

---

### 2.8 景区附近推荐点位
```
GET /api/scenic/points
鉴权: 无
```

**请求参数:**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| spot_id | int | 否 | 景区ID |
| category | string | 否 | dining/shopping/entertainment |
| page | int | 否 | 页码, 默认1 |
| page_size | int | 否 | 每页条数, 默认20, 最大100 |

**响应示例:**
```json
{
  "total": 15,
  "items": [
    {
      "id": 1,
      "spot_id": 1,
      "name": "楼外楼",
      "category": "dining",
      "description": "百年老字号杭帮菜",
      "address": "孤山路30号",
      "phone": "0571-87969023",
      "lat": 30.2460,
      "lng": 120.1405,
      "rating": 4.5,
      "images": null,
      "distance": 1.2,
      "price_range": "人均80-150元",
      "open_time": "10:30-21:00",
      "sort_order": 1,
      "is_active": true
    }
  ]
}
```

---

### 2.9 添加附近推荐点位
```
POST /api/scenic/points
鉴权: admin
```

**请求参数:**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| spot_id | int | 是 | 景区ID |
| name | string | 是 | 名称, 1-200字符 |
| category | string | 否 | dining/shopping/entertainment, 默认dining |
| description | string | 否 | 描述 |
| address | string | 否 | 地址 |
| phone | string | 否 | 电话 |
| lat | float | 否 | 纬度 |
| lng | float | 否 | 经度 |
| rating | float | 否 | 评分1-5, 默认4.0 |
| images | string | 否 | 图片JSON |
| distance | float | 否 | 距离(公里) |
| price_range | string | 否 | 人均价格区间 |
| open_time | string | 否 | 营业时间 |
| sort_order | int | 否 | 排序, 默认0 |

**响应示例:** 同 2.8 单条item

---

### 2.10 编辑附近推荐点位
```
PUT /api/scenic/points/{point_id}
鉴权: admin
```

**请求参数:** 同 2.9 全部可选, 额外支持 is_active

---

### 2.11 游客评价列表
```
GET /api/scenic/reviews
鉴权: 无
```

**请求参数:**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| spot_id | int | 否 | 景区ID |
| rating | int | 否 | 按评分过滤 1-5 |
| page | int | 否 | 页码, 默认1 |
| page_size | int | 否 | 每页条数, 默认20, 最大100 |

**响应示例:**
```json
{
  "total": 128,
  "items": [
    {
      "id": 1,
      "spot_id": 1,
      "user_id": 5,
      "username": "zhangsan",
      "nickname": "张三",
      "avatar_url": null,
      "rating": 5,
      "content": "景色非常美，推荐！",
      "images": "[\"review1.jpg\"]",
      "is_approved": true,
      "like_count": 12,
      "visit_date": "2026-05-15",
      "created_at": "2026-05-15T16:30:00"
    }
  ],
  "avg_rating": 4.6,
  "rating_distribution": {"5": 80, "4": 30, "3": 12, "2": 4, "1": 2}
}
```

---

### 2.12 发表评价
```
POST /api/scenic/reviews
鉴权: Bearer Token (登录用户)
```

**请求参数:**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| spot_id | int | 是 | 景区ID |
| rating | int | 是 | 评分 1-5 |
| content | string | 是 | 评价内容, 5-2000字符 |
| images | string | 否 | 图片JSON数组 |
| visit_date | date | 否 | 游览日期 |

**响应示例:** 同 2.11 单条item

---

### 2.13 删除评价
```
DELETE /api/scenic/reviews/{review_id}
鉴权: admin
```

**响应示例:**
```json
{"success": true, "message": "评价已删除"}
```

---

### 2.14 景区天气
```
GET /api/scenic/weather
鉴权: 无
```

**请求参数:**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| spot_id | int | 否 | 景区ID，不传返回第一个 |

**响应示例:**
```json
{
  "spot_id": 1,
  "city": "杭州",
  "temperature": 25.5,
  "weather": "晴",
  "humidity": 65,
  "wind": "东南风2级",
  "aqi": 52,
  "update_time": "2026-06-06 12:00",
  "forecast": [
    {"date": "2026-06-06", "weather": "晴", "temp_high": 30.0, "temp_low": 20.0},
    {"date": "2026-06-07", "weather": "多云", "temp_high": 27.0, "temp_low": 17.0},
    {"date": "2026-06-08", "weather": "阴", "temp_high": 30.5, "temp_low": 20.5}
  ]
}
```

---

## 3. 票务模块 (Tickets) — 8 个端点

### 3.1 票种列表
```
GET /api/tickets/types
鉴权: 无
```

**请求参数:**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| spot_id | int | 否 | 景区ID |

**响应示例:**
```json
[
  {
    "id": 1,
    "spot_id": 1,
    "name": "成人票",
    "category": "standard",
    "price": 80.0,
    "original_price": 100.0,
    "daily_stock": 30000,
    "description": "适用于18-60周岁",
    "min_age": 18,
    "max_age": 60,
    "is_active": true,
    "sort_order": 1
  }
]
```

---

### 3.2 创建票种
```
POST /api/tickets/types
鉴权: admin
```

**请求参数:**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| spot_id | int | 是 | 景区ID |
| name | string | 是 | 票种名称 |
| category | string | 否 | 分类, 默认standard |
| price | float | 是 | 售价, >0 |
| original_price | float | 否 | 原价 |
| daily_stock | int | 否 | 日库存, 默认1000 |
| description | string | 否 | 说明 |
| min_age | int | 否 | 最小年龄 |
| max_age | int | 否 | 最大年龄 |

---

### 3.3 购票下单
```
POST /api/tickets/order
鉴权: Bearer Token (登录用户)
```

**请求参数:**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| ticket_type_id | int | 是 | 票种ID |
| spot_id | int | 是 | 景区ID |
| quantity | int | 否 | 数量1-20, 默认1 |
| visit_date | date | 是 | 游览日期 |
| time_slot | string | 是 | 时间段: 08:00-10:00 / 10:00-12:00 / 12:00-14:00 / 14:00-17:00 |
| visitor_name | string | 否 | 游客姓名 |
| visitor_phone | string | 否 | 游客电话 |
| visitor_id_card | string | 否 | 游客身份证 |

**响应示例:**
```json
{
  "id": 100,
  "order_no": "20260606120000A1B2C3",
  "user_id": 5,
  "ticket_type_id": 1,
  "ticket_type_name": "成人票",
  "spot_id": 1,
  "spot_name": "西湖风景名胜区",
  "quantity": 2,
  "visit_date": "2026-06-10",
  "time_slot": "08:00-10:00",
  "total_price": 160.0,
  "status": "PENDING",
  "qr_token": "abcdef123456...",
  "visitor_name": "张三",
  "visitor_phone": "13800138000",
  "verified_at": null,
  "paid_at": null,
  "cancelled_at": null,
  "created_at": "2026-06-06T12:00:00"
}
```

---

### 3.4 我的购票订单
```
GET /api/tickets/orders
鉴权: Bearer Token (登录用户)
```

**请求参数:**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| status | string | 否 | PENDING/PAID/VERIFIED/CANCELLED/EXPIRED/REFUNDED |
| page | int | 否 | 页码, 默认1 |
| page_size | int | 否 | 每页条数, 默认20, 最大100 |

**响应示例:**
```json
{
  "total": 5,
  "items": [ /* 同 3.3 单条订单结构 */ ]
}
```

---

### 3.5 核销验票
```
POST /api/tickets/verify
鉴权: staff / admin
```

**请求参数:**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| qr_token | string | 是 | 票二维码token |

**响应示例:**
```json
{
  "result": "success",
  "message": "核销成功",
  "order": { "id": 100, "order_no": "...", ... }
}
```
result 可能值: `success` / `already_verified` / `invalid_token` / `expired` / `cancelled`

---

### 3.6 申请退款
```
POST /api/tickets/order/{order_id}/refund
鉴权: Bearer Token (登录用户)
```

**响应示例:**
```json
{
  "success": true,
  "message": "退款成功，已退还 ¥160.00",
  "order": { ... },
  "refund_amount": 160.0
}
```

---

### 3.7 按订单号查询
```
GET /api/tickets/order/{order_no}
鉴权: Bearer Token (登录用户)
```

**响应示例:** 同 3.3 单条订单

---

### 3.8 批量过期处理
```
POST /api/tickets/batch-expire
鉴权: admin
```

**响应示例:**
```json
{
  "success": true,
  "message": "已处理 3 张过期票",
  "expired_count": 3
}
```

---

## 4. 酒店模块 (Hotels) — 10 个端点

### 4.1 酒店列表
```
GET /api/hotels
鉴权: 无
```

**请求参数:**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| spot_id | int | 否 | 景区ID |

**响应示例:**
```json
[
  {
    "id": 1,
    "spot_id": 1,
    "name": "西湖国宾馆",
    "address": "杨公堤18号",
    "city": "杭州",
    "district": "西湖区",
    "phone": "0571-87979889",
    "description": "西湖畔五星级酒店",
    "cover_image": null,
    "images": null,
    "lat": 30.2350,
    "lng": 120.1310,
    "rating": 4.8,
    "is_active": true,
    "rooms": [
      {
        "id": 1,
        "hotel_id": 1,
        "name": "湖景大床房",
        "room_type": "大床房",
        "price": 1280.0,
        "total_count": 20,
        "available_count": 15,
        "area": 45.0,
        "bed_type": "1.8m大床",
        "max_guests": 2,
        "has_window": true,
        "has_wifi": true,
        "has_bathtub": true,
        "description": "直面西湖",
        "images": null,
        "is_active": true
      }
    ]
  }
]
```

---

### 4.2 创建酒店
```
POST /api/hotels
鉴权: admin
```

**请求参数:**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| spot_id | int | 是 | 景区ID |
| name | string | 是 | 酒店名称 |
| address | string | 是 | 地址 |
| city | string | 是 | 城市 |
| district | string | 否 | 区县 |
| phone | string | 否 | 电话 |
| description | string | 否 | 介绍 |
| cover_image | string | 否 | 封面图 |
| lat | float | 否 | 纬度 |
| lng | float | 否 | 经度 |

---

### 4.3 酒店房型列表
```
GET /api/hotels/{hotel_id}/rooms
鉴权: 无
```

**响应示例:** 同 4.1 中 rooms 数组元素

---

### 4.4 创建房型
```
POST /api/hotels/{hotel_id}/rooms
鉴权: admin
```

**请求参数:**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| hotel_id | int | 是 | (URL路径中已包含) |
| name | string | 是 | 房型名称 |
| room_type | string | 否 | 类型, 默认"大床房" |
| price | float | 是 | 价格/晚, >0 |
| total_count | int | 否 | 总间数, 默认10 |
| area | float | 否 | 面积(m²) |
| bed_type | string | 否 | 床型 |
| max_guests | int | 否 | 最大入住人数, 默认2 |
| has_window | bool | 否 | 有窗, 默认true |
| has_wifi | bool | 否 | 有WiFi, 默认true |
| has_bathtub | bool | 否 | 有浴缸, 默认false |
| description | string | 否 | 描述 |
| images | string | 否 | 图片 |

---

### 4.5 客房预订
```
POST /api/hotels/orders
鉴权: Bearer Token (登录用户)
```

**请求参数:**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| hotel_id | int | 是 | 酒店ID |
| room_id | int | 是 | 房型ID |
| room_count | int | 否 | 房间数1-10, 默认1 |
| checkin_date | date | 是 | 入住日期 |
| checkout_date | date | 是 | 离店日期 |
| guest_name | string | 是 | 入住人姓名 |
| guest_phone | string | 是 | 手机号, 1[3-9]开头 |
| remark | string | 否 | 备注 |

**响应示例:**
```json
{
  "id": 50,
  "order_no": "20260606120000XYZ789",
  "hotel_id": 1,
  "hotel_name": "西湖国宾馆",
  "room_id": 1,
  "room_name": "湖景大床房",
  "room_count": 1,
  "checkin_date": "2026-06-10",
  "checkout_date": "2026-06-12",
  "nights": 2,
  "total_price": 2560.0,
  "status": "PENDING",
  "guest_name": "张三",
  "guest_phone": "13800138000",
  "remark": null,
  "cancel_reason": null,
  "paid_at": null,
  "cancelled_at": null,
  "created_at": "2026-06-06T12:00:00"
}
```

---

### 4.6 我的客房订单
```
GET /api/hotels/orders
鉴权: Bearer Token (登录用户)
```

**请求参数:**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| status | string | 否 | PENDING/PAID/CHECKED_IN/COMPLETED/CANCELLED/REFUNDED |
| page | int | 否 | 页码, 默认1 |
| page_size | int | 否 | 每页条数, 默认20, 最大100 |

**响应示例:**
```json
{
  "total": 3,
  "items": [ /* 同 4.5 单条订单结构 */ ]
}
```

---

### 4.7 办理入住
```
POST /api/hotels/orders/{order_id}/checkin
鉴权: staff / admin
```

**响应示例:**
```json
{
  "success": true,
  "message": "入住办理成功",
  "order": { "id": 50, "status": "CHECKED_IN", ... }
}
```

---

### 4.8 办理退房
```
POST /api/hotels/orders/{order_id}/checkout
鉴权: staff / admin
```

**响应示例:**
```json
{
  "success": true,
  "message": "退房办理成功，房间库存已恢复",
  "order": { "id": 50, "status": "COMPLETED", ... }
}
```

---

### 4.9 申请退款
```
POST /api/hotels/orders/{order_id}/refund
鉴权: Bearer Token (登录用户)
```

**响应示例:**
```json
{
  "success": true,
  "message": "退款成功，已退还 ¥2560.00，库存已恢复",
  "order": { ... },
  "refund_amount": 2560.0
}
```

---

### 4.10 按订单号查询
```
GET /api/hotels/orders/detail/{order_no}
鉴权: Bearer Token (登录用户)
```

**响应示例:** 同 4.5 单条订单

---

## 5. 停车模块 (Parking) — 8 个端点

### 5.1 停车费率列表
```
GET /api/parking/rates
鉴权: 无
```

**请求参数:**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| spot_id | int | 否 | 景区ID |

**响应示例:**
```json
[
  {
    "id": 1,
    "spot_id": 1,
    "name": "景区主停车场",
    "vehicle_type": "car",
    "first_hour_price": 5.0,
    "additional_hour_price": 3.0,
    "daily_cap": 30.0,
    "free_minutes": 15,
    "total_spots": 200,
    "available_spots": 145,
    "open_time": "00:00",
    "close_time": "24:00",
    "is_active": true
  }
]
```

---

### 5.2 添加停车费率
```
POST /api/parking/rates
鉴权: admin
```

**请求参数:**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| spot_id | int | 是 | 景区ID |
| name | string | 是 | 停车场名称 |
| vehicle_type | string | 否 | car/bus/truck/motorcycle, 默认car |
| first_hour_price | float | 否 | 首小时价格, 默认5.0 |
| additional_hour_price | float | 否 | 续时价格, 默认3.0 |
| daily_cap | float | 否 | 每日封顶, 默认30.0 |
| free_minutes | int | 否 | 免费分钟数, 默认15 |
| total_spots | int | 否 | 总车位数, 默认200 |
| available_spots | int | 否 | 可用车位数, 默认=total_spots |
| open_time | string | 否 | 营业开始, 默认"00:00" |
| close_time | string | 否 | 营业结束, 默认"24:00" |

---

### 5.3 编辑停车费率
```
PUT /api/parking/rates/{rate_id}
鉴权: admin
```

**请求参数:** 同 5.2 全部可选, 额外支持 is_active

---

### 5.4 停车入场
```
POST /api/parking/checkin
鉴权: Bearer Token (登录用户)
```

**请求参数:**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| rate_id | int | 是 | 停车场费率ID |
| plate_number | string | 是 | 车牌号, 1-20字符 |
| vehicle_type | string | 否 | car/bus/truck/motorcycle, 默认car |

**响应示例:**
```json
{
  "success": true,
  "message": "车辆 浙A12345 入场成功",
  "record": {
    "id": 30,
    "rate_id": 1,
    "parking_name": "景区主停车场",
    "user_id": 5,
    "plate_number": "浙A12345",
    "vehicle_type": "car",
    "checkin_time": "2026-06-06T10:00:00",
    "status": "parking",
    "pay_status": "unpaid",
    "created_at": "2026-06-06T10:00:00"
  },
  "record_id": 30
}
```

---

### 5.5 停车出场缴费
```
POST /api/parking/checkout/{record_id}
鉴权: Bearer Token (登录用户)
```

**请求参数:**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| pay_method | string | 否 | wechat/alipay/cash, 默认wechat |

**响应示例:**
```json
{
  "success": true,
  "message": "出场成功，停车 120 分钟，费用 ¥11.00",
  "record": {
    "id": 30,
    "rate_id": 1,
    "parking_name": "景区主停车场",
    "plate_number": "浙A12345",
    "checkin_time": "2026-06-06T10:00:00",
    "checkout_time": "2026-06-06T12:00:00",
    "duration_minutes": 120,
    "total_fee": 11.0,
    "status": "completed",
    "pay_status": "paid",
    "pay_method": "wechat",
    "paid_at": "2026-06-06T12:00:00"
  },
  "duration_minutes": 120,
  "total_fee": 11.0
}
```

---

### 5.6 我的停车记录
```
GET /api/parking/records
鉴权: Bearer Token (登录用户)
```

**请求参数:**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| status | string | 否 | parking/completed |
| page | int | 否 | 页码, 默认1 |
| page_size | int | 否 | 每页条数, 默认20, 最大100 |

**响应示例:**
```json
{
  "total": 5,
  "items": [ /* 同 5.5 中 record 结构 */ ]
}
```

---

### 5.7 全部停车记录（管理员）
```
GET /api/parking/records/all
鉴权: admin
```

**请求参数:**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| plate_number | string | 否 | 车牌号模糊搜索 |
| status | string | 否 | parking/completed |
| page | int | 否 | 页码, 默认1 |
| page_size | int | 否 | 每页条数, 默认20, 最大100 |

---

### 5.8 （无 URL 路径的额外端点: 实际上停车模块共7个独立路由 + /rates POST/PUT = 7+2 = 但计数时 /rates 的 GET/POST/PUT 是3个，checkin/checkout 是2个，/records 和 /records/all 是2个，共7个）

---

## 6. 支付模块 (Payment) — 3 个端点

### 6.1 创建支付
```
POST /api/payment/create
鉴权: Bearer Token (登录用户)
```

**请求参数:**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| order_no | string | 是 | 订单号（票务或酒店） |
| order_type | string | 是 | ticket / hotel |

**响应示例:**
```json
{
  "success": true,
  "message": "[DEV_MODE] 支付模拟成功，¥160.00",
  "payment_params": {
    "appId": "wx_dev_mock_appid",
    "timeStamp": "1717660800",
    "nonceStr": "abc123def456...",
    "package": "prepay_id=prepay_abc...",
    "signType": "MD5",
    "paySign": "MOCK_SIGNATURE"
  },
  "transaction_id": "WX20260606120000A1B2C3D4E5"
}
```

---

### 6.2 微信支付回调通知
```
POST /api/payment/notify
鉴权: 无 (微信回调)
```

**请求参数:**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| transaction_id | string | 是 | 微信支付交易号 |
| order_no | string | 是 | 商户订单号 |
| order_type | string | 否 | ticket / hotel, 默认ticket |
| amount | float | 是 | 支付金额(元) |
| result_code | string | 否 | SUCCESS / FAIL, 默认SUCCESS |
| raw_data | string | 否 | 回调原始数据 |

**响应示例:**
```json
{"return_code": "SUCCESS", "return_msg": "OK"}
```

---

### 6.3 查询支付状态
```
GET /api/payment/status/{order_no}
鉴权: Bearer Token (登录用户)
```

**响应示例:**
```json
{
  "order_no": "20260606120000A1B2C3",
  "order_type": "ticket",
  "transaction_id": "WX20260606120000A1B2C3D4E5",
  "status": "success",
  "amount": 160.0,
  "pay_time": "2026-06-06T12:00:01"
}
```

---

## 7. 仪表盘模块 (Dashboard) — 2 个端点

### 7.1 仪表盘统计数据
```
GET /api/dashboard/stats
鉴权: admin
```

**请求参数:**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| spot_id | int | 否 | 景区ID |

**响应示例:**
```json
{
  "code": 0,
  "data": {
    "spot_id": 1,
    "spot_name": "西湖风景名胜区",
    "total_ticket_types": 4,
    "tickets_sold_today": 1200,
    "tickets_verified_today": 980,
    "ticket_revenue_today": 96000.0,
    "total_hotels": 5,
    "total_rooms": 200,
    "occupied_rooms": 45,
    "hotel_revenue_today": 57600.0,
    "total_revenue_today": 153600.0,
    "ticket_revenue_trend": [
      {"date": "2026-05-31", "value": 86000.0, "label": "5/31"},
      {"date": "2026-06-01", "value": 92000.0, "label": "6/1"}
    ],
    "tickets_sold_trend": [
      {"date": "2026-05-31", "value": 1050, "label": "5/31"},
      {"date": "2026-06-01", "value": 1180, "label": "6/1"}
    ]
  },
  "msg": "ok"
}
```

---

### 7.2 营收报表
```
GET /api/dashboard/revenue
鉴权: admin
```

**请求参数:**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| period | string | 否 | day/week/month, 默认day |
| start_date | string | 否 | 起始日期 YYYY-MM-DD, 默认30天前 |
| end_date | string | 否 | 结束日期 YYYY-MM-DD, 默认今天 |
| spot_id | int | 否 | 景区ID |

**响应示例:**
```json
{
  "code": 0,
  "msg": "ok",
  "data": {
    "period": "day",
    "start_date": "2026-05-07",
    "end_date": "2026-06-06",
    "spot_id": null,
    "summary": {
      "ticket_revenue": 2850000.0,
      "hotel_revenue": 1680000.0,
      "parking_revenue": 45000.0,
      "total_revenue": 4575000.0
    },
    "items": [
      {
        "date": "2026-06-06",
        "ticket_revenue": 96000.0,
        "hotel_revenue": 57600.0,
        "parking_revenue": 1500.0,
        "total_revenue": 155100.0
      }
    ]
  }
}
```

---

## 8. 系统模块 (System) — 2 个端点

### 8.1 健康检查
```
GET /health
鉴权: 无
```

**响应示例:**
```json
{
  "status": "ok",
  "app": "景区智慧管理系统",
  "version": "1.0.0"
}
```

---

### 8.2 根路径
```
GET /
鉴权: 无
```

**响应示例:**
```json
{
  "app": "景区智慧管理系统",
  "api": {
    "auth": "/api/auth",
    "tickets": "/api/tickets",
    "hotels": "/api/hotels",
    "payment": "/api/payment",
    "scenic": "/api/scenic",
    "parking": "/api/parking",
    "dashboard": "/api/dashboard"
  },
  "docs": "/docs"
}
```

---

## 附录

### 鉴权说明
- **无**: 公开接口, 无需鉴权
- **Bearer Token (登录用户)**: 请求头 `Authorization: Bearer <token>`, 通过 `/api/auth/login` 或 `/api/auth/register` 获取
- **staff**: 工作人员角色（含admin）, 权限高于普通用户
- **admin**: 管理员角色, 最高权限

### 通用响应格式
- 成功: HTTP 2xx + JSON body
- 业务错误: HTTP 4xx + `{"detail": "错误描述"}`
- 认证失败: HTTP 401 + `{"detail": "无效的认证凭据"}`
- 权限不足: HTTP 403 + `{"detail": "需要管理员权限"}`

### 端点统计
| 模块 | 端点数量 |
|------|---------|
| 认证 (Auth) | 3 |
| 景区 (Scenic) | 14 |
| 票务 (Tickets) | 8 |
| 酒店 (Hotels) | 10 |
| 停车 (Parking) | 7 |
| 支付 (Payment) | 3 |
| 仪表盘 (Dashboard) | 2 |
| 系统 (System) | 2 |
| **总计** | **49** |
