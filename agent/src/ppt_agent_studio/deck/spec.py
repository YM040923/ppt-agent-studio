from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


Block = dict[str, Any]


@dataclass(frozen=True)
class SlideSpec:
    slide_id: str
    title: str
    layout: str
    blocks: list[Block] = field(default_factory=list)
    speaker_notes: str = ""

    def __post_init__(self) -> None:
        title = self.title.strip()
        if not title:
            raise ValueError("slide title is required")
        if not self.slide_id.strip():
            raise ValueError("slide_id is required")
        if not self.layout.strip():
            raise ValueError("layout is required")
        object.__setattr__(self, "title", title)
        object.__setattr__(self, "slide_id", self.slide_id.strip())
        object.__setattr__(self, "layout", self.layout.strip())
        object.__setattr__(self, "speaker_notes", self.speaker_notes.strip())

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "slide_id": self.slide_id,
            "title": self.title,
            "layout": self.layout,
            "blocks": list(self.blocks),
        }
        if self.speaker_notes:
            payload["speaker_notes"] = self.speaker_notes
        return payload


@dataclass(frozen=True)
class DeckSpec:
    deck_id: str
    title: str
    revision: int
    slides: list[SlideSpec] = field(default_factory=list)
    theme: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.revision < 0:
            raise ValueError("revision must be non-negative")
        if not self.deck_id.strip():
            raise ValueError("deck_id is required")
        title = self.title.strip() or "Untitled Deck"
        object.__setattr__(self, "deck_id", self.deck_id.strip())
        object.__setattr__(self, "title", title)
        object.__setattr__(self, "theme", dict(self.theme) if isinstance(self.theme, dict) else {})
        object.__setattr__(self, "metadata", dict(self.metadata) if isinstance(self.metadata, dict) else {})

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "deck_id": self.deck_id,
            "title": self.title,
            "revision": self.revision,
            "slides": [slide.to_dict() for slide in self.slides],
        }
        if self.theme:
            payload["theme"] = dict(self.theme)
        if self.metadata:
            payload["metadata"] = dict(self.metadata)
        return payload


def deck_from_outline(outline: dict[str, Any], deck_id: str, revision: int = 0) -> DeckSpec:
    title = str(outline.get("deck_title") or outline.get("title") or "Untitled Deck")
    raw_slides = outline.get("slides") if isinstance(outline.get("slides"), list) else []
    slides: list[SlideSpec] = []
    used_slide_ids: set[str] = set()
    for index, raw_slide in enumerate(raw_slides, start=1):
        if not isinstance(raw_slide, dict):
            continue
        slide_title = _outline_text_value(
            raw_slide.get("title"),
            raw_slide.get("section_title"),
            default=f"Slide {index}",
        )
        layout = _outline_text_value(raw_slide.get("prototype_hint"), raw_slide.get("layout"), default="content")
        blocks = _blocks_from_outline_slide(raw_slide)
        slide_id = unique_slide_id(raw_slide.get("slide_id"), index, used_slide_ids)
        used_slide_ids.add(slide_id)
        slides.append(
            SlideSpec(
                slide_id=slide_id,
                title=slide_title,
                layout=layout,
                blocks=blocks,
                speaker_notes=_speaker_notes_from_outline_slide(raw_slide),
            )
        )
    raw_theme = outline.get("theme") if isinstance(outline.get("theme"), dict) else {}
    return DeckSpec(
        deck_id=deck_id,
        title=title,
        revision=revision,
        slides=slides,
        theme=raw_theme,
        metadata=_metadata_from_outline(outline),
    )


def unique_slide_id(raw_slide_id: Any, index: int, used_slide_ids: set[str]) -> str:
    candidate = str(raw_slide_id or "").strip()
    if not candidate or candidate in used_slide_ids:
        candidate = f"s{index}"
    while candidate in used_slide_ids:
        index += 1
        candidate = f"s{index}"
    return candidate


def _outline_text_value(primary: Any, secondary: Any, default: str) -> str:
    for value in (primary, secondary):
        if isinstance(value, str):
            text = value.strip()
            if text:
                return text
    return default


def _blocks_from_outline_slide(slide: dict[str, Any]) -> list[Block]:
    blocks: list[Block] = []
    subtitle = str(slide.get("subtitle") or "").strip()
    if subtitle:
        blocks.append({"type": "subtitle", "text": subtitle})

    content = _first_text_value(slide, ("content", "body", "key_message"))
    if content:
        blocks.append({"type": "text", "text": content})

    toc_items = slide.get("toc_items") if isinstance(slide.get("toc_items"), list) else []
    for item in toc_items:
        text = _outline_item_text(item)
        if text:
            blocks.append({"type": "toc_item", "text": text})

    points = slide.get("points") if isinstance(slide.get("points"), list) else []
    for point in points:
        label, body = _point_label_body(point)
        if label or body:
            blocks.append({"type": "point", "label": label, "body": body})

    bullets = slide.get("bullets") if isinstance(slide.get("bullets"), list) else []
    for bullet in bullets:
        text = _outline_item_text(bullet)
        if text:
            blocks.append({"type": "bullet", "text": text})

    summary_items = slide.get("summary_items") if isinstance(slide.get("summary_items"), list) else []
    for item in summary_items:
        text = _outline_item_text(item)
        if text:
            blocks.append({"type": "summary_item", "text": text})
    return blocks


def _speaker_notes_from_outline_slide(slide: dict[str, Any]) -> str:
    for key in ("speaker_notes", "notes", "talk_track"):
        value = slide.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _metadata_from_outline(outline: dict[str, Any]) -> dict[str, str]:
    raw_metadata = outline.get("metadata") if isinstance(outline.get("metadata"), dict) else {}
    audience = _first_text_value(raw_metadata, ("audience", "target_audience")) or _first_text_value(
        outline, ("audience", "target_audience")
    )
    style = _first_text_value(raw_metadata, ("style", "visual_style", "tone")) or _first_text_value(
        outline, ("style", "visual_style", "tone")
    )
    metadata: dict[str, str] = {}
    if audience:
        metadata["audience"] = audience
    if style:
        metadata["style"] = style
    return metadata


def _first_text_value(source: dict[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = source.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, dict):
            nested = _first_text_value(value, ("text", "value", "content", "body", "label", "title"))
            if nested:
                return nested
    return ""


def _outline_item_text(item: Any) -> str:
    if isinstance(item, dict):
        return _first_text_value(item, ("text", "body", "content", "value", "title", "label"))
    return str(item).strip()


def _point_label_body(point: Any) -> tuple[str, str]:
    if isinstance(point, dict):
        label = _first_text_value(point, ("label", "title", "name"))
        body = _first_text_value(point, ("body", "text", "content", "value", "description"))
        return label, body
    return "", str(point).strip()
