"""LLM 适配层抽象：统一 chat 接口，支持 Function Calling 与 JSON Mode。"""

from abc import ABC, abstractmethod
from typing import Any


class LLMClient(ABC):
    """所有 LLM 提供方实现该接口，业务代码只依赖此抽象。"""

    @abstractmethod
    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict] | None = None,
        json_mode: bool = False,
    ) -> dict[str, Any]:
        """返回 OpenAI 兼容结构：{"content": str, "tool_calls": [...], "raw": {...}}

        messages 采用 OpenAI 结构：content 既可是字符串，也可是多模态分段数组
        （如 [{"type": "text", ...}, {"type": "image_url", ...}]）。
        """
        raise NotImplementedError


def get_llm_client():
    from app.core.config import settings
    from app.services.llm.deepseek import DeepSeekClient

    if settings.llm_provider == "deepseek":
        return DeepSeekClient()
    raise ValueError(f"未知 LLM provider: {settings.llm_provider}")


def get_vision_client():
    """返回多模态客户端；未配置视觉模型时返回 None（调用方回退本地 OCR）。"""
    from app.core.config import settings
    from app.services.llm.deepseek import DeepSeekClient

    if settings.llm_provider != "deepseek" or not settings.llm_vision_model:
        return None
    return DeepSeekClient(
        api_key=settings.llm_vision_api_key or settings.deepseek_api_key,
        base_url=settings.llm_vision_base_url or settings.deepseek_base_url,
        model=settings.llm_vision_model,
    )
