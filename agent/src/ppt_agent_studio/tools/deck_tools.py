from __future__ import annotations

from typing import Any

from ppt_agent_studio.deck.spec import DeckSpec, SlideSpec, deck_from_outline
from ppt_agent_studio.preview.html_renderer import render_preview_document
from ppt_agent_studio.tools.base import ToolRegistry, ToolResult
from ppt_agent_studio.tools.catalog import core_tool_definitions


def build_default_registry() -> ToolRegistry:
    registry = ToolRegistry()
    definitions = {definition.name: definition for definition in core_tool_definitions()}
    registry.register(definitions["deck.create_from_outline"], create_deck_from_outline)
    registry.register(definitions["preview.render_html"], render_preview_html)
    return registry


def create_deck_from_outline(arguments: dict[str, Any]) -> ToolResult:
    outline = arguments.get("outline")
    if not isinstance(outline, dict):
        raise ValueError("outline must be an object")
    deck_id = str(arguments.get("deck_id") or "").strip()
    if not deck_id:
        raise ValueError("deck_id is required")
    revision = int(arguments.get("revision") or 0)
    deck = deck_from_outline(outline, deck_id=deck_id, revision=revision)
    return ToolResult(payload={"deck": deck.to_dict()})


def render_preview_html(arguments: dict[str, Any]) -> ToolResult:
    raw_deck = arguments.get("deck")
    if not isinstance(raw_deck, dict):
        raise ValueError("deck must be an object")
    deck = _deck_from_dict(raw_deck)
    return ToolResult(payload={"html": render_preview_document(deck)})


def _deck_from_dict(raw_deck: dict[str, Any]) -> DeckSpec:
    raw_slides = raw_deck.get("slides") if isinstance(raw_deck.get("slides"), list) else []
    slides = [
        SlideSpec(
            slide_id=str(raw_slide.get("slide_id") or f"s{index}"),
            title=str(raw_slide.get("title") or f"Slide {index}"),
            layout=str(raw_slide.get("layout") or "content"),
            blocks=raw_slide.get("blocks") if isinstance(raw_slide.get("blocks"), list) else [],
        )
        for index, raw_slide in enumerate(raw_slides, start=1)
        if isinstance(raw_slide, dict)
    ]
    return DeckSpec(
        deck_id=str(raw_deck.get("deck_id") or "deck"),
        title=str(raw_deck.get("title") or "Untitled Deck"),
        revision=int(raw_deck.get("revision") or 0),
        slides=slides,
    )
