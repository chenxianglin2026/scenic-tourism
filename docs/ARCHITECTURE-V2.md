# 景区智慧管理系统 — 架构升级方案 V2

> 版本: v2.0  
> 日期: 2026-06-06  
> 作者: Hermes  
> 基于: MVP v1.0 代码审查 (49 API, 61测试)

---

## 一、现有架构审查

### 1.1 技术栈现状

```
FastAPI (Python 3.11) + SQLAlchemy 2.0 Async + SQLite/PostgreSQL
├── 认证: JWT (HS256, 24h过期)
├── ORM: DeclarativeBase + async_sessionmaker
├── DEV_MODE: SQLite (aiosqlite)
├── PROD_MODE: PostgreSQL (asyncpg)
└── 无缓存层
```

### 1.2 数据模型 (14张表)

| 表名 | 用途 | 记录数估计 |
|------|------|-----------|
| users | 用户/员工 | 100-1000 |
| scenic_spots | 景区 | 1-50 |
| ticket_types | 票种 | 3-10/景区 |
| ticket_orders | 票务订单 | 1000-10000/天 |
| hotels | 酒店 | 1-5/景区 |
| rooms | 房型 | 2-10/酒店 |
| hotel_orders | 酒店订单 | 100-1000/天 |
| announcements | 公告 | 10-100/景区 |
| pois | 导览点位 | 10-50/景区 |
| parking_rates | 停车费率 | 1-5/景区 |
| parking_records | 停车记录 | 100-1000/天 |
| nearby_points | 附近推荐 | 5-20/景区 |
| reviews | 游客评价 | 100-10000/景区 |
| payment_records | 支付记录 | 与订单 1:1 |

### 1.3 API端点清单 (49个)

| 模块 | 公开 | 需登录 | 管理员 | 合计 |
|------|------|--------|--------|------|
| auth | 0 | 3 | 0 | 3 |
| scenic | 6 | 1 | 6 | 13 |
| tickets | 1 | 4 | 2 | 7 |
| hotels | 2 | 4 | 4 | 10 |
| parking | 1 | 3 | 2 | 6 |
| dashboard | 0 | 0 | 2 | 2 |
| payment | 1 | 2 | 0 | 3 |
| system | 2 | 0 | 0 | 2 |
| **合计** | **13** | **17** | **16** | **46+3** |

---

## 二、性能瓶颈分析

### 2.1 N+1 查询问题 (严重)

| 位置 | 问题 | 影响 |
|------|------|------|
| `scenic.py:list_reviews` (L672-689) | 每个review单独查询user | 20条评价 = 21次查询 |
| `tickets.py:list_my_orders` (L293-294) | 每个order调用_enrich_order做2次查询 | 20条订单 = 41次查询 |
| `parking.py:list_parking_records` (L384-386) | 每个record查rate name | 20条记录 = 21次查询 |
| `parking.py:list_all_parking_records` (L440-441) | 同上 | 同上 |
| `tickets.py:batch_expire` (L511-525) | 每个过期订单单独查/写payment_record | N×2次查询 |

**修复方案**: 使用 `selectinload` / 批量预加载 / JOIN 查询一次性获取关联数据。

### 2.2 缺少关键数据库索引 (严重)

当前已有索引：主键、外键、部分unique字段。但以下查询路径无索引覆盖：

```sql
-- 需要添加的索引：

-- 1. 票务订单查询热点
CREATE INDEX idx_ticket_orders_created_at ON ticket_orders(created_at);
CREATE INDEX idx_ticket_orders_visit_date ON ticket_orders(visit_date);
CREATE INDEX idx_ticket_orders_paid_at ON ticket_orders(paid_at);
CREATE INDEX idx_ticket_orders_status_created ON ticket_orders(status, created_at);
-- 库存查询复合索引（高频调用）
CREATE INDEX idx_ticket_orders_inventory ON ticket_orders(ticket_type_id, visit_date, time_slot, status);

-- 2. 酒店订单
CREATE INDEX idx_hotel_orders_created_at ON hotel_orders(created_at);
CREATE INDEX idx_hotel_orders_paid_at ON hotel_orders(paid_at);
CREATE INDEX idx_hotel_orders_user_status ON hotel_orders(user_id, status);

-- 3. 停车记录
CREATE INDEX idx_parking_records_checkin_time ON parking_records(checkin_time);
CREATE INDEX idx_parking_records_paid_at ON parking_records(payed_at);
CREATE INDEX idx_parking_records_user_status ON parking_records(user_id, status);
CREATE INDEX idx_parking_records_plate_status ON parking_records(plate_number, status);

-- 4. 评价
CREATE INDEX idx_reviews_created_at ON reviews(created_at);
CREATE INDEX idx_reviews_spot_approved ON reviews(spot_id, is_approved, created_at);

-- 5. 公告
CREATE INDEX idx_announcements_spot_published ON announcements(spot_id, is_published, priority DESC);

-- 6. 附近推荐
CREATE INDEX idx_nearby_points_spot_active ON nearby_points(spot_id, is_active, sort_order, distance);

-- 7. 支付记录
CREATE INDEX idx_payment_records_order_no ON payment_records(order_no);
```

