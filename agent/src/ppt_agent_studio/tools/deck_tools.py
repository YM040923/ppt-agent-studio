from __future__ import annotations

from pathlib import Path
import re
from typing import Any

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.util import Inches, Pt

from ppt_agent_studio.deck.spec import DeckSpec, SlideSpec, deck_from_outline
from ppt_agent_studio.preview.html_renderer import render_preview_document
from ppt_agent_studio.tools.base import ToolRegistry, ToolResult
from ppt_agent_studio.tools.catalog import core_tool_definitions


_HEX_COLOR = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")


def build_default_registry() -> ToolRegistry:
    registry = ToolRegistry()
    definitions = {definition.name: definition for definition in core_tool_definitions()}
    registry.register(definitions["deck.create_from_outline"], create_deck_from_outline)
    registry.register(definitions["deck.update_slide"], update_slide)
    registry.register(definitions["deck.add_slide"], add_slide)
    registry.register(definitions["deck.remove_slide"], remove_slide)
    registry.register(definitions["preview.render_html"], render_preview_html)
    registry.register(definitions["pptx.export"], export_pptx)
    registry.register(definitions["research.collect_brief"], collect_research_brief)
    registry.register(definitions["design.apply_theme"], apply_theme)
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


def update_slide(arguments: dict[str, Any]) -> ToolResult:
    deck = _deck_from_arguments(arguments)
    slide_id = str(arguments.get("slide_id") or "").strip()
    patch = arguments.get("patch")
    if not slide_id:
        raise ValueError("slide_id is required")
    if not isinstance(patch, dict):
        raise ValueError("patch must be an object")

    slides: list[SlideSpec] = []
    found = False
    for slide in deck.slides:
        if slide.slide_id != slide_id:
            slides.append(slide)
            continue
        found = True
        slides.append(
            SlideSpec(
                slide_id=str(patch.get("slide_id") or slide.slide_id),
                title=str(patch.get("title") or slide.title),
                layout=str(patch.get("layout") or slide.layout),
                blocks=patch.get("blocks") if isinstance(patch.get("blocks"), list) else slide.blocks,
                speaker_notes=str(patch.get("speaker_notes") or slide.speaker_notes),
            )
        )
    if not found:
        raise ValueError(f"slide not found: {slide_id}")
    return ToolResult(payload={"deck": _deck_with_slides(deck, slides).to_dict()})


def add_slide(arguments: dict[str, Any]) -> ToolResult:
    deck = _deck_from_arguments(arguments)
    raw_slide = arguments.get("slide")
    if not isinstance(raw_slide, dict):
        raise ValueError("slide must be an object")
    new_slide = _slide_from_dict(raw_slide, len(deck.slides) + 1)
    after_slide_id = str(arguments.get("after_slide_id") or "").strip()

    slides = list(deck.slides)
    if after_slide_id:
        for index, slide in enumerate(slides):
            if slide.slide_id == after_slide_id:
                slides.insert(index + 1, new_slide)
                break
        else:
            raise ValueError(f"slide not found: {after_slide_id}")
    else:
        slides.append(new_slide)
    return ToolResult(payload={"deck": _deck_with_slides(deck, slides).to_dict()})


def remove_slide(arguments: dict[str, Any]) -> ToolResult:
    deck = _deck_from_arguments(arguments)
    slide_id = str(arguments.get("slide_id") or "").strip()
    if not slide_id:
        raise ValueError("slide_id is required")
    slides = [slide for slide in deck.slides if slide.slide_id != slide_id]
    if len(slides) == len(deck.slides):
        raise ValueError(f"slide not found: {slide_id}")
    return ToolResult(payload={"deck": _deck_with_slides(deck, slides).to_dict()})


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
    presentation.core_properties.title = deck.title
    audience = _metadata_text(deck, "audience")
    style = _metadata_text(deck, "style")
    if audience:
        presentation.core_properties.subject = audience
    if style:
        presentation.core_properties.keywords = style
    blank_layout = presentation.slide_layouts[6]

    for index, slide in enumerate(deck.slides, start=1):
        ppt_slide = presentation.slides.add_slide(blank_layout)
        slide_background = _theme_rgb(deck, "slide_background", "#FFFFFF")
        text_color = _theme_rgb(deck, "text", "#111827")
        accent_color = _theme_rgb(deck, "accent", "#2563EB")
        ppt_slide.background.fill.solid()
        ppt_slide.background.fill.fore_color.rgb = slide_background
        _add_accent_bar(ppt_slide, presentation.slide_width, accent_color)
        _add_textbox(
            ppt_slide,
            left=0.65,
            top=6.95,
            width=0.55,
            height=0.2,
            text=f"{index:02d}",
            font_size=10,
            bold=True,
            font_color=accent_color,
        )
        if slide.speaker_notes:
            ppt_slide.notes_slide.notes_text_frame.text = slide.speaker_notes
        _add_textbox(
            ppt_slide,
            left=0.65,
            top=0.45,
            width=11.8,
            height=0.75,
            text=slide.title,
            font_size=30,
            bold=True,
            font_color=text_color,
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
                font_color=text_color,
            )
            y += 0.58

    presentation.save(output_path)
    return ToolResult(payload={"path": str(output_path), "slide_count": len(deck.slides)})


