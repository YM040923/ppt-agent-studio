from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import httpx

from ppt_agent_studio.llm.config import OpenAICompatibleConfig


ChatMessage = dict[str, str]


class OpenAICompatibleChatClient:
    def __init__(
        self,
        config: OpenAICompatibleConfig | None = None,
        http_client: httpx.AsyncClient | None = None,
    ):
        self.config = config or OpenAICompatibleConfig.from_env()
        self._http_client = http_client

    async def complete(self, messages: Sequence[ChatMessage], temperature: float = 0.2) -> str:
        if self.config.requires_api_key and not self.config.has_api_key:
            raise ValueError("OPENAI_API_KEY is required")

        payload = {
            "model": self.config.model,
            "messages": list(messages),
            "temperature": temperature,
        }
        client = self._http_client or httpx.AsyncClient()
        close_client = self._http_client is None
        headers = dict(self.config.extra_headers)
        if self.config.has_api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        try:
            response = await client.post(
                f"{self.config.base_url}/chat/completions",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()
            return _extract_choice_text(data)
        finally:
            if close_client:
                await client.aclose()


def _extract_choice_text(data: Any) -> str:
    if not isinstance(data, dict):
        raise ValueError("OpenAI-compatible response did not include text content")

    choices = data.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise ValueError("OpenAI-compatible response did not include text content")

    choice = choices[0]
    message = choice.get("message")
    if isinstance(message, dict) and "content" in message:
        return _content_to_text(message["content"])

    text = choice.get("text")
    if isinstance(text, str):
        return text

    raise ValueError("OpenAI-compatible response did not include text content")


def _content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        raise ValueError("OpenAI-compatible response did not include text content")

    parts: list[str] = []
    for block in content:
        if isinstance(block, str) and block.strip():
            parts.append(block.strip())
        elif isinstance(block, dict):
            text = _content_block_text(block)
            if text:
                parts.append(text)
    if not parts:
        raise ValueError("OpenAI-compatible response did not include text content")
    return "\n".join(parts)


def _content_block_text(block: dict[str, Any]) -> str:
    text = block.get("text")
    if isinstance(text, str) and text.strip():
        return text.strip()
    if isinstance(text, dict):
        value = text.get("value")
        if isinstance(value, str) and value.strip():
            return value.strip()
    content = block.get("content")
    if isinstance(content, str) and content.strip():
        return content.strip()
    return ""
