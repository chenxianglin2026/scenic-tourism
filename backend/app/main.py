"""
景区智慧管理系统 - FastAPI 入口
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db import init_db
from app.api import auth, tickets, hotels, dashboard


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
app.include_router(dashboard.router)


# 健康检查
@app.get("/health", tags=["系统"])
async def health_check():
    return {"status": "ok", "app": settings.APP_NAME, "version": settings.APP_VERSION}


@app.get("/")
async def root():
    return {
        "app": settings.APP_NAME,
        "api": {
            "auth": "/api/auth",
            "tickets": "/api/tickets",
            "hotels": "/api/hotels",
            "dashboard": "/api/dashboard",
        },
        "docs": "/docs",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
