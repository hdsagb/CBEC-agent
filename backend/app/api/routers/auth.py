from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.security import create_access_token, hash_password, verify_password
from app.db import get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenOut, UserOut

router = APIRouter(prefix="/api/auth", tags=["auth"])


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
def login(req: LoginRequest, db: Session = Depends(get_db)) -> TokenOut:
    user = db.query(User).filter(User.username == req.username).first()
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "用户名或密码错误")
    if user.status != "active":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "账号已停用")
    token = create_access_token(user.id, user.role)
    return TokenOut(access_token=token, user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> User:
    return user