def collect_research_brief(arguments: dict[str, Any]) -> ToolResult:
    topic = str(arguments.get("topic") or "").strip()
    audience = str(arguments.get("audience") or "").strip()
    raw_constraints = arguments.get("constraints")
    constraints = [str(item) for item in raw_constraints] if isinstance(raw_constraints, list) else []
    if not topic:
        raise ValueError("topic is required")
    if not audience:
        raise ValueError("audience is required")
    return ToolResult(
        payload={
            "brief": {
                "topic": topic,
                "audience": audience,
                "constraints": constraints,
                "questions": [
                    "Clarify the decision the deck must support.",
                    "Identify the audience's current belief and desired shift.",
                    "List the proof points needed for executive confidence.",
                ],
            }
        }
    )


def apply_theme(arguments: dict[str, Any]) -> ToolResult:
    raw_deck = arguments.get("deck")
    theme = arguments.get("theme")
    if not isinstance(raw_deck, dict):
        raise ValueError("deck must be an object")
    if not isinstance(theme, dict):
        raise ValueError("theme must be an object")
    deck = dict(raw_deck)
    deck["revision"] = int(deck.get("revision") or 0) + 1
    deck["theme"] = dict(theme)
    return ToolResult(payload={"deck": deck})


def _deck_from_dict(raw_deck: dict[str, Any]) -> DeckSpec:
    raw_slides = raw_deck.get("slides") if isinstance(raw_deck.get("slides"), list) else []
    slides = [
            SlideSpec(
                slide_id=str(raw_slide.get("slide_id") or f"s{index}"),
                title=str(raw_slide.get("title") or f"Slide {index}"),
                layout=str(raw_slide.get("layout") or "content"),
                blocks=raw_slide.get("blocks") if isinstance(raw_slide.get("blocks"), list) else [],
                speaker_notes=str(raw_slide.get("speaker_notes") or ""),
            )
        for index, raw_slide in enumerate(raw_slides, start=1)
        if isinstance(raw_slide, dict)
    ]
    return DeckSpec(
        deck_id=str(raw_deck.get("deck_id") or "deck"),
        title=str(raw_deck.get("title") or "Untitled Deck"),
        revision=int(raw_deck.get("revision") or 0),
        slides=slides,
        theme=raw_deck.get("theme") if isinstance(raw_deck.get("theme"), dict) else {},
        metadata=raw_deck.get("metadata") if isinstance(raw_deck.get("metadata"), dict) else {},
    )


def _deck_from_arguments(arguments: dict[str, Any]) -> DeckSpec:
    raw_deck = arguments.get("deck")
    if not isinstance(raw_deck, dict):
        raise ValueError("deck must be an object")
    return _deck_from_dict(raw_deck)


def _slide_from_dict(raw_slide: dict[str, Any], index: int) -> SlideSpec:
    return SlideSpec(
        slide_id=str(raw_slide.get("slide_id") or f"s{index}"),
        title=str(raw_slide.get("title") or f"Slide {index}"),
        layout=str(raw_slide.get("layout") or "content"),
        blocks=raw_slide.get("blocks") if isinstance(raw_slide.get("blocks"), list) else [],
        speaker_notes=str(raw_slide.get("speaker_notes") or ""),
    )


def _deck_with_slides(deck: DeckSpec, slides: list[SlideSpec]) -> DeckSpec:
    return DeckSpec(
        deck_id=deck.deck_id,
        title=deck.title,
        revision=deck.revision + 1,
        slides=slides,
        theme=deck.theme,
        metadata=deck.metadata,
    )


def _add_accent_bar(slide: Any, slide_width: Any, accent_color: RGBColor) -> None:
    shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, slide_width, Inches(0.08))
    shape.fill.solid()
    shape.fill.fore_color.rgb = accent_color
    shape.line.fill.background()


def _add_textbox(
    slide: Any,
    left: float,
    top: float,
    width: float,
    height: float,
    text: str,
    font_size: int,
    bold: bool,
    font_color: RGBColor | None = None,
) -> None:
    shape = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
    paragraph = shape.text_frame.paragraphs[0]
    run = paragraph.add_run()
    run.text = text
    run.font.size = Pt(font_size)
    run.font.bold = bold
    if font_color is not None:
        run.font.color.rgb = font_color


def _block_text(block: dict[str, Any]) -> str:
    block_type = str(block.get("type") or "text")
    if block_type == "point":
        label = str(block.get("label") or "").strip()
        body = str(block.get("body") or "").strip()
        if label and body:
            return f"{label}: {body}"
        return label or body
    return str(block.get("text") or "").strip()


def _theme_rgb(deck: DeckSpec, key: str, fallback: str) -> RGBColor:
    raw_value = deck.theme.get(key)
    value = raw_value.strip() if isinstance(raw_value, str) else fallback
    if not _HEX_COLOR.fullmatch(value):
        value = fallback
    value = value.lstrip("#")
    if len(value) == 3:
        value = "".join(character * 2 for character in value)
    if len(value) == 8:
        value = value[:6]
    return RGBColor(int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16))


def _metadata_text(deck: DeckSpec, key: str) -> str:
    value = deck.metadata.get(key)
    return value.strip() if isinstance(value, str) else ""