### 2.3 Dashboard统计性能瓶颈 (严重)

`/api/dashboard/stats` 端点单次请求执行 **约29次数据库查询**:
- 基础统计: ~10次查询
- 7天趋势循环: 2次 × 7天 = 14次查询  
- 其他辅助查询: ~5次

**最坏情况**: 管理后台每30秒轮询 → 每分钟58次DB查询 → 高峰期成为瓶颈。

### 2.4 营收报表 `/api/dashboard/revenue` 

3次全表GROUP BY聚合 + Python层week/month聚合。30天范围需遍历全表。

### 2.5 并发库存控制缺陷

`tickets.py:create_ticket_order` (L200-216):
- 使用 `SELECT SUM(quantity) WHERE status IN (...)` 检查库存
- 非原子操作，高并发下存在超卖风险
- 当前SQLite DEV模式有写锁保护，但PostgreSQL生产环境需行级锁

`hotels.py:create_hotel_order` (L300-336):
- 先检查 `available_count`，后扣减
- TOCTOU竞态条件

### 2.6 缺失缓存层

| 数据类型 | 读频率 | 写频率 | 缓存收益 |
|----------|--------|--------|----------|
| 景区信息 (scenic/info) | 极高 | 极低 | ⭐⭐⭐⭐⭐ |
| 票种列表 (tickets/types) | 极高 | 低 | ⭐⭐⭐⭐⭐ |
| 导览点位 (scenic/pois) | 高 | 低 | ⭐⭐⭐⭐ |
| 停车费率 (parking/rates) | 高 | 低 | ⭐⭐⭐⭐ |
| 酒店列表 (hotels) | 高 | 低 | ⭐⭐⭐⭐ |
| 公告列表 | 中 | 中 | ⭐⭐⭐ |
| 附近推荐 | 中 | 低 | ⭐⭐⭐ |
| 评价列表 | 高 | 中 | ⭐⭐ (需按spot_id拆分) |
| Dashboard统计 | 中 | - | ⭐⭐⭐⭐⭐ |
| 天气 (scenic/weather) | 中 | - | ⭐⭐⭐⭐ |
| 用户token黑名单 | - | - | ⭐⭐⭐ |

### 2.7 其他问题

- **密码安全**: 使用SHA-256而非bcrypt/argon2 (auth.py:26-29)
- **无请求限流**: 登录/支付/核销接口无限流保护
- **无API版本前缀**: 路由直接挂载在 `/api/*` 下 
- **天气mock数据**: 每次请求使用random模块计算
- **无结构化日志/监控**: 仅print输出

---

## 三、Redis缓存策略设计

### 3.1 缓存架构总览

```
                     ┌─────────────┐
                     │   Client    │
                     └──────┬──────┘
                            │
                     ┌──────▼──────┐
                     │   FastAPI   │
                     │  ┌───────┐  │
                     │  │Cache  │  │
                     │  │Layer  │  │
                     │  └───┬───┘  │
                     └──────┼──────┘
                            │
              ┌─────────────┼─────────────┐
              │             │             │
       ┌──────▼──────┐ ┌───▼────┐ ┌─────▼─────┐
       │    Redis    │ │  Post- │ │  WeChat   │
       │   (Cache)   │ │greSQL  │ │  Pay API  │
       └─────────────┘ └────────┘ └───────────┘
```

### 3.2 Redis配置

