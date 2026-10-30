"""全局模型配置用例：权限、加密落库、热切换、SSRF 防护与连通性探测分类。"""
import time

import httpx
import pytest

from app.db import SessionLocal
from app.models.llm_config import LLMConfig

URL = "/api/settings/llm"
SAFE_BASE = "https://api.example.com/v1"
GOOD_KEY = "sk-test-1234567890"


@pytest.fixture(autouse=True)
def _reset_llm_state():
    """清空进程内配置缓存与探测缓存，避免用例之间互相影响。"""
    from app.api.routers import settings as settings_router
    from app.services.llm import config_store, probe

    config_store.invalidate()
    probe.invalidate_probe_cache()
    settings_router._last_test_at = 0.0
    yield
    config_store.invalidate()
    probe.invalidate_probe_cache()


def _save(client, headers, **overrides):
    payload = {"provider": "openai", "base_url": SAFE_BASE, "model": "gpt-4o-mini",
               "api_key": GOOD_KEY}
    payload.update(overrides)
    return client.put(URL, json=payload, headers=headers)


@pytest.fixture()
def without_env_key(monkeypatch):
    """屏蔽 .env 里的兜底 Key，让「未配置」路径可被确定性地断言。"""
    from app.core.config import settings
    from app.services.llm import config_store

    monkeypatch.setattr(settings, "deepseek_api_key", "")
    config_store.invalidate()


def test_requires_auth(client):
    assert client.get(URL).status_code == 401
    assert client.put(URL, json={"base_url": SAFE_BASE, "model": "m"}).status_code == 401


def test_env_fallback_unconfigured(client, users, without_env_key):
    resp = client.get(URL, headers=users["merchandiser"]["headers"])
    assert resp.status_code == 200
    body = resp.json()
    assert body["source"] == "env"
    assert body["status"] == "unconfigured"
    assert body["api_key_configured"] is False
    assert body["can_edit"] is False


def test_update_requires_admin(client, users):
    resp = _save(client, users["merchandiser"]["headers"])
    assert resp.status_code == 403


def test_save_encrypts_and_hot_switches(client, users):
    resp = _save(client, users["admin"]["headers"])
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["source"] == "db"
    assert body["api_key_masked"] == "sk-****7890"
    assert body["api_key_configured"] is True
    assert body["can_edit"] is True
    assert body["status"] == "unknown"

    # 数据库只存密文，不能出现明文 Key
    with SessionLocal() as db:
        row = db.get(LLMConfig, 1)
        assert row is not None
        assert GOOD_KEY not in row.api_key_cipher
        assert row.api_key_cipher.startswith("v1:")

    # 保存后无需重启：客户端立即使用新配置
    from app.services.llm.base import get_llm_client

    llm = get_llm_client()
    assert llm.model == "gpt-4o-mini"
    assert llm.base_url == SAFE_BASE
    assert llm.api_key == GOOD_KEY


def test_blank_key_keeps_previous_and_empty_clears(client, users, without_env_key):
    headers = users["admin"]["headers"]
    assert _save(client, headers).status_code == 200

    # 不传 api_key（null）表示保持原值
    resp = client.put(URL, json={"base_url": SAFE_BASE, "model": "gpt-4o-mini"}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["api_key_masked"] == "sk-****7890"

    # 传空字符串表示清除；清除后回退到环境变量配置
    resp = client.put(
        URL, json={"base_url": SAFE_BASE, "model": "gpt-4o-mini", "api_key": ""}, headers=headers
    )
    assert resp.status_code == 200
    assert resp.json()["api_key_configured"] is False
    assert resp.json()["source"] == "env"


@pytest.mark.parametrize(
    "base_url",
    [
        "http://api.example.com/v1",  # 非 HTTPS
        "https://127.0.0.1:8000/v1",  # 环回
        "https://192.168.1.10/v1",  # 私网
        "https://ollama.local/v1",  # 内网域名后缀
        "https://user:pass@api.example.com/v1",  # 带账号密码
        "ftp://api.example.com",  # 非法协议
        "",
    ],
)
def test_ssrf_guard(client, users, base_url):
    resp = _save(client, users["admin"]["headers"], base_url=base_url)
    assert resp.status_code == 400


def test_missing_model_name_rejected(client, users):
    resp = _save(client, users["admin"]["headers"], model="  ")
    assert resp.status_code == 400


class _FakeResponse:
    def __init__(self, status_code: int, text: str = "") -> None:
        self.status_code = status_code
        self.text = text


def _probe_config():
    from app.services.llm.config_store import RuntimeLLMConfig

    return RuntimeLLMConfig(
        provider="openai", base_url=SAFE_BASE, model="gpt-4o-mini", api_key=GOOD_KEY, source="env"
    )


@pytest.mark.parametrize(
    "code,expected",
    [(200, "ok"), (401, "auth_failed"), (429, "rate_limited"), (404, "not_found"),
     (500, "server_error"), (418, "bad_response")],
)
def test_probe_status_classification(monkeypatch, code, expected):
    from app.services.llm import probe

    monkeypatch.setattr(probe.httpx, "get", lambda *a, **k: _FakeResponse(code))
    if code == 404:
        monkeypatch.setattr(probe.httpx, "post", lambda *a, **k: _FakeResponse(404))
    result = probe.probe(_probe_config(), force=True)
    assert result.status == expected


def test_probe_timeout_and_unreachable(monkeypatch):
    from app.services.llm import probe

    def _timeout(*a, **k):
        raise httpx.ConnectTimeout("boom")

    monkeypatch.setattr(probe.httpx, "get", _timeout)
    assert probe.probe(_probe_config(), force=True).status == "timeout"

    monkeypatch.setattr(probe.httpx, "get", lambda *a, **k: _FakeResponse(405))
    monkeypatch.setattr(probe.httpx, "post", lambda *a, **k: _FakeResponse(200))
    assert probe.probe(_probe_config(), force=True).status == "ok"


def test_probe_unconfigured_skips_network(monkeypatch):
    from app.services.llm import probe
    from app.services.llm.config_store import RuntimeLLMConfig

    monkeypatch.setattr(
        probe.httpx, "get", lambda *a, **k: pytest.fail("未配置时不应发起网络请求")
    )
    config = RuntimeLLMConfig(provider="openai", base_url="", model="", api_key="")
    assert probe.probe(config, force=True).status == "unconfigured"


def test_refresh_allowed_for_non_admin(client, users, monkeypatch):
    from app.services.llm import probe

    monkeypatch.setattr(probe.httpx, "get", lambda *a, **k: _FakeResponse(200))
    # 环境变量兜底时需要 Key，临时注入
    from app.core.config import settings

    monkeypatch.setattr(settings, "deepseek_api_key", GOOD_KEY)

    resp = client.post(f"{URL}/refresh", headers=users["merchandiser"]["headers"])
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "ok"

    got = client.get(URL, headers=users["merchandiser"]["headers"])
    assert got.json()["status"] == "ok"
    assert got.json()["can_edit"] is False


def test_test_endpoint_cooldown_and_unconfigured(client, users, without_env_key):
    from app.api.routers import settings as settings_router

    admin = users["admin"]["headers"]
    resp = client.post(f"{URL}/test", headers=admin)
    assert resp.status_code == 200
    assert resp.json()["status"] == "unconfigured"

    # 3 秒内重复点击应被限流，避免打满模型服务
    settings_router._last_test_at = time.monotonic()
    assert client.post(f"{URL}/test", headers=admin).status_code == 429


def test_test_endpoint_requires_admin(client, users):
    assert client.post(f"{URL}/test", headers=users["customs"]["headers"]).status_code == 403
