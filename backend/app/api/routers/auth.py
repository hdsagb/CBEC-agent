import threading
import time

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.security import create_access_token, hash_password, verify_password
from app.db import get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenOut, UserOut

router = APIRouter(prefix="/api/auth", tags=["auth"])

# 同一「客户端 IP + 用户名」在窗口期内失败达到上限后直接拒绝，阻止在线爆破密码。
# 计数只保存在进程内存中，当前 uvicorn 单 worker 部署下足够；多 worker 时需换 Redis。
LOGIN_MAX_FAILURES = 5
LOGIN_FAILURE_WINDOW = 5 * 60

_login_failures: dict[str, list[float]] = {}
_login_failures_lock = threading.Lock()


def _login_key(request: Request, username: str) -> str:
    # 经 nginx 反代时 client.host 是网关地址，优先取它写入的真实客户端 IP
    ip = request.headers.get("x-real-ip") or (request.client.host if request.client else "unknown")
    return f"{ip}|{username.strip().lower()}"


def _ensure_not_locked(key: str) -> None:
    now = time.monotonic()
    with _login_failures_lock:
        recent = [t for t in _login_failures.get(key, []) if now - t < LOGIN_FAILURE_WINDOW]
        if recent:
            _login_failures[key] = recent
        else:
            _login_failures.pop(key, None)
    if len(recent) >= LOGIN_MAX_FAILURES:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "登录失败次数过多，请 5 分钟后再试",
            headers={"Retry-After": str(LOGIN_FAILURE_WINDOW)},
        )


def _record_login_failure(key: str) -> None:
    now = time.monotonic()
    with _login_failures_lock:
        # 顺手清掉整个窗口内都已过期的键，防止大量随机用户名把内存撑大
        for old_key in [
            k for k, times in _login_failures.items() if now - times[-1] >= LOGIN_FAILURE_WINDOW
        ]:
            _login_failures.pop(old_key, None)
        _login_failures.setdefault(key, []).append(now)


def _clear_login_failures(key: str) -> None:
    with _login_failures_lock:
        _login_failures.pop(key, None)


@router.post("/register", response_model=UserOut)
def register(req: RegisterRequest, db: Session = Depends(get_db)) -> User:
    """自助注册：角色固定为 merchandiser，不接受客户端指定角色。

    提权路径被封死后，admin / customs 账号由运维脚本预置
    （见 app/scripts/create_user.py）。
    """
    if db.query(User).filter(User.username == req.username).first():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "用户名已存在")
    user = User(
        username=req.username,
        password_hash=hash_password(req.password),
        display_name=req.display_name or req.username,
        role="merchandiser",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=TokenOut)
def login(req: LoginRequest, request: Request, db: Session = Depends(get_db)) -> TokenOut:
    key = _login_key(request, req.username)
    _ensure_not_locked(key)
    user = db.query(User).filter(User.username == req.username).first()
    if not user or not verify_password(req.password, user.password_hash):
        _record_login_failure(key)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "用户名或密码错误")
    if user.status != "active":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "账号已停用")
    _clear_login_failures(key)
    token = create_access_token(user.id, user.role)
    return TokenOut(access_token=token, user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> User:
    return user
