"""全局大模型配置接口：管理员可写，所有登录用户可读并刷新连通状态。"""

import logging
import time

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_role
from app.core.crypto import mask_secret
from app.db import get_db
from app.models.llm_config import LLMConfig
from app.models.user import User
from app.schemas.settings import LLMConfigOut, LLMConfigUpdate, LLMProbeOut
from app.services.llm import config_store
from app.services.llm import probe as probe_service

logger = logging.getLogger("cbec")

router = APIRouter(prefix="/api/settings", tags=["settings"])

_CONFIG_ID = 1
_TEST_COOLDOWN_SECONDS = 3.0
_last_test_at = 0.0


@router.get("/llm", response_model=LLMConfigOut)
def read_llm_config(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> LLMConfigOut:
    """返回当前生效配置与最近一次探测状态（不含明文 Key）。"""
    return _build_out(db, user)


@router.put("/llm", response_model=LLMConfigOut)
def update_llm_config(
    req: LLMConfigUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
) -> LLMConfigOut:
    """保存全局配置并立即生效（无需重启）。"""
    model = req.model.strip()
    if not model:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "模型名称不能为空")
    if len(model) > 128:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "模型名称过长")

    try:
        base_url = config_store.normalize_base_url(req.base_url)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    vision_model = (req.vision_model or "").strip()
    vision_base_url = (req.vision_base_url or "").strip()
    if vision_model and vision_base_url:
        try:
            vision_base_url = config_store.normalize_base_url(vision_base_url)
        except ValueError as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"视觉模型：{exc}") from exc
    elif vision_model and not vision_base_url:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "填写视觉模型时需要同时提供接口地址")
    else:
        vision_base_url = ""

    current = config_store.load_config(db)
    api_key = req.api_key if req.api_key is not None else None
    vision_api_key = req.vision_api_key if req.vision_api_key is not None else None
    if current.source == "env":
        # 首次在页面上保存：把环境变量里的 Key 一并落库，避免保存后反而变成未配置
        if api_key is None and current.api_key:
            api_key = current.api_key
        if vision_api_key is None and current.vision_api_key:
            vision_api_key = current.vision_api_key

    try:
        config_store.save_config(
            db,
            provider=req.provider,
            base_url=base_url,
            model=model,
            api_key=api_key,
            vision_model=vision_model,
            vision_base_url=vision_base_url,
            vision_api_key=vision_api_key,
            user_id=user.id,
        )
    except RuntimeError as exc:
        # 服务端缺少 LLM_CONFIG_SECRET 时无法加密落库
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    logger.info(
        "模型配置已更新：admin_id=%s provider=%s model=%s base_url=%s api_key=%s",
        user.id,
        req.provider,
        model,
        base_url,
        mask_secret(api_key) if api_key else "未配置",
    )
    db.expire_all()
    return _build_out(db, user)


@router.post("/llm/test", response_model=LLMProbeOut)
def test_llm_config(
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
) -> LLMProbeOut:
    """用当前保存的配置实测一次连通性（保存前也可先测环境变量兜底配置）。"""
    global _last_test_at
    now = time.monotonic()
    if now - _last_test_at < _TEST_COOLDOWN_SECONDS:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "操作过于频繁，请稍后再试")
    _last_test_at = now

    config = config_store.load_config(db)
    result = probe_service.probe(config, force=True)
    config_store.record_status(config, result.status, result.message, result.checked_at)
    db.expire_all()
    return LLMProbeOut(
        status=result.status,
        message=result.message,
        latency_ms=result.latency_ms,
        checked_at=result.checked_at,
        config=_build_out(db, user),
    )


@router.post("/llm/refresh", response_model=LLMProbeOut)
def refresh_llm_status(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> LLMProbeOut:
    """任意登录用户可触发的后台探测，用于刷新对话页右上角的状态灯。

    探测结果按配置指纹缓存 60 秒，频繁轮询不会打满模型服务。
    """
    config = config_store.load_config(db)
    result = probe_service.probe(config)
    config_store.record_status(config, result.status, result.message, result.checked_at)
    db.expire_all()
    return LLMProbeOut(
        status=result.status,
        message=result.message,
        latency_ms=result.latency_ms,
        checked_at=result.checked_at,
        config=_build_out(db, user),
    )


def _build_out(db: Session, user: User) -> LLMConfigOut:
    config = config_store.load_config(db)
    status_value, message, checked_at = config_store.status_meta(db, config)
    row = db.get(LLMConfig, _CONFIG_ID)
    return LLMConfigOut(
        provider=config.provider,
        base_url=config.base_url,
        model=config.model,
        api_key_masked=mask_secret(config.api_key) if config.api_key else "",
        api_key_configured=bool(config.api_key),
        vision_model=config.vision_model,
        vision_base_url=config.vision_base_url,
        vision_api_key_masked=(
            mask_secret(config.vision_api_key) if config.vision_api_key else ""
        ),
        vision_api_key_configured=bool(config.vision_api_key),
        source=config.source,
        status=status_value,
        status_message=message,
        checked_at=checked_at,
        updated_at=row.updated_at if row else None,
        updated_by=row.updated_by if row else 0,
        can_edit=user.role == "admin",
    )
