# 景区智慧管理系统 - 测试文档

> 项目: Scenic v1.0 | 测试框架: pytest + pytest-asyncio + httpx | 测试文件: `tests/test_api.py`

---

## 一、测试运行

### 1.1 前置条件

```bash
cd ~/projects/scenic/code/backend

# 创建虚拟环境并安装依赖
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install pytest pytest-asyncio httpx coverage

# 初始化种子数据（测试依赖预置数据）
python seed.py
```

### 1.2 运行全部测试

```bash
cd ~/projects/scenic/code/backend

# 运行所有测试
pytest tests/ -v

# 或使用 coverage 运行
coverage run -m pytest tests/ -v
coverage report
```

### 1.3 运行特定测试

```bash
# 按测试类运行
pytest tests/test_api.py::TestHealthCheck -v
pytest tests/test_api.py::TestPublicAPIs -v
pytest tests/test_api.py::TestAuthAPIs -v
pytest tests/test_api.py::TestPurchasePayVerifyFlow -v
pytest tests/test_api.py::TestHotelFlow -v
pytest tests/test_api.py::TestExportAPIs -v

# 按关键字过滤
pytest tests/ -k "health" -v
pytest tests/ -k "admin" -v
pytest tests/ -k "guest" -v

# 显示详细错误信息
pytest tests/ -v --tb=long

# 失败时进入 pdb 调试
pytest tests/ --pdb
```

### 1.4 pytest 配置

`pytest.ini`:

```ini
[pytest]
asyncio_mode = auto
testpaths = tests
```

`tests/conftest.py` 注册 pytest-asyncio 插件，无需额外配置。

---

## 二、覆盖率

### 2.1 生成覆盖率报告

```bash
cd ~/projects/scenic/code/backend

# 运行测试并收集覆盖率
coverage run -m pytest tests/ -v

# 终端报告
coverage report -m

# HTML 报告（浏览器查看）
coverage html
open htmlcov/index.html

# XML 报告（CI 集成）
coverage xml
```

### 2.2 覆盖率统计

当前项目 `.gitignore` 已忽略 `.coverage` 和 `htmlcov/`，覆盖率数据不提交到仓库。

预期覆盖率目标:
- API 路由层: >= 90%
- 业务逻辑层: >= 80%
- 整体行覆盖率: >= 85%

### 2.3 CI 集成示例

```yaml
# .github/workflows/test.yml
- name: Run tests
  run: |
    cd backend
    pip install -r requirements.txt
    pip install pytest pytest-asyncio httpx coverage
    python seed.py
    coverage run -m pytest tests/ -v
    coverage xml
- name: Upload coverage
  uses: codecov/codecov-action@v3
  with:
    file: backend/coverage.xml
```

---

## 三、测试架构

### 3.1 测试类组织

| 测试类 | 测试内容 | 测试数 |
|--------|---------|--------|
| `TestHealthCheck` | 健康检查 `/health` | 1 |
| `TestPublicAPIs` | 公开API（景区信息、公告、POI、天气、票种、停车费率、酒店列表） | 9 |
| `TestAuthAPIs` | 认证API（注册、登录、无效登录） | 4 |
| `TestAuthRequiredAPIs` | 鉴权拦截（无token返回401） | 17 |
| `TestNewPublicEndpoints` | 新公开API（推荐点位、评价筛选） | 7 |
| `TestGuestAuthEndpoints` | guest用户鉴权后操作（发表评价、边界测试） | 3 |
| `TestAdminEndpoints` | 管理员专属（创建费率/点位、删除评价、营收报表、权限拦截） | 12 |
| `TestGuestVsAdminAuth` | 角色权限隔离（guest不能操作admin接口） | 4 |
| `TestPurchasePayVerifyFlow` | 购票→支付→核销完整流程 + 边界 | 5 |
| `TestPaymentNotify` | 支付回调 | 1 |
| `TestNewEndpoints` | 天气刷新、综合总览 | 9 |
| `TestExportAPIs` | 数据导出（票务/营收/停车CSV） | 14 |
| `TestHotelFlow` | 酒店模块完整流程（创建酒店/房型→下单→支付→入住→退房） + 边界 | 6 |

### 3.2 测试覆盖的流程

```
用户注册 ──► 登录获取JWT ──► 浏览景区/票种/酒店
                                  │
                                  ▼
                          购票下单 (POST /api/tickets/order)
                                  │
                                  ▼
                          微信支付 (POST /api/payment/create)
                                  │
                                  ▼
                     DEV_MODE 确认支付 (POST /api/payment/confirm)
                                  │
                                  ▼
                          扫码核销 (POST /api/tickets/verify)
                                  │
                                  ▼
                          重复核销拒绝 (already_verified)
```

