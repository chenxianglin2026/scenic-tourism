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
