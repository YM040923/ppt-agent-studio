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
        return _fallback_outline(prompt)


class LLMOutlinePlanner:
    def __init__(self, chat_client: OpenAICompatibleChatClient | None = None):
        self._chat_client = chat_client or OpenAICompatibleChatClient()

    async def create_outline(self, prompt: str) -> dict[str, object]:
        messages: list[ChatMessage] = [
            {"role": "system", "content": PPT_AGENT_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]
        try:
            response = await self._chat_client.complete(messages=messages, temperature=0.2)
        except Exception:
            return _fallback_outline(prompt)
        try:
            outline = json.loads(_extract_json(response))
        except json.JSONDecodeError:
            return _fallback_outline(prompt)
        if not isinstance(outline, dict):
            return _fallback_outline(prompt)
        if not str(outline.get("deck_title") or "").strip():
            outline["deck_title"] = str(outline.get("title") or _topic_from_prompt(prompt))
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


def _fallback_outline(prompt: str) -> dict[str, object]:
    topic = _topic_from_prompt(prompt)
    slide_count = _slide_count_from_prompt(prompt)
    metadata = _metadata_from_prompt(prompt)
    return {
        "deck_title": topic,
        "metadata": metadata,
        "theme": _theme_from_prompt(prompt),
        "slides": _fallback_slides(topic, slide_count, chinese=_looks_chinese(prompt)),
    }


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
    fallback_slides = _fallback_slides(title or "Untitled Deck", target_count, chinese=_looks_chinese(prompt))
    return [*slides, *fallback_slides[len(slides) : target_count]]


def _looks_chinese(value: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", value))


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


def _fallback_slides(topic: str, slide_count: int, chinese: bool = False) -> list[dict[str, object]]:
    cover_subtitle = "\u6f14\u793a\u6587\u7a3f\u8349\u6848" if chinese else "Executive presentation draft"
    cover_notes = (
        "\u5148\u8bf4\u660e\u8fd9\u4efd\u6f14\u793a\u6587\u7a3f\u652f\u6301\u7684\u51b3\u7b56\uff0c\u4ee5\u53ca\u5e0c\u671b\u9ad8\u5c42\u542c\u4f17\u5f62\u6210\u7684\u5171\u8bc6\u3002"
        if chinese
        else "Open with the decision this presentation is meant to support and the audience outcome you want."
    )
    slides: list[dict[str, object]] = [
        {
            "title": topic,
            "subtitle": cover_subtitle,
            "prototype_hint": "cover",
            "speaker_notes": cover_notes,
        }
    ]
    if slide_count == 1:
        return slides

    summary_title = "\u6267\u884c\u6458\u8981" if chinese else "Executive summary"
    recommendation_label = "\u63a8\u8350\u65b9\u6848" if chinese else "Recommendation"
    impact_label = "\u5f71\u54cd" if chinese else "Impact"
    next_step_label = "\u4e0b\u4e00\u6b65" if chinese else "Next step"
    slides.append(
        {
            "title": summary_title,
            "prototype_hint": "content",
            "speaker_notes": (
                "\u5148\u7ed9\u51fa\u63a8\u8350\u65b9\u6848\uff0c\u518d\u91cf\u5316\u5f71\u54cd\uff0c\u6700\u540e\u660e\u786e\u9700\u8981\u9ad8\u5c42\u505a\u51fa\u7684\u4e0b\u4e00\u4e2a\u51b3\u5b9a\u3002"
                if chinese
                else "Start with the recommendation, quantify why it matters, and make the next decision explicit."
            ),
            "points": [
                {
                    "label": recommendation_label,
                    "body": (
                        "\u8bf4\u660e\u5efa\u8bae\u91c7\u53d6\u7684\u8def\u5f84\uff0c\u4ee5\u53ca\u9700\u8981\u542c\u4f17\u786e\u8ba4\u7684\u51b3\u7b56\u3002"
                        if chinese
                        else "State the preferred path and the decision needed from the audience."
                    ),
                },
                {
                    "label": impact_label,
                    "body": (
                        "\u603b\u7ed3\u9884\u671f\u7684\u4e1a\u52a1\u4ef7\u503c\u3001\u98ce\u9669\u964d\u4f4e\u6216\u6218\u7565\u4f18\u52bf\u3002"
                        if chinese
                        else "Summarize the expected business value, risk reduction, or strategic advantage."
                    ),
                },
                {
                    "label": next_step_label,
                    "body": (
                        "\u660e\u786e\u63a8\u8fdb\u6240\u9700\u7684\u5373\u523b\u884c\u52a8\u3001\u8d23\u4efb\u4eba\u548c\u65f6\u95f4\u8282\u70b9\u3002"
                        if chinese
                        else "Name the immediate action, owner, and timing required to move forward."
                    ),
                },
            ],
        }
    )
    if slide_count == 2:
        return slides

    if slide_count == 3:
        slides.append(_recommended_path_slide(chinese=chinese))
        return slides

    middle_titles = (
        [
            "\u542c\u4f17\u51b3\u7b56",
            "\u73b0\u72b6\u8bca\u65ad",
            "\u673a\u4f1a\u683c\u5c40",
            "\u6218\u7565\u9009\u9879",
            "\u63a8\u8350\u8def\u5f84",
            "\u5546\u4e1a\u6848\u4f8b",
            "\u8fd0\u8425\u6a21\u5f0f",
            "\u80fd\u529b\u8def\u7ebf\u56fe",
            "\u98ce\u9669\u63a7\u5236",
            "\u6cbb\u7406\u673a\u5236",
            "\u91c7\u7eb3\u8ba1\u5212",
            "\u6307\u6807\u4e0e\u91cc\u7a0b\u7891",
        ]
        if chinese
        else [
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
    )
    middle_count = slide_count - 3
    for index in range(middle_count):
        base_title = middle_titles[index % len(middle_titles)]
        title = base_title if index < len(middle_titles) else f"{base_title} {index + 1}"
        slides.append(
            {
                "title": title,
                "prototype_hint": "content",
                "speaker_notes": (
                    "\u5148\u843d\u4e00\u4e2a\u6838\u5fc3\u4fe1\u606f\uff0c\u518d\u7528\u8bc1\u636e\u652f\u6491\uff0c\u907f\u514d\u628a\u9875\u9762\u8bb2\u6210\u62a5\u544a\u3002"
                    if chinese
                    else "Land one message, then use the evidence point to support it without over-explaining the slide."
                ),
                "points": [
                    {
                        "label": "\u6838\u5fc3\u4fe1\u606f" if chinese else "Key message",
                        "body": (
                            "\u8bf4\u6e05\u8fd9\u9875\u5e0c\u671b\u542c\u4f17\u8bb0\u4f4f\u7684\u5355\u4e00\u7ed3\u8bba\u3002"
                            if chinese
                            else "State the single takeaway this slide should land."
                        ),
                    },
                    {
                        "label": "\u8bc1\u636e" if chinese else "Evidence",
                        "body": (
                            "\u8865\u5145\u652f\u6491\u8be5\u7ed3\u8bba\u7684\u6570\u636e\u3001\u6848\u4f8b\u6216\u5173\u952e\u4e8b\u5b9e\u3002"
                            if chinese
                            else "Add the proof point, metric, or example that supports the message."
                        ),
                    },
                ],
            }
        )

    slides.append(
        {
            "title": "\u5b9e\u65bd\u8def\u7ebf\u56fe" if chinese else "Implementation roadmap",
            "prototype_hint": "content",
            "speaker_notes": (
                "\u7528\u5177\u4f53\u3001\u6709\u987a\u5e8f\u3001\u53ef\u8861\u91cf\u7684\u4e0b\u4e00\u6b65\u6536\u5c3e\u3002"
                if chinese
                else "Close by making the next steps concrete, sequenced, and measurable."
            ),
            "bullets": [
                "\u660e\u786e\u76ee\u6807\u8fd0\u8425\u6a21\u5f0f\u3002" if chinese else "Define the target operating model.",
                "\u4f18\u5148\u63a8\u8fdb\u9ad8\u4ef7\u503c\u7528\u4f8b\u3002" if chinese else "Prioritize high-leverage use cases.",
                "\u6309\u53ef\u8861\u91cf\u8282\u70b9\u5206\u9636\u6bb5\u843d\u5730\u3002" if chinese else "Sequence rollout with measurable checkpoints.",
            ],
        }
    )
    return slides


def _recommended_path_slide(chinese: bool = False) -> dict[str, object]:
    return {
        "title": "\u63a8\u8350\u8def\u5f84" if chinese else "Recommended path",
        "prototype_hint": "content",
        "speaker_notes": (
            "\u5148\u8bf4\u660e\u63a8\u8350\u65b9\u6848\uff0c\u518d\u89e3\u91ca\u4e3a\u4ec0\u4e48\u5b83\u4f18\u4e8e\u5176\u4ed6\u9009\u9879\u3002"
            if chinese
            else "State the recommendation first, then describe why this path is better than the alternatives."
        ),
        "bullets": [
            "\u660e\u786e\u76ee\u6807\u8fd0\u8425\u6a21\u5f0f\u3002" if chinese else "Define the target operating model.",
            "\u4f18\u5148\u63a8\u8fdb\u9ad8\u4ef7\u503c\u7528\u4f8b\u3002" if chinese else "Prioritize high-leverage use cases.",
            "\u6309\u53ef\u8861\u91cf\u8282\u70b9\u5206\u9636\u6bb5\u843d\u5730\u3002" if chinese else "Sequence rollout with measurable checkpoints.",
        ],
    }
