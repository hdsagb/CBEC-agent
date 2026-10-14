"""pytest 全局夹具：独立临时 SQLite，与开发库完全隔离。

注意：必须先设置环境变量再导入 app.*，config.Settings 在导入时求值。
"""
import os
import sys
import tempfile
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_BACKEND_DIR))

_TEST_DB = Path(tempfile.gettempdir()) / "_pytest_cbec.db"
if _TEST_DB.exists():
    _TEST_DB.unlink()
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB.as_posix()}"
# 导出产物写入临时目录，避免污染开发库的 ./uploads
os.environ["UPLOAD_DIR"] = str(Path(tempfile.gettempdir()) / "_pytest_cbec_uploads")
# 启动自检会拒绝示例密钥，测试环境注入固定长密钥（环境变量优先于 .env）
os.environ["JWT_SECRET"] = "pytest-only-secret-0123456789abcdef"

import pytest
from fastapi.testclient import TestClient

from app.db import Base, engine
from app.main import app
from app.schemas.auth import UserOut
from app.scripts.create_user import create_user

PASSWORD = "test12345"


@pytest.fixture()
def client():
    """每个用例独立的空数据库 + TestClient。"""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def register_user(client):
    """自助注册，失败时给出响应体方便排查。角色由服务端固定为 merchandiser。"""

    def _register(username: str, password: str = PASSWORD):
        resp = client.post(
            "/api/auth/register",
            json={"username": username, "password": password, "display_name": username},
        )
        assert resp.status_code == 200, resp.text
        return resp.json()

    return _register


@pytest.fixture()
def create_role_user(client):
    """按指定角色直接预置账号，等价于运维脚本 app.scripts.create_user。"""

    def _create(username: str, role: str, password: str = PASSWORD):
        user = create_user(username, password, role=role)
        return UserOut.model_validate(user).model_dump()

    return _create


@pytest.fixture()
def login_user(client):
    """登录用户，返回 {access_token, user}。"""

    def _login(username: str, password: str = PASSWORD):
        resp = client.post("/api/auth/login", json={"username": username, "password": password})
        assert resp.status_code == 200, resp.text
        return resp.json()

    return _login


@pytest.fixture()
def users(create_role_user, login_user):
    """三角色账号与鉴权头：{role: {user, headers}}。

    注册接口只能创建 merchandiser，admin / customs 走预置路径，
    与真实部署（运维脚本建号）保持一致。
    """
    out = {}
    for role in ("admin", "customs", "merchandiser"):
        user = create_role_user(f"t_{role}", role)
        data = login_user(f"t_{role}")
        out[role] = {"user": user, "headers": {"Authorization": f"Bearer {data['access_token']}"}}
    return out
