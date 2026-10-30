"""API Key 落库加密：Fernet（AES-CBC + HMAC），密钥由 LLM_CONFIG_SECRET 派生。

数据库中只保存密文，接口只返回掩码字符串；服务端日志禁止输出明文或密文。
"""

import base64
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from app.core.config import settings

_SALT = b"cbec-agent/llm-config/v1"
# 密文前缀：便于未来轮换算法时识别历史版本
_PREFIX = "v1:"
_MIN_SECRET_LENGTH = 16


def _require_secret() -> str:
    secret = settings.llm_config_secret.strip()
    if len(secret) < _MIN_SECRET_LENGTH:
        raise RuntimeError(
            "服务端未配置 LLM_CONFIG_SECRET（至少 16 位），无法加解密大模型 API Key；"
            "请在部署环境补充该变量后重启"
        )
    return secret


@lru_cache(maxsize=4)
def _fernet(secret: str) -> Fernet:
    key = base64.urlsafe_b64encode(
        PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=_SALT, iterations=200_000).derive(
            secret.encode("utf-8")
        )
    )
    return Fernet(key)


def encrypt_secret(plaintext: str) -> str:
    """加密密钥；空值返回空串（表示未配置）。"""
    value = plaintext.strip()
    if not value:
        return ""
    return _PREFIX + _fernet(_require_secret()).encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_secret(token: str) -> str:
    """解密密钥；空值或格式不符返回空串，密钥轮换导致无法解密时抛 RuntimeError。"""
    if not token:
        return ""
    body = token[len(_PREFIX) :] if token.startswith(_PREFIX) else token
    try:
        return _fernet(_require_secret()).decrypt(body.encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        raise RuntimeError(
            "已保存的 API Key 无法解密：LLM_CONFIG_SECRET 可能已变更，请重新保存一次模型配置"
        ) from exc


def mask_secret(value: str) -> str:
    """掩码展示：sk-abc...wxyz -> sk-****wxyz；过短的密钥不暴露任何字符。"""
    if not value:
        return ""
    if len(value) <= 8:
        return "已配置"
    return f"{value[:3]}****{value[-4:]}"
