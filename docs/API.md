# 景区智慧管理系统 - API 文档 v1.0

> 基础 URL: `http://43.163.5.90:8002` (开发) / `https://43.163.5.90/scenic` (生产 HTTPS)
> Swagger UI: `/docs` (FastAPI 自动生成)
> 认证方式: Bearer Token (JWT)

---

## 一、系统端点

### GET /health
健康检查，返回服务状态。

响应: `{ "status": "ok", "app": "景区智慧管理系统", "version": "0.2.0" }`

### GET /
API 总览，列出所有模块路径。

---

## 二、认证模块 `/api/auth`

### POST /api/auth/register - 用户注册
Body: `{ "username": "string", "password": "string", "phone?": "13800138000", "nickname?": "string" }`
响应: TokenResponse (JWT token + 用户信息)

### POST /api/auth/login - 用户登录
Body: `{ "username": "string", "password": "string" }`
响应: TokenResponse

### GET /api/auth/me - 获取当前用户信息 (需登录)
Header: `Authorization: Bearer <token>`
响应: 用户详情 (id, username, phone, role, nickname, avatar_url, is_active)

---

## 三、景区信息模块 `/api/scenic`

### GET /api/scenic/info - 景区完整信息
Query: `spot_id?` (不传返回第一个)
响应: 景区介绍 + 图片 + 开放时间 + 票种列表 + 最新5条公告

### GET /api/scenic/list - 景区列表
Query: `page?` (默认1), `page_size?` (默认200)
响应: `{ total, items: [{ id, name, city, district, is_active, rating }] }`

### PUT /api/scenic/info - 编辑景区信息 (admin)
Body: ScenicInfoUpdate (所有字段可选)

### GET /api/scenic/announcements - 公告列表
Query: `spot_id?`, `category?` (notice/event/maintenance/emergency), `page?`, `page_size?`
响应: `{ total, items: [Announcement] }`

### POST /api/scenic/announcements - 创建公告 (admin)
Body: `{ spot_id, title, content, category?, priority?, expires_at? }`

### PUT /api/scenic/announcements/{id} - 编辑公告 (admin)

### DELETE /api/scenic/announcements/{id} - 删除公告 (admin)

### GET /api/scenic/pois - 导览点位列表
Query: `spot_id?`, `category?`
响应: `[{ id, spot_id, name, category, description, lat, lng, images, audio_url, sort_order }]`

### GET /api/scenic/points - 附近推荐点位 (餐饮/购物/娱乐)
Query: `spot_id?`, `category?` (dining/shopping/entertainment), `page?`, `page_size?`
响应: `{ total, items: [NearbyPoint] }`

### POST /api/scenic/points - 添加附近推荐 (admin)
Body: `{ spot_id, name, category, description?, address?, phone?, lat?, lng?, rating?, price_range?, open_time? }`

### PUT /api/scenic/points/{id} - 编辑附近推荐 (admin)

### DELETE /api/scenic/points/{id} - 删除附近推荐 (admin)

### GET /api/scenic/reviews - 游客评价列表
Query: `spot_id?`, `page?`, `page_size?`
响应: `{ total, items: [Review] }` (评分 + 评论 + 图片)

### POST /api/scenic/reviews - 提交评价 (需登录)
Body: `{ spot_id, rating (1-5), content, images? }`

### GET /api/scenic/weather - 天气信息
Query: `spot_id?`
响应: `{ spot_id, city, temperature, weather, humidity, wind, aqi, update_time, forecast: [] }`

### POST /api/scenic/weather/refresh - 刷新天气缓存 (admin)
Query: `spot_id?`

---

## 四、票务模块 `/api/tickets`

### GET /api/tickets/types - 票种列表
Query: `spot_id?`
响应: `[{ id, spot_id, name, category, price, original_price, daily_stock, description, min_age, max_age, is_active, sort_order }]`

### POST /api/tickets/types - 创建票种 (admin)
Body: `{ spot_id, name, category?, price, original_price?, daily_stock?, description?, min_age?, max_age? }`

### POST /api/tickets/order - 购票下单 (需登录)
Body: `{ ticket_type_id, spot_id, quantity?, visit_date, time_slot, visitor_name?, visitor_phone?, visitor_id_card? }`
- 时间段: "08:00-10:00" / "10:00-12:00" / "12:00-14:00" / "14:00-17:00"
- 库存原子扣减 (乐观锁，防超卖)
- 订单状态: PENDING -> 需调用支付接口

