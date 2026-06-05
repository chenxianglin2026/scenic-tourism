"""
景区智慧管理系统 - 认证 API
注册 / 登录 / JWT 鉴权
"""
import hashlib
import os
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from jose import JWTError, jwt

from app.config import settings
from app.db import get_db, User

router = APIRouter(prefix="/api/auth", tags=["认证"])

security = HTTPBearer()


# ── 密码工具 ─────────────────────────────────────────
def hash_password(pw: str) -> str:
    """SHA-256 加盐哈希"""
    salt = os.urandom(16)
    return salt.hex() + "$" + hashlib.sha256(salt + pw.encode()).hexdigest()


def verify_password(pw: str, hashed: str) -> bool:
    """验证密码"""
    try:
        salt_hex, hash_value = hashed.split("$", 1)
        salt = bytes.fromhex(salt_hex)
        return hashlib.sha256(salt + pw.encode()).hexdigest() == hash_value
    except (ValueError, IndexError):
        return False


# ── Schemas ──────────────────────────────────────────
class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=50)
    password: str = Field(..., min_length=6, max_length=128)
    phone: Optional[str] = Field(None, pattern=r"^1[3-9]\d{9}$")
    nickname: Optional[str] = None


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    username: str
    role: str
    nickname: Optional[str] = None


class UserInfo(BaseModel):
    id: int
    username: str
    phone: Optional[str]
    role: str
    nickname: Optional[str]
    avatar_url: Optional[str]
    is_active: bool

    model_config = {"from_attributes": True}


# ── JWT 工具 ───────────────────────────────────────
def _create_token(user: User) -> str:
    expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(user.id),
        "username": user.username,
        "role": user.role,
        "exp": expire,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def _token_response(user: User) -> TokenResponse:
    return TokenResponse(
        access_token=_create_token(user),
        user_id=user.id,
        username=user.username,
        role=user.role,
        nickname=user.nickname,
    )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """从 JWT token 解析当前用户（作为依赖注入使用）"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无效的认证凭据",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(credentials.credentials, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id_str = payload.get("sub")
        if user_id_str is None:
            raise credentials_exception
        user_id = int(user_id_str)
    except (JWTError, ValueError):
        raise credentials_exception

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise credentials_exception
    return user


async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """要求管理员角色"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return current_user


async def require_staff(current_user: User = Depends(get_current_user)) -> User:
    """要求工作人员角色（含admin）"""
    if current_user.role not in ("admin", "staff"):
        raise HTTPException(status_code=403, detail="需要工作人员权限")
    return current_user


# ── 路由 ─────────────────────────────────────────────
@router.post("/register", response_model=TokenResponse, summary="用户注册")
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(User).where(User.username == req.username))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="用户名已被注册")

    if req.phone:
        phone_exist = await db.execute(select(User).where(User.phone == req.phone))
        if phone_exist.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="手机号已被注册")

    user = User(
        username=req.username,
        phone=req.phone,
        hashed_password=hash_password(req.password),
        nickname=req.nickname or req.username,
        role="guest",
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return _token_response(user)


@router.post("/login", response_model=TokenResponse, summary="用户名密码登录")
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == req.username))
    user = result.scalar_one_or_none()

    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="账户已被禁用")

    return _token_response(user)


@router.get("/me", response_model=UserInfo, summary="获取当前用户信息")
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user
