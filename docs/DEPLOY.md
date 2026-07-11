<<<<<<< HEAD
# 景区智慧管理系统 - 部署文档

## 系统架构

```
微信小程序 ── HTTPS ── Nginx (反向代理) ── FastAPI (uvicorn:8000) ── PostgreSQL 16
                                                      │
                                                      └── 管理后台 (/admin)
```

## 一、VPS 部署 (Docker Compose)

### 1.1 前置要求

- VPS 服务器（Ubuntu 22.04+ / Debian 12+）
- Docker 24+ & Docker Compose v2
- 域名（已备案并解析到 VPS IP）

```bash
# 安装 Docker
curl -fsSL https://get.docker.com | bash
sudo usermod -aG docker $USER
# 退出重新登录使 docker 组生效
```

### 1.2 项目文件准备

```bash
cd ~
git clone <你的仓库地址> scenic
cd scenic
```

确保以下文件结构存在：

```
scenic/
├── docker-compose.yml    # 容器编排
├── Dockerfile            # 后端镜像构建
├── .env                  # 环境变量（生产用）
├── nginx/
│   └── nginx.conf        # Nginx 配置
├── backend/              # FastAPI 后端
│   ├── requirements.txt
│   └── app/
│       ├── main.py
│       ├── config.py
│       ├── db.py
│       └── api/
└── admin/                # 管理后台静态页面
```

### 1.3 创建生产环境变量文件 .env

在项目根目录创建 `.env`：

```ini
# 生产模式
DEV_MODE=false

# PostgreSQL 连接
POSTGRES_DB=scenic
POSTGRES_USER=scenic
POSTGRES_PASSWORD=请修改为强密码
POSTGRES_HOST=postgres
POSTGRES_PORT=5432

# 或直接设置完整 URL
# DATABASE_URL=postgresql+asyncpg://scenic:请修改为强密码@postgres:5432/scenic

# JWT 密钥 — 务必修改为随机字符串！
SECRET_KEY=请随机生成64位字符串
# 生成密钥: openssl rand -hex 32

# 微信小程序
WX_APPID=你的AppID
WX_SECRET=你的AppSecret

# 服务器域名
SERVER_DOMAIN=https://你的域名.com
```

### 1.4 启动服务

```bash
# 构建并启动所有服务
docker compose up -d --build

# 查看日志
docker compose logs -f app

# 检查服务状态
docker compose ps
```

服务说明：

| 服务名 | 端口 | 说明 |
|--------|------|------|
| postgres | 5432 (仅内网) | PostgreSQL 16 数据库 |
| app | 8000 (仅内网) | FastAPI 后端应用 |
| nginx | 80 → HTTPS 443 | 反向代理 |

### 1.5 初始化种子数据（首次部署）

```bash
# 进入 app 容器执行种子脚本
docker compose exec app python seed.py

# 创建管理员账号（如果 seed.py 未包含）
docker compose exec app python init_admin.py
```

默认账号：
- 管理员: admin / admin123
- 游客: guest / guest123
- 工作人员: staff / staff123
- 前台: front_desk / frontdesk123

**生产环境务必修改默认密码！**

### 1.6 验证部署

```bash
# 健康检查
curl http://localhost/health

# API 文档
curl http://localhost/docs
```

浏览器访问:
- API 文档: http://你的域名/docs
- 管理后台: http://你的域名/admin
- 健康检查: http://你的域名/health

---

## 二、Nginx 反向代理配置

### 2.1 容器内配置（docker-compose）

项目自带 `nginx/nginx.conf`，由 docker-compose 自动挂载：

```
upstream backend {
    server app:8000;
}

server {
    listen 80;
    server_name localhost;

    location /api { proxy_pass http://backend; ... }
    location /docs { proxy_pass http://backend; ... }
    location /openapi.json { proxy_pass http://backend; ... }
    location /health { proxy_pass http://backend; ... }
    location / { proxy_pass http://backend; ... }
}
```

### 2.2 生产级配置要点

- `proxy_read_timeout` 设为 120s（大导出请求需要较长响应时间）
- `client_max_body_size` 设 10m（图片上传）
- 生产环境必须启用 HTTPS（见 SSL 章节）

---

## 三、SSL 证书配置（HTTPS）

### 3.1 使用 Let's Encrypt 免费证书

推荐使用 Certbot + Nginx 插件：

```bash
# 安装 certbot
apt update && apt install -y certbot python3-certbot-nginx

# 申请证书
certbot --nginx -d 你的域名.com -d api.你的域名.com
```