### GET /api/tickets/orders - 我的购票订单 (需登录)
Query: `status?` (pending/paid/verified/cancelled/refunding/refunded/expired), `page?`, `page_size?`
响应: `{ total, items: [TicketOrder] }`

### GET /api/tickets/order/{order_no} - 按订单号查询 (需登录)

### POST /api/tickets/verify - 核销验票 (staff/admin)
Body: `{ qr_token }`
响应: `{ result (success/already_verified/invalid_token/expired/cancelled), message, order? }`
- 校验游览日期必须为当天
- 已核销/已取消/已过期/未支付均拒绝核销

### POST /api/tickets/order/{order_id}/refund - 申请退款 (需登录)
- 未支付 -> 直接取消，释放库存
- 已支付 + 游览日期已过 -> 自动退款
- 已支付 + 未到游览日期 -> 进入审核中 (REFUNDING)，需管理员审核
- 已核销 -> 不可退款

### POST /api/tickets/batch-expire - 批量过期处理 (admin)
将过游览日期但仍为 PAID 状态的订单标记为 EXPIRED 并自动退款

---

## 五、酒店模块 `/api/hotels`

### GET /api/hotels - 酒店列表
Query: `spot_id?`
响应: `[{ id, spot_id, name, address, city, district, phone, description, cover_image, lat, lng, rating, is_active, rooms: [Room] }]`

### POST /api/hotels - 创建酒店 (admin)
Body: `{ spot_id, name, address, city, district?, phone?, description?, cover_image?, lat?, lng? }`

### GET /api/hotels/{hotel_id}/rooms - 酒店房型列表

### POST /api/hotels/{hotel_id}/rooms - 创建房型 (admin)
Body: `{ hotel_id, name, room_type?, price, total_count?, area?, bed_type?, max_guests?, has_window?, has_wifi?, has_bathtub?, description?, images? }`

### POST /api/hotels/orders - 客房预订 (需登录)
Body: `{ hotel_id, room_id, room_count?, checkin_date, checkout_date, guest_name, guest_phone, remark? }`
- 库存原子扣减 (available_count)
- 自动计算天数 + 总价

### GET /api/hotels/orders - 我的客房订单 (需登录)
Query: `status?`, `page?`, `page_size?`

### POST /api/hotels/orders/{order_id}/checkin - 办理入住 (staff/admin)
- 状态流转: PAID -> CHECKED_IN
- 校验入住日期不能晚于今天

### POST /api/hotels/orders/{order_id}/checkout - 办理退房 (staff/admin)
- 状态流转: CHECKED_IN -> COMPLETED
- 自动恢复房间库存

### POST /api/hotels/orders/{order_id}/refund - 申请退款 (需登录)
- 逻辑同票务退款

---

## 六、支付模块 `/api/payment`

### POST /api/payment/create - 创建支付 (需登录)
Body: `{ order_no, order_type (ticket/hotel) }`
响应: `{ success, message, transaction_id, payment_params }`
- 支付超时: 30 分钟自动取消
- DEV_MODE: 返回 mock JSAPI 参数
- 生产模式: 返回微信 JSAPI 参数

### POST /api/payment/confirm - [DEV_MODE] 确认支付
Body: `{ transaction_id, order_no }`
- 仅 DEV_MODE 可用
- 完成 PENDING -> PAID 状态流转
- 幂等: 已支付订单重复确认返回成功
- 超时检测: 超30分钟自动取消

### POST /api/payment/cancel - 取消未支付订单 (需登录)
Body: `{ order_no, order_type }`
- 释放票务/酒店库存

### POST /api/payment/notify - 微信支付回调
Body: `{ transaction_id, order_no, order_type, amount, result_code, raw_data? }`
- 开放接口 (无需认证)
- result_code != "SUCCESS" -> 记录失败
- 更新业务订单: PENDING -> PAID

### GET /api/payment/status/{order_no} - 查询支付状态
Query: `order_type?`
响应: `{ order_no, order_type, transaction_id, status, amount, pay_time, expires_at }`

### POST /api/payment/refund/approve - 审核退款 (admin)
Body: `{ transaction_id, approved, reason? }`
- approved=true: 退款 + 释放库存
- approved=false: 拒绝退款，恢复订单为 PAID

### POST /api/payment/timeout/auto-cancel - 自动取消超时订单 (admin)
手动触发超时检测，批量取消超时未支付订单

---

## 七、仪表盘模块 `/api/dashboard`