```python
# app/redis.py - Redis客户端配置
import redis.asyncio as aioredis
from app.config import settings

REDIS_CONFIG = {
    "host": settings.REDIS_HOST,      # 默认 localhost
    "port": settings.REDIS_PORT,      # 默认 6379
    "db": 0,
    "decode_responses": True,
    "socket_timeout": 2,
    "socket_connect_timeout": 2,
    "retry_on_timeout": True,
}

async def get_redis() -> aioredis.Redis:
    """获取Redis连接（连接池自动管理）"""
    return aioredis.from_url(
        f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/0",
        **REDIS_CONFIG
    )
```

### 3.3 缓存策略分类

#### A. Cache-Aside（旁路缓存）— 读多写少数据

适用于：景区信息、票种、POI、停车费率、酒店列表、附近推荐

```python
# 缓存键命名规范: {domain}:{entity}:{id}
# 示例:
#   scenic:info:1          → 景区1的完整信息
#   scenic:pois:1          → 景区1的导览点位
#   tickets:types:1        → 景区1的票种列表  
#   parking:rates:1        → 景区1的停车费率
#   hotels:list:1          → 景区1的酒店列表
#   scenic:points:1        → 景区1的附近推荐

# 过期策略:
CACHE_TTL = {
    "scenic_info":     3600,   # 1小时
    "ticket_types":    1800,   # 30分钟
    "pois":            3600,   # 1小时
    "parking_rates":   1800,   # 30分钟
    "hotels":          1800,   # 30分钟
    "nearby_points":   3600,   # 1小时
    "announcements":    600,   # 10分钟
    "weather":          300,   # 5分钟
}
```

**实现模式**:

```python
async def get_cached_or_fetch(redis, key: str, fetch_fn, ttl: int):
    """通用缓存读取装饰器"""
    cached = await redis.get(key)
    if cached:
        return json.loads(cached)
    data = await fetch_fn()
    if data is not None:
        await redis.setex(key, ttl, json.dumps(data, default=str))
    return data

async def invalidate_cache(redis, pattern: str):
    """按模式删除缓存"""
    keys = await redis.keys(pattern)
    if keys:
        await redis.delete(*keys)
```

**写入时失效**:

| 写入操作 | 失效的缓存模式 |
|----------|---------------|
| PUT /api/scenic/info | `scenic:info:*` |
| PUT /api/tickets/types | `tickets:types:*`, `scenic:info:*` |
| POST /api/scenic/announcements | `scenic:info:*`, `announcements:*` |
| PUT /api/parking/rates | `parking:rates:*` |
| POST /api/scenic/points | `scenic:points:*` |
| POST /api/scenic/reviews | `reviews:*` |

#### B. Write-Through（写穿透）— 库存数据

适用于：票种每日库存、酒店可用房间、停车可用车位

```python
# 库存缓存键: inventory:ticket:{ticket_type_id}:{date}:{time_slot}
#             inventory:room:{room_id}
#             inventory:parking:{rate_id}

# 扣减使用Redis DECR原子操作 + Lua脚本保证原子性:
LUA_DECR_INVENTORY = """
local key = KEYS[1]
local qty = tonumber(ARGV[1])
local current = tonumber(redis.call('GET', key) or '0')
if current >= qty then
    return redis.call('DECRBY', key, qty)
else
    return -1
end
"""
```

#### C. Dashboard统计缓存 — 定时计算

```python
# 缓存键: dashboard:stats:{spot_id}:{date}
#         dashboard:revenue:day:{date}
#         dashboard:revenue:week:{iso_week}
#         dashboard:revenue:month:{YYYY-MM}

# 策略:
# 1. Redis缓存Dashboard数据，TTL=60秒（1分钟热度）
# 2. 每天凌晨通过定时任务预计算昨日报表，TTL=86400秒
# 3. 今日数据实时查询但缓存30秒
```

#### D. Token黑名单

```python
# 缓存键: token:blacklist:{user_id}
# 用途: 用户退出/修改密码/封禁时失效所有token
# TTL: 与token过期时间一致 (24h)
```

### 3.4 缓存穿透/击穿/雪崩防护

| 问题 | 方案 |
|------|------|
| **缓存穿透** | 空值缓存（TTL=60s），布隆过滤器过滤不存在的ID |
| **缓存击穿** | 热点key互斥锁：`SETNX lock:key 1 EX 5` |
| **缓存雪崩** | TTL加随机偏移（±20%），多级缓存兜底 |

