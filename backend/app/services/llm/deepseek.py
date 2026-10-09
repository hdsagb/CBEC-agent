"""DeepSeek 适配：OpenAI 兼容 /chat/completions，httpx 直连，无 SDK 依赖。"""

from typing import Any

import httpx

from app.core.config import settings
from app.services.llm.base import LLMClient


class DeepSeekClient(LLMClient):
    def chat(
        self,
        messages: list[dict[str, str]],
        tools: list[dict] | None = None,
        json_mode: bool = False,
    ) -> dict[str, Any]:
        if not settings.deepseek_api_key:
            raise RuntimeError("未配置 DEEPSEEK_API_KEY")

        body: dict[str, Any] = {
            "model": settings.deepseek_model,
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