```
管理后台:
  创建酒店 ──► 创建房型 ──► 游客下单 ──► 支付 ──► 入住 ──► 退房
  创建费率 ──► 创建点位 ──► 编辑景区信息 ──► 营收报表 ──► 导出CSV
```

### 3.3 角色权限矩阵（已测试覆盖）

| 操作 | guest | staff | admin | front_desk |
|------|-------|-------|-------|------------|
| 浏览景区/票种/酒店 | ✓ | ✓ | ✓ | ✓ |
| 注册/登录 | ✓ | ✓ | ✓ | ✓ |
| 购票下单 | ✓ | ✓ | ✓ | ✓ |
| 酒店预订 | ✓ | ✓ | ✓ | ✓ |
| 发表评价 | ✓ | ✓ | ✓ | ✓ |
| 核销验票 | ✗ | ✓ | ✓ | ✗ |
| 办理入住/退房 | ✗ | ✓ | ✓ | ✗ |
| 创建票种 | ✗ | ✗ | ✓ | ✗ |
| 创建酒店/房型 | ✗ | ✗ | ✓ | ✗ |
| 编辑景区信息 | ✗ | ✗ | ✓ | ✗ |
| 添加停车费率 | ✗ | ✗ | ✓ | ✗ |
| 添加推荐点位 | ✗ | ✗ | ✓ | ✗ |
| 删除评价 | ✗ | ✗ | ✓ | ✗ |
| 营收报表 | ✗ | ✗ | ✓ | ✗ |
| 综合总览 | ✗ | ✗ | ✓ | ✗ |
| 刷新天气缓存 | ✗ | ✗ | ✓ | ✗ |
| 数据导出CSV | ✗ | ✗ | ✓ | ✗ |

---

## 四、API 端点清单

> 总计 49 个端点 | 基础地址: `http://127.0.0.1:8000` | 交互文档: `/docs`
>
> 详细请求/响应参数见 [API.md](./API.md)

### 4.1 认证模块 (`/api/auth`) — 3 端点

| 方法 | 路径 | 鉴权 | 说明 |
|------|------|------|------|
| POST | `/api/auth/register` | 无 | 用户注册 |
| POST | `/api/auth/login` | 无 | 用户名密码登录 |
| GET | `/api/auth/me` | Bearer Token | 获取当前用户信息 |

### 4.2 景区模块 (`/api/scenic`) — 14 端点

| 方法 | 路径 | 鉴权 | 说明 |
|------|------|------|------|
| GET | `/api/scenic/info` | 无 | 获取景区完整信息（票种+酒店+天气） |
| PUT | `/api/scenic/info` | admin | 编辑景区信息 |
| GET | `/api/scenic/announcements` | 无 | 公告列表 |
| POST | `/api/scenic/announcements` | admin | 创建公告 |
| PUT | `/api/scenic/announcements/{id}` | admin | 编辑公告 |
| DELETE | `/api/scenic/announcements/{id}` | admin | 删除公告 |
| GET | `/api/scenic/pois` | 无 | 导览点位列表 |
| GET | `/api/scenic/points` | 无 | 景区附近推荐点位（餐饮/购物/娱乐） |
| POST | `/api/scenic/points` | admin | 添加推荐点位 |
| PUT | `/api/scenic/points/{id}` | admin | 编辑推荐点位 |
| GET | `/api/scenic/reviews` | 无 | 游客评价列表（评分分布） |
| POST | `/api/scenic/reviews` | 登录用户 | 发表评价 |
| DELETE | `/api/scenic/reviews/{id}` | admin | 删除评价 |
| GET | `/api/scenic/weather` | 无 | 景区天气（温度/湿度/风力/AQI/3天预报） |
| POST | `/api/scenic/weather/refresh` | admin | 刷新天气缓存 |

### 4.3 票务模块 (`/api/tickets`) — 8 端点

| 方法 | 路径 | 鉴权 | 说明 |
|------|------|------|------|
| GET | `/api/tickets/types` | 无 | 获取票种列表 |
| POST | `/api/tickets/types` | admin | 创建票种 |
| POST | `/api/tickets/order` | 登录用户 | 购票下单 |
| GET | `/api/tickets/orders` | 登录用户 | 我的购票订单 |
| GET | `/api/tickets/order/{order_no}` | 登录用户 | 按订单号查询 |
| POST | `/api/tickets/verify` | staff/admin | 核销验票（扫码） |
| POST | `/api/tickets/order/{id}/refund` | 登录用户 | 申请退款 |
| POST | `/api/tickets/batch-expire` | admin | 批量过期处理 |

### 4.4 酒店模块 (`/api/hotels`) — 9 端点

