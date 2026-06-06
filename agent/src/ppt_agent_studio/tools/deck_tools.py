from __future__ import annotations

from pathlib import Path
from typing import Any

from pptx import Presentation
from pptx.util import Inches, Pt

from ppt_agent_studio.deck.spec import DeckSpec, SlideSpec, deck_from_outline
from ppt_agent_studio.preview.html_renderer import render_preview_document
from ppt_agent_studio.tools.base import ToolRegistry, ToolResult
from ppt_agent_studio.tools.catalog import core_tool_definitions


def build_default_registry() -> ToolRegistry:
    registry = ToolRegistry()
    definitions = {definition.name: definition for definition in core_tool_definitions()}
    registry.register(definitions["deck.create_from_outline"], create_deck_from_outline)
    registry.register(definitions["preview.render_html"], render_preview_html)
    registry.register(definitions["pptx.export"], export_pptx)
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


def export_pptx(arguments: dict[str, Any]) -> ToolResult:
    raw_deck = arguments.get("deck")
    if not isinstance(raw_deck, dict):
        raise ValueError("deck must be an object")
    output_path = Path(str(arguments.get("output_path") or "")).expanduser()
    if not output_path.name:
        raise ValueError("output_path is required")

    deck = _deck_from_dict(raw_deck)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    presentation = Presentation()
    presentation.slide_width = Inches(13.333)
    presentation.slide_height = Inches(7.5)
    blank_layout = presentation.slide_layouts[6]

    for slide in deck.slides:
        ppt_slide = presentation.slides.add_slide(blank_layout)
        _add_textbox(
            ppt_slide,
            left=0.65,
            top=0.45,
            width=11.8,
            height=0.75,
            text=slide.title,
            font_size=30,
            bold=True,
        )
        y = 1.45
        for block in slide.blocks:
            block_text = _block_text(block)
            if not block_text:
                continue
            _add_textbox(
                ppt_slide,
                left=0.85,
                top=y,
                width=11.1,
                height=0.5,
                text=block_text,
                font_size=18,
                bold=block.get("type") == "subtitle",
            )
            y += 0.58

    presentation.save(output_path)
    return ToolResult(payload={"path": str(output_path), "slide_count": len(deck.slides)})


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


def _add_textbox(slide: Any, left: float, top: float, width: float, height: float, text: str, font_size: int, bold: bool) -> None:
    shape = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
    paragraph = shape.text_frame.paragraphs[0]
    run = paragraph.add_run()
    run.text = text
    run.font.size = Pt(font_size)
    run.font.bold = bold


def _block_text(block: dict[str, Any]) -> str:
    block_type = str(block.get("type") or "text")
    if block_type == "point":
        label = str(block.get("label") or "").strip()
        body = str(block.get("body") or "").strip()
        if label and body:
            return f"{label}: {body}"
        return label or body
    return str(block.get("text") or "").strip()
