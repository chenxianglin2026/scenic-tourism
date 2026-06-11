# 景区智慧管理系统 - 部署文档 v1.0

> 最后更新: 2026-06-11
> VPS: 43.163.5.90 (TencentOS, Docker)
> 后端端口: 8002 → 443 /scenic/ (HTTPS)
> 状态: v0.2.0 运行中

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
│   ├── tests/              # API 测试 (238 tests)
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

## 三、环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| DEV_MODE | true | 开发模式 (SQLite) / 生产模式 (PostgreSQL) |
| APP_NAME | 景区智慧管理系统 | 应用名称 |
| APP_VERSION | 0.2.0 | 版本号 |
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

## 四、本地开发

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
# 238 tests, ~2s
```

---

## 五、Docker 部署

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
      - APP_VERSION=0.2.0
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

## 六、VPS 生产部署

### 6.1 部署架构
```
Internet → :443 (Nginx) → /scenic/ → :8002 (Docker backend)
```

### 6.2 Nginx 配置
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

### 6.3 VPS 部署步骤

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

### 6.4 数据库备份
```bash
# 备份 SQLite
docker exec scenic-backend cp /app/data/scenic.db /app/data/scenic.db.$(date +%Y%m%d)

# 从宿主机备份
cp /var/lib/docker/volumes/scenic_scenic_data/_data/scenic.db ~/backups/
```

---

## 七、生产环境安全检查清单

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

## 八、OTA 对接配置

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

## 九、故障排查

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
