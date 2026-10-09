"""pytest 全局夹具：独立临时 SQLite，与开发库完全隔离。

注意：必须先设置 DATABASE_URL 再导入 app.*，config.Settings 在导入时求值。
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

import pytest
from fastapi.testclient import TestClient

from app.db import Base, engine
from app.main import app

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
    """注册用户，失败时给出响应体方便排查。"""

    def _register(username: str, role: str = "merchandiser", password: str = PASSWORD):
        resp = client.post(
            "/api/auth/register",
            json={"username": username, "password": password, "display_name": username, "role": role},
        )
        assert resp.status_code == 200, resp.text
        return resp.json()

    return _register


@pytest.fixture()
def login_user(client):
    """登录用户，返回 {access_token, user}。"""

    def _login(username: str, password: str = PASSWORD):
        resp = client.post("/api/auth/login", json={"username": username, "password": password})
        assert resp.status_code == 200, resp.text
        return resp.json()

    return _login


@pytest.fixture()
def users(register_user, login_user):
    """三角色账号与鉴权头：{role: {user, headers}}。"""
    out = {}
    for role in ("admin", "customs", "merchandiser"):
        user = register_user(f"t_{role}", role=role)
        data = login_user(f"t_{role}")
        out[role] = {"user": user, "headers": {"Authorization": f"Bearer {data['access_token']}"}}
    return out
