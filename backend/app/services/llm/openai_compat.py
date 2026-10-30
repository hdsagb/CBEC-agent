"""OpenAI 兼容接口客户端：一套实现适配所有兼容 /chat/completions 的模型服务。

DeepSeek、Moonshot、智谱、通义、OpenAI 官方以及本地 vLLM / Ollama 的兼容模式
均可使用，区别只在 base_url、model 与 API Key。
"""

import logging
from typing import Any

import httpx

from app.services.llm.base import LLMClient

logger = logging.getLogger("cbec")


class OpenAICompatClient(LLMClient):
    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        timeout: float = 60.0,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict] | None = None,
        json_mode: bool = False,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"model": self.model, "messages": messages}
        if tools:
            payload["tools"] = [
                {"type": "function", "function": tool} for tool in tools
            ]
            payload["tool_choice"] = "auto"
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        resp = httpx.post(
            f"{self.base_url}/chat/completions",
            headers=headers,
            json=payload,
            timeout=self.timeout,
            follow_redirects=False,
        )
        if resp.status_code >= 400:
            raise RuntimeError(
                f"模型服务返回 HTTP {resp.status_code}: {resp.text[:200]}"
            )

        data = resp.json()
        choice = (data.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        return {
            "content": message.get("content") or "",
            "tool_calls": message.get("tool_calls") or [],
            "raw": data,
        }