### GET /api/dashboard/stats - 完整统计数据 (admin)
Query: `spot_id?`
响应: DashboardStats (票务/酒店/停车营收 + 近7天趋势)

### GET /api/dashboard/revenue - 营收报表 (admin)
Query: `period` (day/week/month), `start_date?`, `end_date?`, `spot_id?`
响应: 按日/周/月聚合的门票+酒店+停车营收

### GET /api/dashboard/overview - 综合总览 (admin)
Query: `spot_id?`
响应: 门票/酒店/停车/评价综合统计数据

---

## 八、停车模块 `/api/parking`

### GET /api/parking/rates - 停车费率列表
Query: `spot_id?`
响应: `[{ id, spot_id, name, vehicle_type, first_hour_price, additional_hour_price, daily_cap, free_minutes, total_spots, available_spots }]`

### POST /api/parking/rates - 添加停车费率 (admin)
Body: `{ spot_id, name, vehicle_type?, first_hour_price?, additional_hour_price?, daily_cap?, free_minutes?, total_spots? }`

### PUT /api/parking/rates/{rate_id} - 编辑停车费率 (admin)

### POST /api/parking/checkin - 车辆入场 (需登录)
Body: `{ rate_id, plate_number, vehicle_type? }`
- 校验车位库存
- 同一车牌不能重复入场

### POST /api/parking/checkout/{record_id} - 车辆出场缴费 (需登录)
Body: `{ pay_method? }`
- 自动计算停车时长 + 费用 (免费时长15分钟)
- 恢复车位库存

### GET /api/parking/records - 我的停车记录 (需登录)
Query: `status?`, `page?`, `page_size?`

### GET /api/parking/records/all - 全部停车记录 (admin)
Query: `plate_number?`, `status?`, `page?`, `page_size?`

---

## 九、数据导出模块 `/api/export`

### GET /api/export/tickets - 导出票务数据 CSV (admin)
Query: `start_date?`, `end_date?`, `spot_id?`, `ticket_type_id?`, `status?`
响应: CSV 文件流

### GET /api/export/revenue - 导出营收报表 CSV (admin)
Query: `period` (day/week/month), `start_date?`, `end_date?`, `spot_id?`
响应: CSV 文件流

### GET /api/export/parking - 导出停车记录 CSV (admin)
Query: `start_date?`, `end_date?`, `spot_id?`, `plate_number?`, `status?`
响应: CSV 文件流

---

## 十、OTA 对接模块 `/api/ota`

### GET /api/ota/configs - OTA渠道配置列表 (admin)
### GET /api/ota/configs/{platform} - 单个渠道配置 (admin)
platform: ctrip / meituan / fliggy

### PUT /api/ota/configs/{platform} - 更新渠道配置 (admin)
Body: `{ platform, api_key?, api_secret?, hotel_id?, spot_id?, is_enabled?, sync_interval_minutes?, webhook_url? }`

### POST /api/ota/orders/push - 接收OTA推送订单 (开放接口)
Body: `{ platform, channel_order_no, action (create/cancel/modify), product_type (ticket/hotel), payload }`
- OTA 平台主动回调本系统的核心接口
- 幂等安全

### GET /api/ota/orders - OTA订单列表 (admin)
Query: `platform?`, `status?`, `page?`, `page_size?`

### POST /api/ota/stock/sync - 单产品库存同步 (admin)
Body: `{ platform, product_type (ticket/room), product_id, available_stock }`

### POST /api/ota/stock/batch-sync - 批量库存同步 (admin)
Body: `{ platform, product_type?, spot_id? }`
同步指定平台所有产品库存到各OTA

### GET /api/ota/revenue - OTA渠道营收报表 (admin)
Query: `platform?`, `start_date?`, `end_date?`
响应: 各OTA平台的订单数/营收/佣金/净收入

---

## 十一、角色权限

| 角色 | 权限范围 |
|------|---------|
| guest | 注册/登录、浏览景区、购票、订房、停车、支付、退款申请 |
| staff | guest权限 + 核销验票、办理入住/退房 |
| admin | 全部权限 (管理配置、仪表盘、数据导出、OTA管理) |

---

## 十二、通用约定

- 所有 API 返回 JSON
- 时间格式: ISO 8601 (如 `2026-01-15T09:30:00`)
- 日期格式: `YYYY-MM-DD`
- 金额单位: 人民币元，保留两位小数
- 分页: `page` 从 1 开始，`page_size` 默认 20，上限 100
- Python 关键字: `lat`/`lng`/`enabled` (非 latitude/longitude/enable)
