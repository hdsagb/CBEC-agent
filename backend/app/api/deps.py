from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db import get_db
from app.models.user import User

bearer_scheme = HTTPBearer(auto_error=False)

ROLE_HIERARCHY = {"merchandiser": 0, "customs": 1, "admin": 2}


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "未登录")
    payload = decode_access_token(credentials.credentials)
    if payload is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "登录已过期，请重新登录")
    user = db.get(User, int(payload.get("sub", "0")))
    if user is None or user.status != "active":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "账号不可用")
    return user


def require_role(minimum_role: str):
    def checker(user: User = Depends(get_current_user)) -> User:
        if ROLE_HIERARCHY.get(user.role, -1) < ROLE_HIERARCHY[minimum_role]:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "权限不足")
        return user

    return checker