### 3.2 手动配置 SSL

如果你的 nginx 在宿主机运行（非 Docker），修改配置：

```nginx
server {
    listen 443 ssl http2;
    server_name 你的域名.com;

    ssl_certificate     /etc/letsencrypt/live/你的域名.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/你的域名.com/privkey.pem;

    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    location /api {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto https;
    }
}

# HTTP → HTTPS 重定向
server {
    listen 80;
    server_name 你的域名.com;
    return 301 https://$host$request_uri;
}
```

### 3.3 Docker Compose 中集成 SSL

修改 `docker-compose.yml` 中 nginx 服务，增加端口和证书挂载：

```yaml
nginx:
  image: nginx:alpine
  ports:
    - "80:80"
    - "443:443"
  volumes:
    - ./nginx/nginx.conf:/etc/nginx/conf.d/default.conf:ro
    - /etc/letsencrypt:/etc/letsencrypt:ro
```

### 3.4 自动续期

```bash
# certbot 自动续期 cron
echo "0 3 * * * certbot renew --quiet --post-hook 'docker compose restart nginx'" | crontab -
```

---

## 四、微信小程序配置

### 4.1 注册小程序

1. 前往 [微信公众平台](https://mp.weixin.qq.com/) 注册小程序
2. 获取 AppID 和 AppSecret
3. 将 AppID/AppSecret 填入 `.env` 文件

### 4.2 配置小程序项目

在微信开发者工具中打开 `miniapp/` 目录，修改 `project.config.json`：

```json
{
  "appid": "你的小程序AppID",
  "projectname": "scenic-tourism"
}
```

### 4.3 服务器域名白名单

在微信公众平台 → 开发管理 → 开发设置 → 服务器域名：

| 类型 | 域名 |
|------|------|
| request 合法域名 | https://你的域名.com |
|  | https://api.你的域名.com |
| socket 合法域名 | wss://你的域名.com |
| uploadFile 合法域名 | https://你的域名.com |
| downloadFile 合法域名 | https://你的域名.com |

**要求**: 以上域名必须已备案且启用 HTTPS。

### 4.4 小程序代码中修改 API 地址

查找小程序代码中的 API 基础路径（通常在 `app.js` 或 `utils/api.js`），修改为你的生产服务器地址：

```javascript
// 开发环境
const BASE_URL = 'http://localhost:8000'

// 生产环境
const BASE_URL = 'https://你的域名.com'
```

---

## 五、数据库迁移：SQLite → PostgreSQL

### 5.1 迁移原理

项目通过 `DEV_MODE` 环境变量自动切换数据库引擎：

| DEV_MODE | 数据库 | 驱动 |
|----------|--------|------|
| `true` (默认) | SQLite | aiosqlite |
| `false` | PostgreSQL | asyncpg |

切换由 `config.py` 的 `db_url` property 自动处理，无需修改任何代码。

### 5.2 从 SQLite 迁移到 PostgreSQL 的步骤

**方案一：重新生成数据（推荐）**

生产环境直接用种子脚本：

```bash
# 确保 DEV_MODE=false
docker compose exec app python seed.py
```

这会生成 3 个景区 + 票种 + 酒店 + 房型 + 停车场 + 公告 + POI + 天气缓存 + 评价 + 推荐点位 全套测试数据。

**方案二：手动导出导入**

```bash
# 1. 从 SQLite 导出为 SQL
sqlite3 backend/data/scenic.db .dump > dump.sql

# 2. 修改 SQL 兼容性（SQLite语法→PostgreSQL语法）
# - 删除 SQLite 特有的 PRAGMA
# - 将 INTEGER PRIMARY KEY AUTOINCREMENT 改为 SERIAL PRIMARY KEY
# - 将 DATETIME 默认值 'CURRENT_TIMESTAMP' 改为 NOW()

# 3. 导入到 PostgreSQL
docker compose exec -T postgres psql -U scenic -d scenic < dump.sql
```

**方案三：程序化迁移**

编写迁移脚本（适合已有生产数据）：

```python
# migrate.py
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.config import settings
from app.db import Base, User, TicketOrder, HotelOrder, ...

# 1. CREATE TABLE in PostgreSQL
pg_engine = create_engine(settings.DATABASE_URL.replace("+asyncpg", ""))
Base.metadata.create_all(pg_engine)

# 2. 从 SQLite 读取 → 写入 PostgreSQL
sqlite_engine = create_engine("sqlite:///data/scenic.db")
with Session(sqlite_engine) as src, Session(pg_engine) as dst:
    for user in src.query(User).all():
        dst.add(User(**{c.name: getattr(user, c.name) for c in User.__table__.columns}))
    dst.commit()
```

### 5.3 验证迁移

```bash
# 进入 PostgreSQL 检查
docker compose exec postgres psql -U scenic -d scenic -c "\dt"

# 检查 API 是否正常
curl http://localhost/api/scenic/info
```

---

## 六、日常运维命令

```bash
# 重启服务
docker compose restart app

# 查看日志
docker compose logs -f --tail=100 app

# 进入容器调试
docker compose exec app bash

# 数据库备份
docker compose exec postgres pg_dump -U scenic scenic > scenic_$(date +%Y%m%d).sql

# 更新代码后重新构建
git pull
docker compose up -d --build

# 查看资源使用
docker stats
```

## 七、安全注意事项

1. **修改默认密码**: 部署后立即修改 admin/staff/guest 等默认账号密码
2. **SECRET_KEY**: 使用 `openssl rand -hex 32` 生成的随机字符串
3. **数据库密码**: 使用强密码，不要使用 scenic123
4. **防火墙**: 仅开放 80/443 端口，5432 端口只监听到 127.0.0.1
5. **HTTPS**: 生产环境必须启用 SSL
6. **日志**: 定期清理 Nginx 和 app 的日志文件
7. **备份**: 设置 PostgreSQL 自动备份 cron 任务
=======
# 景区智慧管理系统 - 部署运维文档 v1.1

> 最后更新: 2026-06-12
> VPS: 43.163.5.90 (TencentOS, Docker)
> 后端端口: 8002 → 443 /scenic/ (HTTPS)
> 版本: v1.0.6 | API端点: 77 | 测试: 243 (全绿)
> 状态: 生产运行中

---

## 一、系统架构

```
                          ┌────────────────────┐
                          │   微信小程序        │
                          │   (miniapp/)        │
                          └────────┬───────────┘
                                   │ HTTPS
                          ┌────────▼───────────┐
                          │  Nginx (:443)       │
                          │  /scenic/ → :8002   │
                          └────────┬───────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              │                    │                    │
     ┌────────▼──────┐   ┌────────▼──────┐   ┌────────▼──────┐
     │  FastAPI       │   │  管理后台      │   │  SQLite/      │
     │  (:8002)       │   │  (admin/)      │   │  PostgreSQL   │
     └────────┬──────┘   │  静态托管       │   │  (持久化卷)    │
              │          └────────────────┘   └───────────────┘
     ┌────────▼──────┐
     │  OTA 对接      │
     │  携程/美团/飞猪 │
     └───────────────┘
```

---

## 二、项目结构

```
scenic/code/
├── backend/                # FastAPI 后端
│   ├── app/
│   │   ├── main.py         # 应用入口 (路由注册、CORS)
│   │   ├── config.py       # 配置管理 (环境变量)
│   │   ├── db.py           # 数据模型 + 异步引擎
│   │   └── api/            # API 路由模块
│   │       ├── auth.py     # 认证 (注册/登录/JWT)
│   │       ├── tickets.py  # 票务 (购票/核销/退款)
│   │       ├── hotels.py   # 酒店 (预订/入住/退房)
│   │       ├── payment.py  # 支付 (创建/回调/退款审核)
│   │       ├── dashboard.py # 仪表盘 (统计/营收/总览)
│   │       ├── scenic.py   # 景区信息 (POI/公告/评价/天气)
│   │       ├── parking.py  # 停车 (入场/出场/费率)
│   │       ├── export.py   # 数据导出 (CSV)
│   │       └── ota.py      # OTA对接 (携程/美团/飞猪)
│   ├── tests/              # API 测试 (243 tests, 96.1% 覆盖率)
│   ├── data/               # SQLite 数据库文件
│   ├── seed.py             # 种子数据脚本
│   ├── init_admin.py       # 管理员初始化
│   ├── Dockerfile          # 后端镜像
│   └── requirements.txt    # Python 依赖
├── admin/                  # 管理后台 (HTML/CSS/JS, 11页)
├── miniapp/                # 微信小程序 (6页)
├── docs/                   # 文档
│   ├── API.md              # API 接口文档
│   ├── GOVERNANCE.md       # 治理总纲
│   ├── BOUNDARIES.md       # 项目边界
│   └── RISK-TIERS.md       # 风险分级
├── docker-compose.yml      # Docker Compose 编排
└── Dockerfile              # 根 Dockerfile (含 admin/)
```

---

## 三、API 端点覆盖

| 模块 | 前缀 | 路由数 | 测试覆盖 | 覆盖率 |
|------|------|--------|---------|--------|
| 认证 | /api/auth | 3 | 3 | 100% |
| 景区信息 | /api/scenic | 16 | 15 | 93.8% |
| 票务 | /api/tickets | 8 | 7 | 87.5% |
| 酒店 | /api/hotels | 10 | 9 | 90.0% |
| 支付 | /api/payment | 8 | 8 | 100% |
| 仪表盘 | /api/dashboard | 3 | 3 | 100% |
| 停车 | /api/parking | 10 | 10 | 100% |
| 导出 | /api/export | 3 | 3 | 100% |
| OTA | /api/ota | 14 | 14 | 100% |
| 系统 | / | 2 | 2 | 100% |
| **总计** | | **77** | **74** | **96.1%** |

未覆盖端点（低优先级公开/管理接口）：
- `GET /api/scenic/list` — 景区列表分页（公开）
- `POST /api/tickets/batch-expire` — 批量过期处理（admin）
- `GET /api/hotels/orders/detail/{order_no}` — 按订单号查询客房订单（需登录）

---

## 四、环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| DEV_MODE | true | 开发模式 (SQLite) / 生产模式 (PostgreSQL) |
| APP_NAME | 景区智慧管理系统 | 应用名称 |
| APP_VERSION | 1.0.6 | 版本号 |
| DEBUG | false | 调试模式 |
| DATABASE_URL | (空) | PostgreSQL 连接串 (DEV_MODE=false 时必填) |
| POSTGRES_DB | scenic | PG 数据库名 |
| POSTGRES_USER | scenic | PG 用户名 |
| POSTGRES_PASSWORD | scenic123 | PG 密码 |
| POSTGRES_HOST | postgres | PG 主机 |
| POSTGRES_PORT | 5432 | PG 端口 |
| SECRET_KEY | scenic-jwt-secret-... | JWT 签名密钥 (生产必须更换!) |
| ACCESS_TOKEN_EXPIRE_MINUTES | 1440 | Token 过期时间 (分钟)，默认24h |
| WX_APPID | (空) | 微信小程序 AppID |
| WX_SECRET | (空) | 微信小程序 AppSecret |
| SERVER_DOMAIN | (空) | 服务器域名 |

---

## 五、本地开发

### 前置条件
- Python 3.11+
- pip

### 安装
```bash
cd scenic/code/backend
pip install -r requirements.txt
```

### 初始化数据
```bash
cd backend
python3 seed.py          # 创建种子数据 (景区/票种/酒店/订单)
python3 init_admin.py    # 创建管理员账户 admin/admin123
```

### 启动
```bash
cd backend
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

访问:
- API: http://localhost:8000
- Swagger: http://localhost:8000/docs
- 管理后台: http://localhost:8000/admin

### 运行测试
```bash
cd backend
python3 -m pytest tests/ -v
# 243 tests, ~2s
```

---

## 六、Docker 部署

### 构建 + 启动
```bash
cd scenic/code
docker compose up -d --build
```

服务端口: `8002`
数据持久化: Docker Volume `scenic_data` → `/app/data/scenic.db`

### docker-compose.yml
```yaml
services:
  scenic-backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: scenic-backend
    ports:
      - "8002:8002"
    environment:
      - DEV_MODE=true
      - APP_NAME=景区智慧管理系统
      - APP_VERSION=1.0.6
      - DEBUG=false
    volumes:
      - scenic_data:/app/data
    restart: unless-stopped

volumes:
  scenic_data:
```

### 常用命令
```bash
# 查看日志
docker logs -f scenic-backend

# 重启服务
docker compose restart

# 进入容器
docker exec -it scenic-backend bash

# 重建 (代码变更后)
docker compose up -d --build

# 停止
docker compose down
```

### 初始化 (首次部署)
```bash
# 先构建启动容器
docker compose up -d --build

# 进入容器初始化数据
docker exec -it scenic-backend python seed.py
docker exec -it scenic-backend python init_admin.py
```

---

## 七、VPS 生产部署

### 7.1 部署架构
```
Internet → :443 (Nginx) → /scenic/ → :8002 (Docker backend)
```

### 7.2 Nginx 配置
文件: `/root/scenic-nginx.conf` (已部署于 VPS 宿主机)
```
server {
    listen 443 ssl http2;
    server_name 43.163.5.90;
    ssl_certificate /etc/nginx/ssl/scenic.crt;
    ssl_certificate_key /etc/nginx/ssl/scenic.key;

    location /scenic/ {
        proxy_pass http://127.0.0.1:8002/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 7.3 VPS 部署步骤

```bash
# 1. SSH 到 VPS
ssh root@43.163.5.90

# 2. 拉取代码
cd ~/scenic/code
git pull origin main

# 3. 重建容器
cd ~/scenic/code
docker compose up -d --build

# 4. 首次部署需初始化数据
docker exec -it scenic-backend python seed.py
docker exec -it scenic-backend python init_admin.py

# 5. Nginx 配置变更后重载 (Tier 2 — 需确认)
cp ~/scenic/scenic-nginx.conf /etc/nginx/conf.d/
nginx -t && nginx -s reload

# 6. 验证
curl -k https://43.163.5.90/scenic/health
```

### 7.4 数据库备份
```bash
# 备份 SQLite
docker exec scenic-backend cp /app/data/scenic.db /app/data/scenic.db.$(date +%Y%m%d)

# 从宿主机备份
cp /var/lib/docker/volumes/scenic_scenic_data/_data/scenic.db ~/backups/
```

### 7.5 回滚步骤

回滚到上一个稳定版本：
```bash
# 1. SSH 到 VPS
ssh root@43.163.5.90

# 2. 查看 Git 历史找到稳定版本
cd ~/scenic/code
git log --oneline -20

# 3. 回滚到指定提交
git reset --hard <稳定提交hash>

# 4. 重建容器
docker compose up -d --build

# 5. 验证
curl -k https://43.163.5.90/scenic/health
```

注意事项：
- 数据库迁移不可逆 — 回滚前务必手动备份 DB
- 管理后台静态文件随代码部署，回滚后自动恢复
- 如需回滚到较远版本，建议先 dump DB 再重建

### 7.6 监控与健康检查

```bash
# API 健康检查（建议 crontab 每5分钟检测）
curl -sf https://43.163.5.90/scenic/health || echo "HEALTH CHECK FAILED"

# 容器资源监控
docker stats scenic-backend --no-stream

# 日志实时监控
docker logs -f scenic-backend --tail 100

# 磁盘使用
df -h /var/lib/docker

# 数据库大小
du -sh /var/lib/docker/volumes/scenic_scenic_data/_data/scenic.db
```

建议的 crontab 监控脚本 (`/root/scenic-monitor.sh`):
```bash
#!/bin/bash
# 景区后端健康监控
RESP=$(curl -sf -o /dev/null -w "%{http_code}" https://43.163.5.90/scenic/health)
if [ "$RESP" != "200" ]; then
    echo "[$(date)] 景区后端异常 HTTP:$RESP" >> /var/log/scenic-monitor.log
    # 可选: 发送告警短信/邮件/企业微信通知
fi
```

---

## 八、生产环境安全检查清单

- [ ] SECRET_KEY 已更换为高强度随机字符串
- [ ] DEV_MODE=false (PostgreSQL 替代 SQLite)
- [ ] DATABASE_URL 或 POSTGRES_* 已配置
- [ ] WX_APPID / WX_SECRET 已配置真实值
- [ ] OTA 渠道 api_key / api_secret 已配置生产密钥
- [ ] CORS_ORIGINS 限制为实际域名
- [ ] SSL 证书已部署
- [ ] 数据库定期备份 crontab 已设置
- [ ] admin 账户密码已更改

---

## 九、OTA 对接配置

### 携程 (Ctrip)
```
PUT /api/ota/configs/ctrip
Body: {
  "api_key": "生产密钥",
  "api_secret": "生产密钥",
  "hotel_id": "OTA侧酒店ID",
  "spot_id": "OTA侧景区ID",
  "is_enabled": true,
  "sync_interval_minutes": 5,
  "webhook_url": "https://api.ctrip.com/callback/order"
}
```

### 美团 (Meituan) / 飞猪 (Fliggy)
类似配置，见 API 文档第十节。

---

## 十、故障排查

### 容器无法启动
```bash
docker logs scenic-backend --tail 50
# 常见原因: 端口占用、数据库目录权限
```

### API 返回 500
```bash
docker exec scenic-backend python3 -m pytest tests/ -v
# 检查数据库完整性
```

### Nginx 502
```bash
# 确认后端容器运行中
docker ps | grep scenic

# 确认端口监听
curl http://127.0.0.1:8002/health
```

### 小程序无法连接
- 确认 VPS 防火墙开放 443
- 确认微信后台已配置服务器域名
- 确认 SSL 证书有效
>>>>>>> 3e8aa7ae9f42778437a7de7f58d54d5c0d4bfe96
