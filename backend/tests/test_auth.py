"""B 组用例：认证（注册 / 登录 / JWT 校验 / 停用账号 / 启动安全自检）。"""
import pytest

from app.core.config import Settings
from app.db import SessionLocal
from app.models.user import User

PASSWORD = "test12345"


def test_b1_register_ignores_client_role(client):
    """SEC-01 回归：注册接口不接受客户端指定角色，传 role=admin 也只落为 merchandiser。"""
    resp = client.post(
        "/api/auth/register",
        json={"username": "b1_user", "password": PASSWORD, "display_name": "普通用户", "role": "admin"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["username"] == "b1_user"
    assert body["role"] == "merchandiser"
    assert body["status"] == "active"


def test_b2_duplicate_username(client, register_user):
    register_user("b2_dup")
    resp = client.post("/api/auth/register", json={"username": "b2_dup", "password": PASSWORD})
    assert resp.status_code == 400
    assert "已存在" in resp.json()["detail"]


def test_b3_login_returns_token_and_user(client, users):
    data = users["admin"]["user"]
    assert data["role"] == "admin"
    # users 夹具内部已完成登录并拿到 token，这里再显式登录一次验证响应结构
    resp = client.post("/api/auth/login", json={"username": "t_admin", "password": PASSWORD})
    body = resp.json()
    assert resp.status_code == 200
    assert body["access_token"]
    assert body["user"]["username"] == "t_admin"


def test_b4_login_wrong_password(client, register_user):
    register_user("b4_user")
    resp = client.post("/api/auth/login", json={"username": "b4_user", "password": "wrong-pass"})
    assert resp.status_code == 401
    assert "用户名或密码错误" in resp.json()["detail"]


def test_b5_me_with_valid_token(client, users):
    resp = client.get("/api/auth/me", headers=users["customs"]["headers"])
    assert resp.status_code == 200
    assert resp.json()["username"] == "t_customs"


def test_b6_me_rejects_missing_or_bad_token(client):
    # 无 token
    assert client.get("/api/auth/me").status_code == 401
    # 伪造 token
    fake = client.get("/api/auth/me", headers={"Authorization": "Bearer fake.token.here"})
    assert fake.status_code == 401
    # 缺 Bearer 前缀
    bad = client.get("/api/auth/me", headers={"Authorization": "abc"})
    assert bad.status_code == 401


def test_b7_disabled_user_blocked(client, register_user, login_user):
    register_user("b7_disabled")
    data = login_user("b7_disabled")  # 停用前可正常登录
    old_headers = {"Authorization": f"Bearer {data['access_token']}"}

    db = SessionLocal()
    db.query(User).filter(User.username == "b7_disabled").update({"status": "disabled"})
    db.commit()
    db.close()

    # 停用后重新登录被拦截（403）
    resp = client.post("/api/auth/login", json={"username": "b7_disabled", "password": PASSWORD})
    assert resp.status_code == 403
    assert "停用" in resp.json()["detail"]
    # 停用前签发的 token 也失效（/me 401）
    resp = client.get("/api/auth/me", headers=old_headers)
    assert resp.status_code == 401
    assert "不可用" in resp.json()["detail"]


def test_b8_register_cannot_grant_privileges(client, login_user):
    """SEC-01 回归：注册提权被封死后，特权接口对自助注册账号一律 403。"""
    resp = client.post(
        "/api/auth/register",
        json={"username": "b8_escalate", "password": PASSWORD, "role": "admin"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["role"] == "merchandiser"

    headers = {"Authorization": f"Bearer {login_user('b8_escalate')['access_token']}"}
    assert client.get("/api/auth/me", headers=headers).json()["role"] == "merchandiser"
    # 导入模板属 customs 及以上专属，普通注册账号应被拦截
    gated = client.get("/api/elements/template", headers=headers)
    assert gated.status_code == 403
    assert gated.json()["detail"] == "权限不足"


@pytest.mark.parametrize(
    "weak",
    ["", "change-me-to-a-random-long-string", "dev-secret-change-me", "secret", "abc123"],
)
def test_b9_insecure_jwt_secret_rejected(weak):
    """SEC-02 回归：空值、示例值与过短的 JWT_SECRET 在启动自检阶段被拒绝。"""
    with pytest.raises(RuntimeError):
        Settings(jwt_secret=weak).validate_security()


def test_b10_strong_jwt_secret_accepted():
    """SEC-02 回归：足够长的随机密钥可通过启动自检。"""
    Settings(jwt_secret="a" * 32).validate_security()
