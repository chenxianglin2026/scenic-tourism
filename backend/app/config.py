"""
景区智慧管理系统 - 配置模块
DEV_MODE=True 使用 SQLite，否则使用 PostgreSQL
"""
from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import Optional
import os


class Settings(BaseSettings):
    # 应用基础
    APP_NAME: str = "景区智慧管理系统"
    APP_VERSION: str = "1.0.6"
    DEBUG: bool = True

    # 开发模式开关
    DEV_MODE: bool = True

    # 数据库 - dev 模式自动切 SQLite，prod 模式必须配置 DATABASE_URL
    DATABASE_URL: str = ""

    # PostgreSQL 容器连接参数（docker-compose 注入）
    POSTGRES_DB: Optional[str] = None
    POSTGRES_USER: Optional[str] = None
    POSTGRES_PASSWORD: Optional[str] = None
    POSTGRES_HOST: Optional[str] = None
    POSTGRES_PORT: Optional[str] = None

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def build_database_url_from_parts(cls, v):
        if v is None or str(v).strip() == "":
            pg_db = os.getenv("POSTGRES_DB", "scenic")
            pg_user = os.getenv("POSTGRES_USER", "scenic")
            pg_pass = os.getenv("POSTGRES_PASSWORD", "scenic123")
            pg_host = os.getenv("POSTGRES_HOST", "postgres")
            pg_port = os.getenv("POSTGRES_PORT", "5432")
            return f"postgresql+asyncpg://{pg_user}:{pg_pass}@{pg_host}:{pg_port}/{pg_db}"
        return v

    @property
    def db_url(self) -> str:
        if self.DEV_MODE:
            db_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
            os.makedirs(db_dir, exist_ok=True)
            return f"sqlite+aiosqlite:///{db_dir}/scenic.db"
        if not self.DATABASE_URL:
            raise ValueError(
                "DEV_MODE=False 且未配置 DATABASE_URL，"
                "请设置环境变量 DATABASE_URL 或 POSTGRES_* 系列变量"
            )
        return self.DATABASE_URL

    @property
    def db_sync_url(self) -> str:
        """同步引擎用（seed 脚本等）"""
        if self.DEV_MODE:
            db_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
            os.makedirs(db_dir, exist_ok=True)
            return f"sqlite:///{db_dir}/scenic.db"
        return self.DATABASE_URL.replace("+aiosqlite", "").replace("+asyncpg", "")

    # JWT 配置 — CHANGE IN PRODUCTION: set SECRET_KEY env var
    SECRET_KEY: str = "scenic-jwt-secret-change-in-production"  # default only for DEV_MODE
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 小时
    # 注册开关 (生产环境应设为 False)
    REGISTRATION_ENABLED: bool = True

    # CORS
    CORS_ORIGINS: list[str] = [
        "http://localhost:8000",
        "http://localhost:3000",
        "http://localhost:5173",
        "*",  # 小程序开发阶段允许所有来源
    ]

    # 微信小程序配置
    WX_APPID: str = ""
    WX_SECRET: str = ""

    # 微信支付 V3 配置（生产环境必填）
    WX_PAY_MCHID: str = ""
    WX_PAY_SERIAL_NO: str = ""
    WX_PAY_PRIVATE_KEY_PATH: str = ""
    WX_PAY_API_V3_KEY: str = ""

    # 服务器域名
    SERVER_DOMAIN: str = ""

    # TTLock 配置
    TTLOCK_CLIENT_ID: Optional[str] = None
    TTLOCK_CLIENT_SECRET: Optional[str] = None
    TTLOCK_USERNAME: Optional[str] = None
    TTLOCK_PASSWORD: Optional[str] = None

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
