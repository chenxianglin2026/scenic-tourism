"""
景区智慧管理系统 - FastAPI 入口
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import os

from app.config import settings
from app.db import init_db
from app.api import auth, tickets, hotels, rooms, dashboard, payment, scenic, parking, export, ota, packages


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时：初始化数据库表
    await init_db()
    print(f"🚀 {settings.APP_NAME} v{settings.APP_VERSION} 启动成功")
    print(f"   DEV_MODE={settings.DEV_MODE}")
    print(f"   数据库: {settings.db_url}")
    yield
    # 关闭时清理


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="景区智慧管理系统后台 API — 票务+客房+管理",
    lifespan=lifespan,
)

# CORS — 允许小程序 + 管理后台
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(auth.router)
app.include_router(tickets.router)
app.include_router(hotels.router)
app.include_router(rooms.router)
app.include_router(dashboard.router)
app.include_router(payment.router)
app.include_router(scenic.router)
app.include_router(parking.router)

# 注册导出路由
app.include_router(export.router)

# 注册OTA对接路由
app.include_router(ota.router)

# 注册套餐组合路由
app.include_router(packages.router)

# 托管管理后台静态文件（本地调试）
admin_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'admin')
if os.path.exists(admin_path):
    app.mount("/admin", StaticFiles(directory=admin_path, html=True), name="admin")

# 健康检查
@app.get("/health", tags=["系统"])
async def health_check():
    return {"status": "ok", "app": settings.APP_NAME, "version": settings.APP_VERSION}


@app.get("/", response_class=HTMLResponse)
async def root():
    return """<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>景区智慧管理系统</title>
<style>*{margin:0;padding:0;box-sizing:border-box}body{font:16px -apple-system,"PingFang SC","Microsoft YaHei",sans-serif;text-align:center;background:linear-gradient(135deg,#2b8a3e,#1a6b2e);color:#fff;min-height:100vh;display:flex;flex-direction:column;align-items:center;justify-content:center}.c{max-width:320px;width:90%}.lg{font-size:48px;margin-bottom:8px}h1{font-size:28px;font-weight:700;margin-bottom:6px}.sub{font-size:14px;opacity:.7;margin-bottom:36px}.btn{display:block;padding:16px 20px;margin:12px 0;background:rgba(255,255,255,.12);border:1px solid rgba(255,255,255,.15);border-radius:14px;color:#fff;text-decoration:none;font-size:16px;font-weight:500;transition:.2s;text-align:center}.btn:hover{background:rgba(255,255,255,.22);transform:translateY(-1px)}.ic{font-size:20px;margin-right:6px;vertical-align:middle}.ar{float:right;opacity:.5;font-size:14px;line-height:1.4}.ft{position:fixed;bottom:20px;left:0;right:0;font-size:12px;opacity:.5;text-align:center}.ft a{color:#fff;text-decoration:none}</style></head>
<body><div class=c><div class=lg>🏞️</div><h1>景区智慧管理系统</h1><div class=sub>门票 · 酒店 · 停车一站式管理</div>
<a class=btn href=/scenic/admin/><span class=ic>🔐</span>管理员登录<span class=ar>›</span></a>
<a class=btn href=/scenic/docs><span class=ic>📖</span>API 文档<span class=ar>›</span></a>
</div><div class=ft><a href=https://beian.miit.gov.cn target=_blank>粤ICP备16027093号-1</a></div></body></html>"""


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
