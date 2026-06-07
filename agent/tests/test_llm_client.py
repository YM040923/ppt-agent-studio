import asyncio
import json

import httpx
import pytest

from ppt_agent_studio.llm.client import OpenAICompatibleChatClient
from ppt_agent_studio.llm.config import OpenAICompatibleConfig


def test_chat_client_posts_openai_compatible_request_and_parses_text():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["headers"] = dict(request.headers)
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": "A concise executive story."
                        }
                    }
                ]
            },
        )

    transport = httpx.MockTransport(handler)
    config = OpenAICompatibleConfig(
        base_url="https://provider.example/v1",
        api_key="secret-value",
        model="gpt-compatible-model",
        extra_headers={"X-Provider": "tenant-001"},
    )

    async def run():
        async with httpx.AsyncClient(transport=transport) as http_client:
            client = OpenAICompatibleChatClient(config=config, http_client=http_client)
            return await client.complete(
                messages=[
                    {"role": "system", "content": "You are a PPT strategist."},
                    {"role": "user", "content": "Draft the story."},
                ],
                temperature=0.2,
            )

    text = asyncio.run(run())

    assert text == "A concise executive story."
    assert captured["url"] == "https://provider.example/v1/chat/completions"
    assert captured["headers"]["authorization"] == "Bearer secret-value"
    assert captured["headers"]["x-provider"] == "tenant-001"
    assert captured["body"] == {
        "model": "gpt-compatible-model",
        "messages": [
            {"role": "system", "content": "You are a PPT strategist."},
            {"role": "user", "content": "Draft the story."},
        ],
        "temperature": 0.2,
    }


def test_chat_client_requires_api_key():
    config = OpenAICompatibleConfig(
        base_url="https://provider.example/v1",
        api_key="",
        model="gpt-compatible-model",
    )

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(200))) as http_client:
            client = OpenAICompatibleChatClient(config=config, http_client=http_client)
            return await client.complete(messages=[{"role": "user", "content": "Draft"}])

    with pytest.raises(ValueError, match="OPENAI_API_KEY is required"):
        asyncio.run(run())