```python
async def get_with_protection(redis, key, fetch_fn, ttl):
    """带保护的缓存读取"""
    # 1. 尝试读取
    cached = await redis.get(key)
    if cached:
        return json.loads(cached)
    
    # 2. 防止击穿：加锁
    lock_key = f"lock:{key}"
    locked = await redis.setnx(lock_key, "1")
    if locked:
        await redis.expire(lock_key, 5)
        try:
            data = await fetch_fn()
            if data is not None:
                # TTL加随机偏移防止雪崩
                actual_ttl = ttl + random.randint(0, int(ttl * 0.2))
                await redis.setex(key, actual_ttl, json.dumps(data, default=str))
            else:
                # 空值缓存防穿透
                await redis.setex(key, 60, json.dumps(None))
            return data
        finally:
            await redis.delete(lock_key)
    else:
        # 其他请求等待锁释放
        for _ in range(10):
            await asyncio.sleep(0.1)
            cached = await redis.get(key)
            if cached:
                return json.loads(cached)
    return await fetch_fn()
```

### 3.5 Session/限流

```python
# 登录限流: rate:login:{ip} → 5次/分钟
# API限流: rate:api:{ip}:{endpoint} → 可配置
# 核销限流: rate:verify:{staff_id} → 100次/分钟
```

---

## 四、数据库索引优化方案

### 4.1 索引设计原则

1. **覆盖高频查询的WHERE/JOIN/ORDER BY列**
2. **复合索引列顺序**: 等值条件 → 范围条件 → 排序条件
3. **监控慢查询日志**，按需创建，避免过度索引
4. **定期ANALYZE** 更新统计信息

### 4.2 推荐新增索引清单

#### 优先级 P0 (必须添加，影响核心业务)

```sql
-- ticket_orders: 库存查询 (每笔订单都触发)
CREATE INDEX idx_ticket_orders_inventory 
    ON ticket_orders(ticket_type_id, visit_date, time_slot, status)
    WHERE status IN ('paid', 'verified', 'pending');
-- 注: PostgreSQL支持部分索引，SQLite需去掉WHERE，改为全索引

-- ticket_orders: 我的订单列表 (用户高频操作)
CREATE INDEX idx_ticket_orders_user_status_created 
    ON ticket_orders(user_id, status, created_at DESC);

-- ticket_orders: Dashboard营收统计
CREATE INDEX idx_ticket_orders_created_status 
    ON ticket_orders(created_at, status);
CREATE INDEX idx_ticket_orders_paid_at 
    ON ticket_orders(paid_at);

-- hotel_orders: 用户订单列表
CREATE INDEX idx_hotel_orders_user_status 
    ON hotel_orders(user_id, status, created_at DESC);

-- parking_records: 车牌号查重 (入场时检查)
CREATE INDEX idx_parking_records_plate_status 
    ON parking_records(plate_number, status);

-- reviews: 评价列表（最频繁的公开查询之一）
CREATE INDEX idx_reviews_spot_approved_created 
    ON reviews(spot_id, is_approved, created_at DESC);

-- payment_records: 退款时关联查询
CREATE INDEX idx_payment_records_order_no 
    ON payment_records(order_no);
```

#### 优先级 P1 (推荐添加)

```sql
-- 公告过滤查询
CREATE INDEX idx_announcements_spot_published_priority 
    ON announcements(spot_id, is_published, priority DESC, published_at DESC);

-- 附近推荐排序过滤
CREATE INDEX idx_nearby_points_spot_active 
    ON nearby_points(spot_id, is_active, sort_order, distance);

-- 停车记录管理端查询
CREATE INDEX idx_parking_records_checkin_time_status 
    ON parking_records(checkin_time DESC, status);

-- hotel_orders Dashboard统计
CREATE INDEX idx_hotel_orders_created_status 
    ON hotel_orders(created_at, status);
CREATE INDEX idx_hotel_orders_paid_at 
    ON hotel_orders(paid_at);

-- 停车营收统计
CREATE INDEX idx_parking_records_paid_at 
    ON parking_records(paid_at);
```

#### 优先级 P2 (可选，数据量大后添加)

