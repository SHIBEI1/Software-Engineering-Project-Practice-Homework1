"""Minimal OpenAI-compatible LLM client with bounded retries."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any
from urllib import error, request

from .models import ChatMessage


class LLMError(RuntimeError):
    """Raised after a remote LLM request cannot be completed."""


@dataclass(frozen=True)
class LLMConfig:
    api_key: str | None
    base_url: str
    model: str
    max_retries: int = 2

    @classmethod
    def from_env(cls) -> "LLMConfig":
        """Load generic LLM_* variables, retaining OPENAI_* aliases for compatibility."""
        base_url = (
            os.getenv("LLM_BASE_URL")
            or os.getenv("OPENAI_BASE_URL")
            or "https://api.openai.com/v1"
        ).rstrip("/")
        return cls(
            api_key=os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY"),
            base_url=base_url,
            model=os.getenv("LLM_MODEL") or os.getenv("OPENAI_MODEL") or "gpt-4o-mini",
        )


class OpenAICompatibleClient:
    """A dependency-free client for the Chat Completions compatible endpoint."""

    def __init__(self, config: LLMConfig | None = None) -> None:
        self.config = config or LLMConfig.from_env()

    @property
    def available(self) -> bool:
        return bool(self.config.api_key)

    def chat(
        self,
        system_prompt: str,
        history: list[ChatMessage],
        response_format: dict[str, str] | None = None,
    ) -> str:
        if not self.available:
            raise LLMError("未配置 LLM_API_KEY（也兼容 OPENAI_API_KEY）")
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend({"role": item.role, "content": item.content} for item in history)
        payload: dict[str, Any] = {
            "model": self.config.model,
            "messages": messages,
            "temperature": 0.2,
        }
        if response_format is not None:
            payload["response_format"] = response_format
        body = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.config.api_key}",
        }
        last_error = "未知错误"
        for attempt in range(self.config.max_retries + 1):
            try:
                req = request.Request(
                    f"{self.config.base_url}/chat/completions",
                    data=body,
                    headers=headers,
                    method="POST",
                )
                with request.urlopen(req, timeout=30) as response:
                    data = json.loads(response.read().decode("utf-8"))
                return data["choices"][0]["message"]["content"].strip()
            except (error.URLError, error.HTTPError, KeyError, IndexError, json.JSONDecodeError) as exc:
                last_error = str(exc)
                if attempt < self.config.max_retries:
                    time.sleep(0.5 * (2**attempt))
        raise LLMError(f"LLM 调用失败，已重试 {self.config.max_retries} 次：{last_error}")
