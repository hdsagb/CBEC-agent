"""LLM 适配层抽象：统一 chat 接口，支持 Function Calling 与 JSON Mode。"""

from abc import ABC, abstractmethod
from typing import Any


class LLMClient(ABC):
    """所有 LLM 提供方实现该接口，业务代码只依赖此抽象。"""

    @abstractmethod
    def chat(
        self,
        messages: list[dict[str, str]],
        tools: list[dict] | None = None,
        json_mode: bool = False,
    ) -> dict[str, Any]:
        """返回 OpenAI 兼容结构：{"content": str, "tool_calls": [...], "raw": {...}}"""
        raise NotImplementedError


def get_llm_client():
    from app.core.config import settings
    from app.services.llm.deepseek import DeepSeekClient

    if settings.llm_provider == "deepseek":
        return DeepSeekClient()
    raise ValueError(f"未知 LLM provider: {settings.llm_provider}")