```sql
-- 按城市搜索景区
CREATE INDEX idx_scenic_spots_city_active 
    ON scenic_spots(city, is_active);

-- 票种按景区查找
CREATE INDEX idx_ticket_types_spot_active_sort 
    ON ticket_types(spot_id, is_active, sort_order);

-- 酒店按城市搜索
CREATE INDEX idx_hotels_city_active 
    ON hotels(city, is_active);

-- POI按景区+分类
CREATE INDEX idx_pois_spot_category_active 
    ON pois(spot_id, category, is_active, sort_order);

-- 停车费率按景区
CREATE INDEX idx_parking_rates_spot_active 
    ON parking_rates(spot_id, is_active);
```

### 4.3 索引维护策略

```python
# PostgreSQL: 定期维护
# 每天凌晨3点执行:
#   REINDEX TABLE ticket_orders;
#   ANALYZE ticket_orders;
#   VACUUM ANALYZE ticket_orders;

# SQLite: 
# 每次seed后执行:
#   PRAGMA optimize;
#   ANALYZE;
```

### 4.4 索引对现有查询的影响预估

| 查询 | 当前扫描 | 索引后 | 提升 |
|------|---------|--------|------|
| 库存检查 (ticket_orders) | 全表扫描 | Index Only Scan | ~100x |
| 我的票订单列表 | 全表扫描 | Index Scan | ~50x |
| 评价列表 (spot_id + 分页) | 全表扫描 | Index Scan | ~40x |
| 公告列表 (spot_id + 分类 + 分页) | 全表扫描 | Index Scan | ~20x |
| Dashboard统计 (按日期范围) | Seq Scan | Index Scan | ~30x |
| 停车记录按车牌搜索 | 全表扫描 | Index Scan | ~100x |

---

## 五、API版本管理方案

### 5.1 版本策略

```
采用 URL Path 版本控制: /api/v1/*, /api/v2/*

版本规则:
- v1: 当前所有API（保持向后兼容，标记为 stable）
- v2: 重构后的API（新功能 + 性能优化）
- 主版本号变更: 不兼容的API变更
- 次版本号: 向下兼容的新功能
```

### 5.2 路由结构

```
/api/
├── v1/                          # 当前MVP API（保持兼容）
│   ├── auth/                    # 不变
│   ├── scenic/                  # 保持不变
│   ├── tickets/                 # 保持不变
│   ├── hotels/                  # 保持不变
│   ├── parking/                 # 保持不变
│   ├── dashboard/               # 保持不变
│   └── payment/                 # 保持不变
│
├── v2/                          # 架构升级版
│   ├── auth/
│   │   ├── POST /login          # 增强: 支持验证码/微信登录
│   │   ├── POST /register       # 增强: 手机验证码注册
│   │   ├── POST /logout         # 新增: token失效
│   │   └── GET  /me             # 不变
│   │
│   ├── scenic/
│   │   ├── GET  /info           # 增强: 缓存, 响应字段优化
│   │   ├── GET  /announcements  # 增强: 分页优化, 支持游标
│   │   ├── GET  /pois           # 增强: 缓存
│   │   ├── GET  /points         # 增强: 缓存, 距离排序
│   │   ├── GET  /reviews        # 增强: 修复N+1, 游标分页
│   │   ├── POST /reviews        # 不变
│   │   └── GET  /weather        # 增强: 对接真实天气API
│   │
│   ├── tickets/
│   │   ├── GET  /types          # 增强: 缓存
│   │   ├── POST /order          # 增强: Redis库存扣减, 行锁
│   │   ├── GET  /orders         # 增强: 修复N+1
│   │   ├── POST /verify         # 增强: 限流, 幂等
│   │   └── POST /{id}/refund    # 增强: 分布式锁
│   │
│   ├── hotels/
│   │   ├── GET  /               # 增强: 缓存
│   │   ├── POST /orders         # 增强: Redis库存
│   │   └── GET  /orders         # 增强: 修复N+1
│   │
│   ├── parking/
│   │   ├── GET  /rates          # 增强: 缓存
│   │   ├── POST /checkin        # 增强: Redis库存
│   │   └── POST /{id}/checkout  # 增强: 费率缓存
│   │
│   ├── dashboard/
│   │   ├── GET  /stats          # 增强: 缓存, 预计算
│   │   └── GET  /revenue        # 增强: 汇总表查询
│   │
│   └── payment/
│       ├── POST /create         # 增强: 幂等性Token
│       ├── POST /notify         # 增强: 签名验证
│       └── GET  /status/{no}    # 不变
│
└── (根路径健康检查)
    ├── GET  /health
    └── GET  /
```

