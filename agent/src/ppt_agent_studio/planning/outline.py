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
        slide_count = _slide_count_from_prompt(prompt)
        return {
            "deck_title": topic,
            "theme": _theme_from_prompt(prompt),
            "slides": _fallback_slides(topic, slide_count),
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
        if not isinstance(outline.get("theme"), dict):
            outline["theme"] = _theme_from_prompt(prompt)
        if not _has_usable_slides(outline):
            title = str(outline.get("deck_title") or outline.get("title") or prompt.removesuffix(".").strip())
            outline["deck_title"] = title or "Untitled Deck"
            outline["slides"] = _fallback_slides(outline["deck_title"], _slide_count_from_prompt(prompt))
        return outline


def _extract_json(text: str) -> str:
    match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1)
    stripped = text.strip()
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start != -1 and end != -1 and end > start:
        return stripped[start : end + 1]
    return stripped


def _has_usable_slides(outline: dict[str, object]) -> bool:
    slides = outline.get("slides")
    return isinstance(slides, list) and any(isinstance(slide, dict) for slide in slides)


def _theme_from_prompt(prompt: str) -> dict[str, str]:
    normalized = prompt.casefold()
    executive_markers = ("麦肯锡", "高层", "高管", "管理者", "咨询", "mckinsey", "executive", "board", "consulting")
    if any(marker in normalized for marker in executive_markers):
        return {
            "name": "executive-consulting",
            "background": "#EEF2F7",
            "slide_background": "#FFFFFF",
            "text": "#111827",
            "accent": "#2563EB",
        }
    return {
        "name": "clean-business",
        "background": "#F3F4F6",
        "slide_background": "#FFFFFF",
        "text": "#111827",
        "accent": "#0F766E",
    }


def _slide_count_from_prompt(prompt: str) -> int:
    match = re.search(r"\b(\d{1,3})\s*(?:slides?|pages?)\b|(\d{1,3})\s*[页張张]", prompt, flags=re.IGNORECASE)
    if match:
        value = int(match.group(1) or match.group(2))
        return max(1, min(value, 30))
    chinese_match = re.search(r"([一二两三四五六七八九十]{1,3})\s*[页張张]", prompt)
    if not chinese_match:
        return 3
    value = _chinese_number_to_int(chinese_match.group(1))
    return max(1, min(value, 30))


def _chinese_number_to_int(value: str) -> int:
    digits = {
        "一": 1,
        "二": 2,
        "两": 2,
        "三": 3,
        "四": 4,
        "五": 5,
        "六": 6,
        "七": 7,
        "八": 8,
        "九": 9,
    }
    if value == "十":
        return 10
    if "十" in value:
        tens_text, ones_text = value.split("十", 1)
        tens = digits.get(tens_text, 1) if tens_text else 1
        ones = digits.get(ones_text, 0) if ones_text else 0
        return tens * 10 + ones
    return digits.get(value, 3)


def _fallback_slides(topic: str, slide_count: int) -> list[dict[str, object]]:
    slides: list[dict[str, object]] = [
        {
            "title": topic,
            "subtitle": "Executive presentation draft",
            "prototype_hint": "cover",
        }
    ]
    if slide_count == 1:
        return slides

    slides.append(
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
        }
    )
    if slide_count == 2:
        return slides

    if slide_count == 3:
        slides.append(_recommended_path_slide())
        return slides

    middle_titles = [
        "Audience decision",
        "Current-state diagnosis",
        "Opportunity landscape",
        "Strategic options",
        "Recommended path",
        "Business case",
        "Operating model",
        "Capability roadmap",
        "Risk controls",
        "Governance model",
        "Adoption plan",
        "Metrics and milestones",
    ]
    middle_count = slide_count - 3
    for index in range(middle_count):
        base_title = middle_titles[index % len(middle_titles)]
        title = base_title if index < len(middle_titles) else f"{base_title} {index + 1}"
        slides.append(
            {
                "title": title,
                "prototype_hint": "content",
                "points": [
                    {"label": "Key message", "body": "State the single takeaway this slide should land."},
                    {"label": "Evidence", "body": "Add the proof point, metric, or example that supports the message."},
                ],
            }
        )

    slides.append(
        {
            "title": "Implementation roadmap",
            "prototype_hint": "content",
            "bullets": [
                "Define the target operating model.",
                "Prioritize high-leverage use cases.",
                "Sequence rollout with measurable checkpoints.",
            ],
        }
    )
    return slides


def _recommended_path_slide() -> dict[str, object]:
    return {
        "title": "Recommended path",
        "prototype_hint": "content",
        "bullets": [
            "Define the target operating model.",
            "Prioritize high-leverage use cases.",
            "Sequence rollout with measurable checkpoints.",
        ],
    }
