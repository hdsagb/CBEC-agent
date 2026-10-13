"""DeepSeek 适配：OpenAI 兼容 /chat/completions，httpx 直连，无 SDK 依赖。"""

from typing import Any

import httpx

from app.core.config import settings
from app.services.llm.base import LLMClient


class DeepSeekClient(LLMClient):
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
    ) -> None:
        # 允许按调用方传入不同配置（如多模态视觉模型走独立 endpoint）
        self.api_key = api_key if api_key is not None else settings.deepseek_api_key
        self.base_url = (base_url or settings.deepseek_base_url).rstrip("/")
        self.model = model or settings.deepseek_model

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict] | None = None,
        json_mode: bool = False,
    ) -> dict[str, Any]:
        if not self.api_key:
            raise RuntimeError("未配置 DEEPSEEK_API_KEY")

        body: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
        }
        if tools:
            body["tools"] = [{"type": "function", "function": t} for t in tools]
        if json_mode:
            body["response_format"] = {"type": "json_object"}

        resp = httpx.post(
            f"{settings.deepseek_base_url}/chat/completions",
            headers={"Authorization": f"Bearer {settings.deepseek_api_key}"},
            json=body,
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        choice = data["choices"][0]["message"]
        return {
            "content": choice.get("content") or "",
            "tool_calls": choice.get("tool_calls") or [],
            "raw": data,
        }
