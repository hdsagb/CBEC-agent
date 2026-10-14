"""预置指定角色的账号（运维脚本）。

自助注册接口只能创建 merchandiser 账号，因此 admin / customs 必须由
具备服务器访问权限的人通过本脚本创建：

    # 本地开发（在 backend 目录下）
    .venv\\Scripts\\python.exe -m app.scripts.create_user admin "强密码" --role admin

    # Docker 部署（在仓库根目录）
    docker compose -f deploy/docker-compose.yml exec api python -m app.scripts.create_user admin "强密码" --role admin

脚本幂等性说明：用户名已存在时直接报错退出，不会覆盖既有密码。
"""
import argparse

from app.core.security import hash_password
from app.db import Base, SessionLocal, engine
from app.models.user import User

VALID_ROLES = ("merchandiser", "customs", "admin")


def create_user(
    username: str, password: str, role: str = "merchandiser", display_name: str = ""
) -> User:
    """创建账号；用户名重复或角色非法时抛 ValueError。

    供 CLI 与测试夹具复用，故不吞异常，由调用方决定如何呈现。
    """
    if role not in VALID_ROLES:
        raise ValueError(f"非法角色：{role}，可选 {', '.join(VALID_ROLES)}")
    db = SessionLocal()
    try:
        if db.query(User).filter(User.username == username).first():
            raise ValueError(f"用户名已存在：{username}")
        user = User(
            username=username,
            password_hash=hash_password(password),
            display_name=display_name or username,
            role=role,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="创建指定角色的账号")
    parser.add_argument("username", help="登录用户名")
    parser.add_argument("password", help="登录密码")
    parser.add_argument("--role", default="merchandiser", choices=VALID_ROLES, help="账号角色")
    parser.add_argument("--display-name", default="", help="显示名称，缺省与用户名相同")
    args = parser.parse_args()

    # 本地开发可能尚未建表，先与启动逻辑保持一致地补建
    Base.metadata.create_all(bind=engine)
    try:
        user = create_user(args.username, args.password, args.role, args.display_name)
    except ValueError as exc:
        raise SystemExit(f"创建失败：{exc}")
    print(f"已创建账号 {user.username}（角色 {user.role}）")


if __name__ == "__main__":
    main()
