"""大模型运行时配置：数据库优先、环境变量兜底，进程内缓存 + 保存即热切换。

设计要点：
- 全局只有一套配置（llm_config 表单行，id 固定为 1），管理员写入、全员读取。
- 数据库中存的是加密后的 API Key，读出时才解密；对外只暴露掩码。
- 进程内缓存 15 秒：保存后立即 invalidate，单进程即时生效；多进程最迟 15 秒生效。
"""

import ipaddress
import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.crypto import decrypt_secret, encrypt_secret
from app.models.llm_config import LLMConfig

logger = logging.getLogger("cbec")

CACHE_TTL_SECONDS = 15.0
_CONFIG_ID = 1

_BLOCKED_HOST_SUFFIXES = (".local", ".internal", ".localhost")

_cache_lock = threading.Lock()
_cache_value: "RuntimeLLMConfig | None" = None
_cache_expires = 0.0

# 环境变量兜底的探测结果只存在内存中（没有可写的数据库行）
_env_status: dict[str, object] = {
    "status": "unknown",
    "error": "",
    "checked_at": None,
}


@dataclass(frozen=True)
class RuntimeLLMConfig:
    """运行中的模型配置快照；密钥字段不进入 repr，避免误打印到日志。"""

    provider: str
    base_url: str
    model: str
    api_key: str = field(default="", repr=False)
    vision_model: str = ""
    vision_base_url: str = ""
    vision_api_key: str = field(default="", repr=False)
    source: str = "env"

    @property
    def configured(self) -> bool:
        """地址、模型名、Key 三者齐全才认为可调用。"""
        return bool(self.base_url and self.model and self.api_key)

    @property
    def vision_enabled(self) -> bool:
        return bool(self.vision_model)


def invalidate() -> None:
    """清除进程内缓存，使下一次读取直接命中数据库（用于保存后热切换）。"""
    global _cache_value, _cache_expires
    with _cache_lock:
        _cache_value = None
        _cache_expires = 0.0


def load_config(db: Session | None = None, use_cache: bool = True) -> RuntimeLLMConfig:
    """读取当前生效的配置：数据库行存在且完整时优先，否则回退环境变量。"""
    global _cache_value, _cache_expires

    if use_cache:
        with _cache_lock:
            if _cache_value is not None and time.monotonic() < _cache_expires:
                return _cache_value

    config = _load_uncached(db)
    with _cache_lock:
        _cache_value = config
        _cache_expires = time.monotonic() + CACHE_TTL_SECONDS
    return config


def save_config(
    db: Session,
    *,
    provider: str,
    base_url: str,
    model: str,
    api_key: str | None,
    vision_model: str | None = None,
    vision_base_url: str | None = None,
    vision_api_key: str | None = None,
    user_id: int = 0,
) -> LLMConfig:
    """保存全局配置并立即生效。

    api_key / vision_api_key 传 None 表示「保持不变」，传空字符串表示「清除」。
    """
    row = db.get(LLMConfig, _CONFIG_ID)
    if row is None:
        row = LLMConfig(id=_CONFIG_ID)
        db.add(row)

    row.provider = (provider or "openai").strip()
    row.base_url = (base_url or "").strip().rstrip("/")
    row.model = (model or "").strip()

    if api_key is not None:
        value = api_key.strip()
        row.api_key_cipher = encrypt_secret(value) if value else ""

    if vision_model is not None:
        row.vision_model = vision_model.strip()
    if vision_base_url is not None:
        row.vision_base_url = vision_base_url.strip().rstrip("/")
    if vision_api_key is not None:
        value = vision_api_key.strip()
        row.vision_api_key_cipher = encrypt_secret(value) if value else ""

    row.updated_by = user_id
    row.updated_at = datetime.utcnow()
    # 配置变更后旧的探测结果不再可信
    row.last_status = "unknown"
    row.last_error = ""
    row.last_checked_at = None

    db.commit()
    db.refresh(row)

    invalidate()
    # 探测缓存键包含配置指纹，这里一并清理，避免刚保存就看到旧状态
    from app.services.llm.probe import invalidate_probe_cache

    invalidate_probe_cache()
    return row


