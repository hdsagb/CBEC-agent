"""LLM 适配层抽象：统一 chat 接口，支持 Function Calling 与 JSON Mode。

具体提供方一律走 OpenAI 兼容协议，因此这里只有一个客户端实现；
运行期到底连哪家模型，由 config_store 从数据库 / 环境变量解析。
"""

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


NOT_CONFIGURED_HINT = "尚未配置可用的大模型，请点击对话页右上角的模型标识完成配置"


def get_llm_client() -> LLMClient:
    """按当前生效配置构造客户端；未配置时抛错，由上层降级为提示文案。"""
    from app.services.llm.config_store import load_config
    from app.services.llm.openai_compat import OpenAICompatClient

    config = load_config()
    if not config.configured:
        raise RuntimeError(NOT_CONFIGURED_HINT)
    return OpenAICompatClient(
        api_key=config.api_key,
        base_url=config.base_url,
        model=config.model,
    )


def get_vision_client() -> LLMClient | None:
    """返回多模态客户端；未配置视觉模型时返回 None（调用方回退本地 OCR）。"""
    from app.services.llm.config_store import load_config
    from app.services.llm.openai_compat import OpenAICompatClient

    config = load_config()
    if not config.vision_enabled:
        return None
    return OpenAICompatClient(
        api_key=config.vision_api_key or config.api_key,
        base_url=config.vision_base_url or config.base_url,
        model=config.vision_model,
    )