### 5.3 FastAPI实现方式

```python
# app/main.py
from app.api.v1 import router as v1_router
from app.api.v2 import router as v2_router

app.include_router(v1_router, prefix="/api/v1")
app.include_router(v2_router, prefix="/api/v2")

# 默认路由重定向到最新版本
@app.get("/api")
async def api_root():
    return {
        "latest": "/api/v2",
        "stable": "/api/v1",
        "deprecated": [],
        "docs": "/docs"
    }
```

### 5.4 版本过渡策略

| 阶段 | 时间 | v1状态 | v2状态 |
|------|------|--------|--------|
| Phase 1 | 当前 | STABLE | - |
| Phase 2 | 第1-2周 | STABLE | BETA (逐步迁移) |
| Phase 3 | 第3-4周 | STABLE | STABLE (双版本并存) |
| Phase 4 | 3个月后 | DEPRECATED (添加Sunset header) | STABLE |
| Phase 5 | 6个月后 | REMOVED | STABLE |

**响应头约定**:
```
# v1响应头:
API-Version: 1
API-Deprecated: true
API-Sunset: Sun, 31 Dec 2026 23:59:59 GMT
API-Latest-Version: 2
```

### 5.5 兼容性保证

- v1和v2共享同一数据库，版本差异仅在API层
- 数据模型向后兼容：新增字段使用默认值，不删除字段
- v2可以返回v1兼容的响应格式（通过查询参数 `?format=v1`）
- 客户端通过请求头 `Accept-Version: v1` 或URL路径 `/api/v1/` 指定版本

---

## 六、性能优化方案汇总

### 6.1 优先级分级

| 优先级 | 优化项 | 预期收益 | 工作耗时 |
|--------|--------|---------|----------|
| P0 | 修复N+1查询问题 | 减少50-80% DB查询 | 0.5天 |
| P0 | 添加核心数据库索引 | 查询速度提升10-100x | 0.5天 |
| P1 | Redis缓存层实现 | 减少70% DB负载 | 3天 |
| P1 | Dashboard缓存 + 预计算 | Dashboard响应 <50ms | 2天 |
| P1 | 并发库存控制修复 | 消除超卖风险 | 1天 |
| P2 | API版本化改造 | 架构规范化 | 2天 |
| P2 | 请求限流 | 安全防护 | 1天 |
| P3 | 密码升级bcrypt | 安全加固 | 0.5天 |
| P3 | 结构化日志 | 可观测性 | 1天 |

### 6.2 N+1 修复代码示例

**修复前** (`scenic.py:list_reviews`):
```python
# 每个review单独查询user — N+1问题
for r in reviews:
    user_result = await db.execute(select(User).where(User.id == r.user_id))
    user = user_result.scalar_one_or_none()
```

**修复后**:
```python
# 批量预加载用户信息
user_ids = [r.user_id for r in reviews]
users_result = await db.execute(
    select(User).where(User.id.in_(user_ids))
)
user_map = {u.id: u for u in users_result.scalars().all()}

for r in reviews:
    user = user_map.get(r.user_id)
    items.append(ReviewOut(..., username=user.username if user else None, ...))
```

**tickets.py 修复 `_enrich_order`**:
```python
# 修复前: 每个订单2次查询
# 修复后: 使用 selectinload 或 批量查询
async def _enrich_orders(orders, db):
    """批量填充订单关联数据"""
    type_ids = list(set(o.ticket_type_id for o in orders if o.ticket_type_id))
    spot_ids = list(set(o.spot_id for o in orders if o.spot_id))
    
    # 并行查询
    types_result = await db.execute(
        select(TicketType.id, TicketType.name).where(TicketType.id.in_(type_ids))
    )
    spots_result = await db.execute(
        select(ScenicSpot.id, ScenicSpot.name).where(ScenicSpot.id.in_(spot_ids))
    )
    type_map = {tid: tname for tid, tname in types_result.all()}
    spot_map = {sid: sname for sid, sname in spots_result.all()}
    
    return [TicketOrderOut(
        ..., 
        ticket_type_name=type_map.get(o.ticket_type_id),
        spot_name=spot_map.get(o.spot_id),
    ) for o in orders]
```

