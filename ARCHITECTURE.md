# 景区智慧管理系统 - 项目架构

> 最后更新: 2026-06-09

## 技术栈

- 后端: Python FastAPI + SQLite
- 前端: 微信小程序 (6 页面) + 管理后台 (11 页面)
- OTA: 携程/美团/飞猪对接框架 (810 行)
- 部署: Docker Compose
- VPS: 43.163.5.90:8002, nginx /scenic/ 代理
- 主题色: #c8a052 (金色)

## 目录结构

```
code/
├── backend/
│   ├── app/
│   │   ├── main.py          # FastAPI 入口
│   │   ├── db.py            # 数据模型 (15 个)
│   │   ├── config.py        # 配置
│   │   └── api/
│   │       ├── auth.py      # 认证
│   │       ├── scenic.py    # 景区信息/POI/推荐
│   │       ├── tickets.py   # 票务管理
│   │       ├── hotels.py    # 酒店/房型
│   │       ├── parking.py   # 停车管理
│   │       ├── ota.py       # OTA 渠道 (810行)
│   │       ├── export.py    # CSV 导出
│   │       ├── payment.py   # 支付
│   │       └── dashboard.py # 看板
│   ├── tests/test_api.py    # 177 测试
│   └── seed.py              # 种子数据 (泰山/西湖/黄山)
├── admin/                   # 管理后台 (11 页面)
├── miniapp/                 # 微信小程序 (6 页面)
│   ├── app.js
│   ├── utils/api.js
│   └── pages/
├── Dockerfile
└── docker-compose.yml
```

## VPS 部署

| 组件 | 端口 | 路径 |
|------|------|------|
| scenic-backend | 8002 | 直接映射 |
| 宿主机 nginx 443 | /scenic/ → 8002 | SSL 终止 |

## 景区数据

| 景区 | 经纬度 |
|------|--------|
| 泰山 | 36.2580, 117.1250 |
| 西湖 | 30.2375, 120.1398 |
| 黄山 | 30.1420, 118.1650 |

## 外部依赖

| 依赖 | 状态 |
|------|------|
| 小程序 AppID | 待注册 (企业打款验证) |
| 携程 OTA | 框架就绪 |
| 美团 OTA | 框架就绪 |
| 飞猪 OTA | 框架就绪 |
| 微信支付 | 未对接 |
