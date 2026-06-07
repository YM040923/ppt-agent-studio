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
        topic = _topic_from_prompt(prompt)
        slide_count = _slide_count_from_prompt(prompt)
        metadata = _metadata_from_prompt(prompt)
        return {
            "deck_title": topic,
            "metadata": metadata,
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
        if not isinstance(outline.get("metadata"), dict):
            outline["metadata"] = _metadata_from_prompt(prompt)
        if not isinstance(outline.get("theme"), dict):
            outline["theme"] = _theme_from_prompt(prompt)
        if not _has_usable_slides(outline):
            title = str(outline.get("deck_title") or outline.get("title") or _topic_from_prompt(prompt))
            outline["deck_title"] = title or "Untitled Deck"
            outline["slides"] = _fallback_slides(outline["deck_title"], _slide_count_from_prompt(prompt))
        else:
            outline["slides"] = _normalized_llm_slides(outline, prompt)
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
    return len(_usable_slides(outline)) > 0


def _usable_slides(outline: dict[str, object]) -> list[dict[str, object]]:
    slides = outline.get("slides")
    if not isinstance(slides, list):
        return []
    return [slide for slide in slides if isinstance(slide, dict)]


def _normalized_llm_slides(outline: dict[str, object], prompt: str) -> list[dict[str, object]]:
    slides = _usable_slides(outline)
    requested_count = _requested_slide_count_from_prompt(prompt)
    target_count = requested_count if requested_count is not None else len(slides)
    target_count = max(1, min(target_count, 30))
    if len(slides) >= target_count:
        return slides[:target_count]

    title = str(outline.get("deck_title") or outline.get("title") or prompt.removesuffix(".").strip())
    fallback_slides = _fallback_slides(title or "Untitled Deck", target_count)
    return [*slides, *fallback_slides[len(slides) : target_count]]


def _topic_from_prompt(prompt: str) -> str:
    cleaned = prompt.removesuffix(".").strip()
    chinese_topic = _first_prompt_match(
        prompt,
        (
            r"(?:\u5173\u4e8e|\u95dc\u65bc)\s*(?P<value>.+?)\s*(?:\u7684)?\s*(?:\d{1,3}|[\u4e00\u4e8c\u4e09\u56db\u4e94\u516d\u4e03\u516b\u4e5d\u5341\u4e24\u5169]{1,3})?\s*(?:\u9875|\u9801|\u5f20|\u5f35|PPT|ppt)",
        ),
    )
    if chinese_topic:
        return chinese_topic

    english_topic = _english_topic_from_prompt(cleaned)
    return english_topic or cleaned or "Untitled Deck"


def _english_topic_from_prompt(prompt: str) -> str:
    value = re.sub(
        r"^(?:make|create|draft|build|generate)\s+(?:me\s+)?(?:a|an|the)?\s*",
        "",
        prompt,
        flags=re.IGNORECASE,
    )
    value = re.sub(r"\b\d{1,3}\s*(?:slides?|pages?)\b", "", value, count=1, flags=re.IGNORECASE)
    value = re.sub(r"\b(?:deck|presentation|ppt)\b.*$", "", value, flags=re.IGNORECASE)
    value = re.sub(r"\s+", " ", value).strip(" -:,.")
    if not value:
        return ""
    return _business_title(value)


def _business_title(value: str) -> str:
    acronyms = {"ai", "api", "cfo", "cio", "ceo", "cto", "it", "ppt", "roi"}
    words = []
    for word in value.split():
        normalized = word.casefold().strip(".,:;")
        if normalized in acronyms:
            words.append(word.upper())
        else:
            words.append(f"{word[:1].upper()}{word[1:].lower()}")
    return " ".join(words)


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


def _metadata_from_prompt(prompt: str) -> dict[str, str]:
    metadata: dict[str, str] = {}
    audience = _first_prompt_match(
        prompt,
        (
            r"\btarget\s+audience\s*(?:is|:|=)?\s*(?P<value>[^,.;]+)",
            r"\baudience\s*(?:is|:|=)\s*(?P<value>[^,.;]+)",
            r"\bfor\s+(?:the\s+)?(?P<value>[^,.;]+)",
            r"(?:\u76ee\u6807\u53d7\u4f17|\u53d7\u4f17)\s*(?:\u662f|:|：)?\s*(?P<value>[^,，。；;]+)",
        ),
    )
    style = _first_prompt_match(
        prompt,
        (
            r"\bstyle\s*(?:is|:|=)?\s*(?P<value>[^,.;]+)",
            r"\btone\s*(?:is|:|=)\s*(?P<value>[^,.;]+)",
            r"(?P<value>mckinsey|bcg|bain|consulting)\s+style\b",
            r"(?:\u98ce\u683c|\u98a8\u683c)\s*(?:\u662f|:|：)?\s*(?P<value>[^,，。；;]+)",
        ),
    )
    if audience:
        metadata["audience"] = audience
    if style:
        metadata["style"] = style
    return metadata


def _first_prompt_match(prompt: str, patterns: tuple[str, ...]) -> str:
    for pattern in patterns:
        match = re.search(pattern, prompt, flags=re.IGNORECASE)
        if match:
            value = match.group("value").strip(" \t\r\n'\"")
            if value:
                return value
    return ""


def _slide_count_from_prompt(prompt: str) -> int:
    return _requested_slide_count_from_prompt(prompt) or 3


def _requested_slide_count_from_prompt(prompt: str) -> int | None:
    match = re.search(r"\b(\d{1,3})\s*(?:slides?|pages?)\b|(\d{1,3})\s*[页張张]", prompt, flags=re.IGNORECASE)
    if match:
        value = int(match.group(1) or match.group(2))
        return max(1, min(value, 30))
    chinese_match = re.search(r"([一二两三四五六七八九十]{1,3})\s*[页張张]", prompt)
    if not chinese_match:
        return None
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
            "speaker_notes": "Open with the decision this presentation is meant to support and the audience outcome you want.",
        }
    ]
    if slide_count == 1:
        return slides

    slides.append(
        {
            "title": "Executive summary",
            "prototype_hint": "content",
            "speaker_notes": "Start with the recommendation, quantify why it matters, and make the next decision explicit.",
            "points": [
                {
                    "label": "Recommendation",
                    "body": "State the preferred path and the decision needed from the audience.",
                },
                {
                    "label": "Impact",
                    "body": "Summarize the expected business value, risk reduction, or strategic advantage.",
                },
                {
                    "label": "Next step",
                    "body": "Name the immediate action, owner, and timing required to move forward.",
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
                "speaker_notes": "Land one message, then use the evidence point to support it without over-explaining the slide.",
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
            "speaker_notes": "Close by making the next steps concrete, sequenced, and measurable.",
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
        "speaker_notes": "State the recommendation first, then describe why this path is better than the alternatives.",
        "bullets": [
            "Define the target operating model.",
            "Prioritize high-leverage use cases.",
            "Sequence rollout with measurable checkpoints.",
        ],
    }