### 6.3 并发库存控制修复

**方案**: PostgreSQL使用 `SELECT ... FOR UPDATE` 行锁

```python
# tickets.py 下单库存检查 (PostgreSQL生产环境)
from sqlalchemy import select, update

# 方案A: 悲观锁
tt_result = await db.execute(
    select(TicketType).where(
        TicketType.id == req.ticket_type_id,
        TicketType.spot_id == req.spot_id,
        TicketType.is_active == True,
    ).with_for_update()  # 行锁
)

# 方案B: Redis原子库存 (推荐 — 更高并发)
async def check_and_decr_inventory(redis, ticket_type_id, date, time_slot, qty):
    """Redis Lua脚本原子检查并扣减库存"""
    key = f"inventory:ticket:{ticket_type_id}:{date}:{time_slot}"
    lua_script = """
    local current = tonumber(redis.call('GET', KEYS[1]) or '0')
    local needed = tonumber(ARGV[1])
    if current >= needed then
        redis.call('DECRBY', KEYS[1], needed)
        return 1
    else
        return 0
    end
    """
    result = await redis.eval(lua_script, 1, key, qty)
    return bool(result)
```

### 6.4 Dashboard优化

**方案**: 预计算 + 增量更新

```python
# 1. 创建每日汇总表（物化视图或定时任务写入）
class DailySummary(Base):
    __tablename__ = "daily_summaries"
    date: Mapped[date]
    spot_id: Mapped[int]
    tickets_sold: Mapped[int]
    tickets_verified: Mapped[int]
    ticket_revenue: Mapped[float]
    hotel_revenue: Mapped[float]
    parking_revenue: Mapped[float]

# 2. 定时任务（每天凌晨1点）
async def aggregate_daily_summary():
    """汇总昨日数据写入 daily_summaries"""
    yesterday = date.today() - timedelta(days=1)
    # ... 执行聚合查询并写入

# 3. Dashboard接口
async def dashboard_stats_v2(spot_id, db, redis):
    # 历史数据从daily_summaries查（秒级）
    # 今日数据实时查 + Redis缓存30秒
    # 7天趋势从daily_summaries查 + 今日Redis补偿
```

### 6.5 建议的项目结构调整

```
backend/
├── app/
│   ├── main.py                  # FastAPI 入口
│   ├── config.py                # 配置
│   ├── db.py                    # 数据库模型 + 会话
│   ├── redis.py                 # Redis客户端 (新增)
│   ├── cache.py                 # 缓存工具 (新增)
│   ├── limiter.py               # 限流中间件 (新增)
│   ├── api/
│   │   ├── __init__.py
│   │   ├── v1/                  # v1 API (原api目录)
│   │   │   ├── __init__.py
│   │   │   ├── auth.py
│   │   │   ├── scenic.py
│   │   │   ├── tickets.py
│   │   │   ├── hotels.py
│   │   │   ├── parking.py
│   │   │   ├── payment.py
│   │   │   └── dashboard.py
│   │   └── v2/                  # v2 API (新增)
│   │       ├── __init__.py
│   │       ├── auth.py
│   │       ├── scenic.py
│   │       ├── tickets.py
│   │       ├── hotels.py
│   │       ├── parking.py
│   │       ├── payment.py
│   │       └── dashboard.py
│   ├── services/                # 业务逻辑层 (新增)
│   │   ├── ticket_service.py
│   │   ├── hotel_service.py
│   │   ├── parking_service.py
│   │   └── payment_service.py
│   ├── models/                  # SQLAlchemy模型 (从db.py拆分)
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── user.py
│   │   ├── scenic.py
│   │   ├── ticket.py
│   │   ├── hotel.py
│   │   ├── parking.py
│   │   ├── payment.py
│   │   └── review.py
│   └── tasks/                   # 定时任务 (新增)
│       ├── __init__.py
│       ├── daily_summary.py     # 日汇总
│       └── expire_orders.py     # 过期订单处理
├── tests/
│   ├── test_api_v1.py
│   ├── test_api_v2.py
│   └── test_services.py
├── migrations/                  # Alembic迁移 (新增)
├── alembic.ini
├── requirements.txt
└── Dockerfile
```

---

## 七、实施路线图

### Phase 1: 紧急修复（第1周）

