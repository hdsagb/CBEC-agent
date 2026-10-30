"""大模型连通性探测：优先 GET /models，个别服务 404/405 时回退最小 chat 请求。

结果按「地址 + 模型 + Key 指纹」缓存 60 秒，避免多人同时打开页面把探测请求打满。
"""

import hashlib
import logging
import time
from dataclasses import dataclass
from datetime import datetime

import httpx

from app.services.llm.config_store import RuntimeLLMConfig

logger = logging.getLogger("cbec")

TIMEOUT_SECONDS = 10.0
CACHE_TTL_SECONDS = 60.0

# 页面状态灯依据：ok=绿；unconfigured=灰；unknown=黄；其余=红
_probe_cache: dict[str, tuple[float, "ProbeResult"]] = {}


@dataclass(frozen=True)
class ProbeResult:
    status: str
    message: str
    latency_ms: int
    checked_at: datetime


def invalidate_probe_cache() -> None:
    _probe_cache.clear()


def probe(config: RuntimeLLMConfig, force: bool = False) -> ProbeResult:
    if not config.configured:
        return ProbeResult(
            status="unconfigured",
            message="尚未配置可用的模型地址、模型名称与 API Key",
            latency_ms=0,
            checked_at=datetime.utcnow(),
        )

    fingerprint = _fingerprint(config)
    now = time.monotonic()
    cached = _probe_cache.get(fingerprint)
    if not force and cached is not None and cached[0] > now:
        return cached[1]

    start = time.perf_counter()
    status, message = _request(config)
    result = ProbeResult(
        status=status,
        message=message,
        latency_ms=int((time.perf_counter() - start) * 1000),
        checked_at=datetime.utcnow(),
    )
    _probe_cache[fingerprint] = (now + CACHE_TTL_SECONDS, result)
    return result


def _fingerprint(config: RuntimeLLMConfig) -> str:
    key_digest = hashlib.sha256(config.api_key.encode("utf-8")).hexdigest()[:12]
    raw = f"{config.base_url}|{config.model}|{key_digest}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _request(config: RuntimeLLMConfig) -> tuple[str, str]:
    headers = {"Authorization": f"Bearer {config.api_key}"}
    try:
        resp = httpx.get(
            f"{config.base_url}/models",
            headers=headers,
            timeout=TIMEOUT_SECONDS,
            follow_redirects=False,
        )
    except httpx.TimeoutException:
        return "timeout", f"连接模型服务超时（>{int(TIMEOUT_SECONDS)}s）"
    except httpx.HTTPError as exc:
        return "unreachable", f"无法连接模型服务：{type(exc).__name__}"

    if resp.status_code == 200:
        return "ok", "连接正常"
    if resp.status_code in (404, 405):
        # 部分兼容实现没有实现 /models，改用一次最小对话请求验证
        return _chat_probe(config, headers)
    return _classify(resp.status_code)


def _chat_probe(config: RuntimeLLMConfig, headers: dict) -> tuple[str, str]:
    body = {
        "model": config.model,
        "messages": [{"role": "user", "content": "ping"}],
        "max_tokens": 1,
    }
    try:
        resp = httpx.post(
            f"{config.base_url}/chat/completions",
            headers=headers,
            json=body,
            timeout=TIMEOUT_SECONDS,
            follow_redirects=False,
        )
    except httpx.TimeoutException:
        return "timeout", f"对话接口超时（>{int(TIMEOUT_SECONDS)}s）"
    except httpx.HTTPError as exc:
        return "unreachable", f"无法连接对话接口：{type(exc).__name__}"

    if resp.status_code == 200:
        return "ok", "连接正常（经最小对话请求验证）"
    if resp.status_code == 400:
        return "bad_request", "接口已连通，但测试请求被拒绝（请检查模型名称是否正确）"
    return _classify(resp.status_code)


def _classify(code: int) -> tuple[str, str]:
    if code in (401, 403):
        return "auth_failed", "API Key 无效或没有访问权限"
    if code == 429:
        return "rate_limited", "模型服务限流（429），请稍后重试"
    if code == 404:
        return "not_found", "接口或模型不存在，请检查接口地址与模型名称"
    if code >= 500:
        return "server_error", f"模型服务异常（HTTP {code}）"
    return "bad_response", f"模型服务返回异常状态（HTTP {code}）"
