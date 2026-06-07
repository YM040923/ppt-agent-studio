from __future__ import annotations

from collections.abc import Sequence

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
        if not self.config.has_api_key:
            raise ValueError("OPENAI_API_KEY is required")

        payload = {
            "model": self.config.model,
            "messages": list(messages),
            "temperature": temperature,
        }
        client = self._http_client or httpx.AsyncClient()
        close_client = self._http_client is None
        headers = {
            **self.config.extra_headers,
            "Authorization": f"Bearer {self.config.api_key}",
        }
        try:
            response = await client.post(
                f"{self.config.base_url}/chat/completions",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()
            return str(data["choices"][0]["message"]["content"])
        finally:
            if close_client:
                await client.aclose()