| 任务 | 内容 | 工时 |
|------|------|------|
| P0-1 | 修复所有N+1查询（reviews, tickets, parking） | 4h |
| P0-2 | 添加核心数据库索引（P0清单） | 4h |
| P0-3 | 数据库连接池调优 | 2h |
| P0-4 | 密码升级为bcrypt | 2h |

### Phase 2: 缓存层（第2周）

| 任务 | 内容 | 工时 |
|------|------|------|
| P1-1 | Redis集成 + 连接池配置 | 4h |
| P1-2 | Cache-Aside实现（scenic, tickets, hotels, parking） | 8h |
| P1-3 | Dashboard缓存 + 定时任务框架 | 8h |
| P1-4 | Token黑名单实现 | 4h |

### Phase 3: 并发安全（第2-3周）

| 任务 | 内容 | 工时 |
|------|------|------|
| P1-5 | PostgreSQL行锁库存扣减 | 4h |
| P1-6 | Redis原子库存方案（高并发场景） | 8h |
| P1-7 | 支付幂等性Token | 4h |
| P1-8 | 核销接口幂等性 | 2h |

### Phase 4: API版本化（第3周）

| 任务 | 内容 | 工时 |
|------|------|------|
| P2-1 | 路由结构调整 /api/v1 /api/v2 | 4h |
| P2-2 | v2 API实现（使用缓存+优化后的service层） | 8h |
| P2-3 | 版本兼容性中间件 | 4h |

### Phase 5: 安全与可观测性（第4周）

| 任务 | 内容 | 工时 |
|------|------|------|
| P2-4 | 登录/支付/核销接口限流 | 4h |
| P3-1 | 结构化日志（loguru/json格式） | 4h |
| P3-2 | 慢查询监控 + APM接入 | 4h |
| P3-3 | 健康检查增强（DB/Redis连通性） | 2h |

---

## 八、监控与运维

### 8.1 关键指标监控

| 指标 | 目标 | 告警阈值 |
|------|------|----------|
| API P95延迟 | <200ms | >500ms 告警 |
| Dashboard响应 | <100ms | >500ms 告警 |
| 购票下单成功率 | >99.9% | <99.5% 告警 |
| DB连接池使用率 | <70% | >85% 告警 |
| Redis命中率 | >90% | <80% 告警 |
| 超卖事件 | 0 | >0 立即告警 |
| 库存缓存不一致 | 0 | >0 告警 |

### 8.2 降级策略

```
Redis不可用 → 自动跳过缓存，直连DB（降级模式）
PostgreSQL不可用 → 返回503 + 降级页面
高并发时段 → 限流排队，返回Retry-After头
```

---

## 九、附录

### A. 依赖清单

```
# requirements.txt 新增依赖
redis[hiredis]==5.0.1          # Redis客户端 + C加速
bcrypt==4.1.2                   # 密码哈希（替换SHA-256）
loguru==0.7.2                   # 结构化日志
slowapi==0.1.9                  # 限流
apscheduler==3.10.4             # 定时任务
alembic==1.13.0                 # 数据库迁移
sqlalchemy-utils==0.41.2        # 工具类
```

### B. 配置新增项

```python
class Settings(BaseSettings):
    # ... 原有配置 ...
    
    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str = ""
    REDIS_DB: int = 0
    
    # 限流
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_LOGIN: str = "5/minute"      # 登录限流
    RATE_LIMIT_PAYMENT: str = "10/minute"   # 支付限流
    RATE_LIMIT_VERIFY: str = "100/minute"   # 核销限流
    
    # 缓存TTL (秒)
    CACHE_TTL_SCENIC: int = 3600
    CACHE_TTL_TICKET: int = 1800
    CACHE_TTL_DASHBOARD: int = 60
    CACHE_TTL_INVENTORY: int = 86400
    
    # 定时任务
    DAILY_SUMMARY_HOUR: int = 1     # 凌晨1点汇总
    EXPIRE_ORDER_HOUR: int = 2      # 凌晨2点过期处理
```

### C. Docker Compose 更新

```yaml
# docker-compose.yml 新增服务
services:
  redis:
    image: redis:7-alpine
    container_name: scenic-redis
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes --maxmemory 256mb --maxmemory-policy allkeys-lru
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 3

volumes:
  redis_data:
```

---

*本文档基于现有代码审查生成，方案细节可根据实际需求调整。实施前建议在测试环境验证所有变更。*