def status_meta(
    db: Session | None, config: RuntimeLLMConfig
) -> tuple[str, str, datetime | None]:
    """返回 (状态, 错误信息, 最近探测时间)；环境变量配置走内存。"""
    if config.source == "db" and db is not None:
        row = db.get(LLMConfig, _CONFIG_ID)
        if row is not None:
            return row.last_status or "unknown", row.last_error or "", row.last_checked_at
    if not config.configured:
        return "unconfigured", "", None
    return (
        str(_env_status["status"]),
        str(_env_status["error"]),
        _env_status["checked_at"],  # type: ignore[return-value]
    )


def record_status(
    config: RuntimeLLMConfig, status: str, error: str, checked_at: datetime | None = None
) -> None:
    """回写探测结果：数据库配置写表，环境变量配置写内存。"""
    checked = checked_at or datetime.utcnow()
    if config.source == "db":
        from app.db import SessionLocal

        with SessionLocal() as db:
            row = db.get(LLMConfig, _CONFIG_ID)
            if row is not None:
                row.last_status = status
                row.last_error = error
                row.last_checked_at = checked
                db.commit()
        return

    _env_status["status"] = status
    _env_status["error"] = error
    _env_status["checked_at"] = checked


def normalize_base_url(raw: str) -> str:
    """校验并规范化模型接口地址，默认只允许公网 HTTPS，防止 SSRF。"""
    value = (raw or "").strip().rstrip("/")
    if not value:
        raise ValueError("接口地址不能为空")

    parsed = urlparse(value)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("接口地址必须以 http:// 或 https:// 开头")
    if parsed.username or parsed.password:
        raise ValueError("接口地址不能包含用户名或密码")

    host = (parsed.hostname or "").lower()
    if not host:
        raise ValueError("接口地址缺少主机名")

    if _is_allowlisted(value):
        return value

    if parsed.scheme != "https":
        raise ValueError("出于安全考虑，自定义接口地址必须使用 HTTPS")
    if _is_blocked_host(host):
        raise ValueError("接口地址不能指向本机或内网地址")
    return value


def _load_uncached(db: Session | None = None) -> RuntimeLLMConfig:
    if db is None:
        from app.db import SessionLocal

        with SessionLocal() as session:
            return _from_db_or_env(session)
    return _from_db_or_env(db)


def _from_db_or_env(db: Session) -> RuntimeLLMConfig:
    row = db.get(LLMConfig, _CONFIG_ID)
    if row is None or not (row.api_key_cipher and row.base_url and row.model):
        return _env_config()

    try:
        api_key = decrypt_secret(row.api_key_cipher)
    except RuntimeError as exc:
        # 例如更换了 LLM_CONFIG_SECRET：不能让整个服务不可用，退回环境变量
        logger.warning("数据库模型配置解密失败，回退环境变量配置：%s", exc)
        return _env_config()

    vision_key = ""
    if row.vision_api_key_cipher:
        try:
            vision_key = decrypt_secret(row.vision_api_key_cipher)
        except RuntimeError:
            vision_key = ""

    return RuntimeLLMConfig(
        provider=row.provider or "openai",
        base_url=row.base_url.rstrip("/"),
        model=row.model,
        api_key=api_key,
        vision_model=row.vision_model or "",
        vision_base_url=(row.vision_base_url or "").rstrip("/"),
        vision_api_key=vision_key,
        source="db",
    )


def _env_config() -> RuntimeLLMConfig:
    return RuntimeLLMConfig(
        provider=(settings.llm_provider or "openai").strip().lower(),
        base_url=settings.deepseek_base_url.strip().rstrip("/"),
        model=settings.deepseek_model.strip(),
        api_key=settings.deepseek_api_key.strip(),
        vision_model=settings.llm_vision_model.strip(),
        vision_base_url=settings.llm_vision_base_url.strip().rstrip("/"),
        vision_api_key=settings.llm_vision_api_key.strip(),
        source="env",
    )


def _is_allowlisted(value: str) -> bool:
    """白名单按前缀匹配，便于放行内网自建服务（如 Ollama / vLLM）。"""
    lowered = value.lower()
    for item in settings.llm_allowed_base_urls:
        allowed = (item or "").strip().lower().rstrip("/")
        if allowed and lowered.startswith(allowed):
            return True
    return False


def _is_blocked_host(host: str) -> bool:
    if host in ("localhost", "127.0.0.1", "0.0.0.0", "::1"):
        return True
    if host.endswith(_BLOCKED_HOST_SUFFIXES):
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return ip.is_private or ip.is_loopback or ip.is_reserved or ip.is_link_local
