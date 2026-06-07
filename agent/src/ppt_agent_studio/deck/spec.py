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

    def __post_init__(self) -> None:
        if self.revision < 0:
            raise ValueError("revision must be non-negative")
        if not self.deck_id.strip():
            raise ValueError("deck_id is required")
        title = self.title.strip() or "Untitled Deck"
        object.__setattr__(self, "deck_id", self.deck_id.strip())
        object.__setattr__(self, "title", title)
        object.__setattr__(self, "theme", dict(self.theme) if isinstance(self.theme, dict) else {})

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "deck_id": self.deck_id,
            "title": self.title,
            "revision": self.revision,
            "slides": [slide.to_dict() for slide in self.slides],
        }
        if self.theme:
            payload["theme"] = dict(self.theme)
        return payload


def deck_from_outline(outline: dict[str, Any], deck_id: str, revision: int = 0) -> DeckSpec:
    title = str(outline.get("deck_title") or outline.get("title") or "Untitled Deck")
    raw_slides = outline.get("slides") if isinstance(outline.get("slides"), list) else []
    slides: list[SlideSpec] = []
    for index, raw_slide in enumerate(raw_slides, start=1):
        if not isinstance(raw_slide, dict):
            continue
        slide_title = str(raw_slide.get("title") or raw_slide.get("section_title") or f"Slide {index}")
        layout = str(raw_slide.get("prototype_hint") or raw_slide.get("layout") or "content")
        blocks = _blocks_from_outline_slide(raw_slide)
        slides.append(
            SlideSpec(
                slide_id=str(raw_slide.get("slide_id") or f"s{index}"),
                title=slide_title,
                layout=layout,
                blocks=blocks,
                speaker_notes=_speaker_notes_from_outline_slide(raw_slide),
            )
        )
    raw_theme = outline.get("theme") if isinstance(outline.get("theme"), dict) else {}
    return DeckSpec(deck_id=deck_id, title=title, revision=revision, slides=slides, theme=raw_theme)


def _blocks_from_outline_slide(slide: dict[str, Any]) -> list[Block]:
    blocks: list[Block] = []
    subtitle = str(slide.get("subtitle") or "").strip()
    if subtitle:
        blocks.append({"type": "subtitle", "text": subtitle})

    toc_items = slide.get("toc_items") if isinstance(slide.get("toc_items"), list) else []
    for item in toc_items:
        text = str(item).strip()
        if text:
            blocks.append({"type": "toc_item", "text": text})

    points = slide.get("points") if isinstance(slide.get("points"), list) else []
    for point in points:
        if not isinstance(point, dict):
            continue
        label = str(point.get("label") or "").strip()
        body = str(point.get("body") or "").strip()
        if label or body:
            blocks.append({"type": "point", "label": label, "body": body})

    bullets = slide.get("bullets") if isinstance(slide.get("bullets"), list) else []
    for bullet in bullets:
        text = str(bullet).strip()
        if text:
            blocks.append({"type": "bullet", "text": text})

    summary_items = slide.get("summary_items") if isinstance(slide.get("summary_items"), list) else []
    for item in summary_items:
        text = str(item).strip()
        if text:
            blocks.append({"type": "summary_item", "text": text})
    return blocks


def _speaker_notes_from_outline_slide(slide: dict[str, Any]) -> str:
    for key in ("speaker_notes", "notes", "talk_track"):
        value = slide.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""
