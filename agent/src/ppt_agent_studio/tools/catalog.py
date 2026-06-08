from __future__ import annotations

from ppt_agent_studio.tools.base import ToolDefinition


def core_tool_definitions() -> list[ToolDefinition]:
    return [
        ToolDefinition(
            name="deck.create_from_outline",
            description="Create a DeckSpec from a structured presentation outline.",
            input_schema={
                "type": "object",
                "required": ["outline", "deck_id"],
                "properties": {
                    "outline": {"type": "object"},
                    "deck_id": {"type": "string"},
                    "revision": {"type": "integer", "minimum": 0},
                },
            },
        ),
        ToolDefinition(
            name="deck.update_slide",
            description="Update one slide in the current DeckSpec by slide_id.",
            input_schema={
                "type": "object",
                "required": ["deck", "slide_id", "patch"],
                "properties": {
                    "deck": {"type": "object"},
                    "slide_id": {"type": "string"},
                    "patch": {"type": "object"},
                },
            },
        ),
        ToolDefinition(
            name="deck.add_slide",
            description="Append or insert a slide into the current DeckSpec.",
            input_schema={
                "type": "object",
                "required": ["deck", "slide"],
                "properties": {
                    "deck": {"type": "object"},
                    "slide": {"type": "object"},
                    "after_slide_id": {"type": "string"},
                    "before_slide_id": {"type": "string"},
                },
            },
        ),
        ToolDefinition(
            name="deck.remove_slide",
            description="Remove a slide from the current DeckSpec by slide_id.",
            input_schema={
                "type": "object",
                "required": ["deck", "slide_id"],
                "properties": {
                    "deck": {"type": "object"},
                    "slide_id": {"type": "string"},
                },
            },
        ),
        ToolDefinition(
            name="preview.render_html",
            description="Render the current DeckSpec as an HTML preview document.",
            input_schema={
                "type": "object",
                "required": ["deck"],
                "properties": {"deck": {"type": "object"}},
            },
        ),
        ToolDefinition(
            name="pptx.export",
            description="Export the current DeckSpec to an editable PowerPoint file.",
            input_schema={
                "type": "object",
                "required": ["deck", "output_path"],
                "properties": {
                    "deck": {"type": "object"},
                    "output_path": {"type": "string"},
                },
            },
        ),
        ToolDefinition(
            name="research.collect_brief",
            description="Collect a concise source brief for the deck topic and audience.",
            input_schema={
                "type": "object",
                "required": ["topic", "audience"],
                "properties": {
                    "topic": {"type": "string"},
                    "audience": {"type": "string"},
                    "constraints": {"type": "array", "items": {"type": "string"}},
                },
            },
        ),
        ToolDefinition(
            name="design.apply_theme",
            description="Apply a presentation theme token set to the DeckSpec.",
            input_schema={
                "type": "object",
                "required": ["deck", "theme"],
                "properties": {
                    "deck": {"type": "object"},
                    "theme": {"type": "object"},
                },
            },
        ),
    ]
