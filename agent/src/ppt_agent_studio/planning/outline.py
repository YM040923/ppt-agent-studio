from __future__ import annotations

import json
import re
from typing import Protocol

from ppt_agent_studio.llm.client import ChatMessage, OpenAICompatibleChatClient
from ppt_agent_studio.prompts import PPT_AGENT_SYSTEM_PROMPT


class OutlinePlanner(Protocol):
    async def create_outline(self, prompt: str) -> dict[str, object]:
        ...


class FallbackOutlinePlanner:
    async def create_outline(self, prompt: str) -> dict[str, object]:
        topic = prompt.removesuffix(".").strip()
        return {
            "deck_title": topic,
            "slides": [
                {
                    "title": topic,
                    "subtitle": "Executive presentation draft",
                    "prototype_hint": "cover",
                },
                {
                    "title": "Strategic context",
                    "prototype_hint": "content",
                    "points": [
                        {
                            "label": "Objective",
                            "body": "Clarify the decision, audience, and expected business outcome.",
                        },
                        {
                            "label": "Signal",
                            "body": "Frame the core trend and why it matters now.",
                        },
                    ],
                },
                {
                    "title": "Recommended path",
                    "prototype_hint": "content",
                    "bullets": [
                        "Define the target operating model.",
                        "Prioritize high-leverage use cases.",
                        "Sequence rollout with measurable checkpoints.",
                    ],
                },
            ],
        }


class LLMOutlinePlanner:
    def __init__(self, chat_client: OpenAICompatibleChatClient | None = None):
        self._chat_client = chat_client or OpenAICompatibleChatClient()

    async def create_outline(self, prompt: str) -> dict[str, object]:
        messages: list[ChatMessage] = [
            {"role": "system", "content": PPT_AGENT_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]
        response = await self._chat_client.complete(messages=messages, temperature=0.2)
        outline = json.loads(_extract_json(response))
        if not isinstance(outline, dict):
            raise ValueError("outline response must be a JSON object")
        return outline


def _extract_json(text: str) -> str:
    match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1)
    return text.strip()