| 方法 | 路径 | 鉴权 | 说明 |
|------|------|------|------|
| GET | `/api/hotels` | 无 | 酒店列表 |
| POST | `/api/hotels` | admin | 创建酒店 |
| GET | `/api/hotels/{hotel_id}/rooms` | 无 | 酒店房型列表 |
| POST | `/api/hotels/{hotel_id}/rooms` | admin | 创建房型 |
| POST | `/api/hotels/orders` | 登录用户 | 客房预订 |
| GET | `/api/hotels/orders` | 登录用户 | 我的客房订单 |
| GET | `/api/hotels/orders/detail/{order_no}` | 登录用户 | 按订单号查询 |
| POST | `/api/hotels/orders/{id}/checkin` | staff/admin | 办理入住 |
| POST | `/api/hotels/orders/{id}/checkout` | staff/admin | 办理退房 |
| POST | `/api/hotels/orders/{id}/refund` | 登录用户 | 申请退款 |

### 4.5 支付模块 (`/api/payment`) — 9 端点

| 方法 | 路径 | 鉴权 | 说明 |
|------|------|------|------|
| POST | `/api/payment/create` | 登录用户 | 创建支付（微信JSAPI下单） |
| POST | `/api/payment/confirm` | 无 | [DEV_MODE] 确认支付 |
| POST | `/api/payment/cancel` | 登录用户 | 取消未支付订单 |
| POST | `/api/payment/notify` | 无 | 微信支付回调通知 |
| GET | `/api/payment/status/{order_no}` | 登录用户 | 查询支付状态 |
| POST | `/api/payment/refund/approve` | admin | 退款审核 |
| GET | `/api/payment/refund/pending` | admin | 待审核退款列表 |
| POST | `/api/payment/auto-cancel` | admin | 扫描并自动取消超时未支付订单 |

### 4.6 停车模块 (`/api/parking`) — 6 端点

| 方法 | 路径 | 鉴权 | 说明 |
|------|------|------|------|
| GET | `/api/parking/rates` | 无 | 停车费率列表 |
| POST | `/api/parking/rates` | admin | 添加停车费率 |
| PUT | `/api/parking/rates/{id}` | admin | 编辑停车费率 |
| POST | `/api/parking/checkin` | 登录用户 | 停车入场 |
| POST | `/api/parking/checkout/{record_id}` | 登录用户 | 停车出场缴费 |
| GET | `/api/parking/records` | 登录用户 | 我的停车记录 |
| GET | `/api/parking/records/all` | admin | 全部停车记录 |

### 4.7 仪表盘模块 (`/api/dashboard`) — 3 端点

| 方法 | 路径 | 鉴权 | 说明 |
|------|------|------|------|
| GET | `/api/dashboard/stats` | admin | 仪表盘完整统计 |
| GET | `/api/dashboard/revenue` | admin | 营收报表（按日/周/月） |
| GET | `/api/dashboard/overview` | admin | 综合总览（门票+酒店+停车+评价） |

### 4.8 导出模块 (`/api/export`) — 3 端点

| 方法 | 路径 | 鉴权 | 说明 |
|------|------|------|------|
| GET | `/api/export/tickets` | admin | 导出票务数据 CSV |
| GET | `/api/export/revenue` | admin | 导出营收报表 CSV |
| GET | `/api/export/parking` | admin | 导出停车记录 CSV |

### 4.9 系统端点 — 3 端点

| 方法 | 路径 | 鉴权 | 说明 |
|------|------|------|------|
| GET | `/` | 无 | API 导航页 |
| GET | `/health` | 无 | 健康检查 |
| GET | `/docs` | 无 | Swagger UI 交互文档 |

---

## 五、代码库导航

```
code/backend/
├── tests/
│   ├── conftest.py          # pytest 配置（注册 pytest-asyncio）
│   └── test_api.py          # API 集成测试（61 个用例）
├── app/
│   ├── main.py              # FastAPI 入口（路由注册、CORS、静态文件）
│   ├── config.py            # 配置管理（DEV_MODE、数据库URL、JWT、CORS）
│   ├── db.py                # 数据库模型 + 引擎（SQLAlchemy Async）
│   └── api/
│       ├── auth.py          # 认证 API（注册/登录/用户信息）
│       ├── scenic.py        # 景区 API（信息/公告/POI/点位/评价/天气）
│       ├── tickets.py       # 票务 API（票种/下单/核销/退款/过期）
│       ├── hotels.py        # 酒店 API（酒店/房型/预订/入离/退款）
│       ├── payment.py       # 支付 API（创建/确认/回调/退款审核）
│       ├── parking.py       # 停车 API（费率/入场/出场/记录）
│       ├── dashboard.py     # 仪表盘 API（统计/营收/综合总览）
│       └── export.py        # 导出 API（票务/营收/停车 CSV）
├── requirements.txt         # Python 依赖
├── pytest.ini               # pytest 配置（asyncio_mode=auto）
├── seed.py                  # 种子数据脚本（3景区+票种+酒店+房型+...）
└── data/
    └── scenic.db            # SQLite 开发数据库（由 seed.py 生成）
```
