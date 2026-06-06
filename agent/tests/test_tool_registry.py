import asyncio

import pytest

from ppt_agent_studio.tools.base import ToolDefinition, ToolRegistry, ToolResult
from ppt_agent_studio.tools.catalog import core_tool_definitions
from ppt_agent_studio.tools.deck_tools import build_default_registry


def test_core_tool_catalog_lists_mvp_interfaces():
    definitions = core_tool_definitions()
    names = [definition.name for definition in definitions]

    assert len(definitions) >= 8
    assert len(names) == len(set(names))
    assert {
        "deck.create_from_outline",
        "deck.update_slide",
        "deck.add_slide",
        "deck.remove_slide",
        "preview.render_html",
        "pptx.export",
        "research.collect_brief",
        "design.apply_theme",
    }.issubset(set(names))
    assert all(definition.input_schema.get("type") == "object" for definition in definitions)


def test_tool_registry_rejects_duplicate_tools():
    definition = ToolDefinition(
        name="demo.echo",
        description="Echo test arguments.",
        input_schema={"type": "object"},
    )
    registry = ToolRegistry()
    registry.register(definition, lambda args: ToolResult(payload=dict(args)))

    with pytest.raises(ValueError, match="already registered"):
        registry.register(definition, lambda args: ToolResult(payload=dict(args)))


def test_tool_registry_runs_sync_and_async_handlers():
    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="demo.sync",
            description="Return a synchronous result.",
            input_schema={"type": "object"},
        ),
        lambda args: ToolResult(payload={"kind": "sync", "value": args["value"]}),
    )

    async def async_handler(args):
        return ToolResult(payload={"kind": "async", "value": args["value"]})

    registry.register(
        ToolDefinition(
            name="demo.async",
            description="Return an asynchronous result.",
            input_schema={"type": "object"},
        ),
        async_handler,
    )

    async def run():
        return [
            await registry.run("demo.sync", {"value": 1}),
            await registry.run("demo.async", {"value": 2}),
        ]

    results = asyncio.run(run())

    assert [result.payload for result in results] == [
        {"kind": "sync", "value": 1},
        {"kind": "async", "value": 2},
    ]


def test_tool_registry_validates_required_arguments_before_running_handler():
    calls = []
    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="demo.required",
            description="Require an argument.",
            input_schema={"type": "object", "required": ["value"]},
        ),
        lambda args: calls.append(args) or ToolResult(),
    )

    async def run():
        return await registry.run("demo.required", {})

    with pytest.raises(ValueError, match="missing required tool argument: value"):
        asyncio.run(run())
    assert calls == []


def test_default_registry_creates_deck_and_preview_html():
    registry = build_default_registry()
    outline = {
        "deck_title": "AI Strategy",
        "slides": [
            {"title": "AI Strategy", "subtitle": "Board briefing", "prototype_hint": "cover"},
            {"title": "Priorities", "bullets": ["Focus", "Sequence"], "prototype_hint": "content"},
        ],
    }

    async def run():
        deck_result = await registry.run(
            "deck.create_from_outline",
            {"outline": outline, "deck_id": "deck_001", "revision": 2},
        )
        preview_result = await registry.run("preview.render_html", {"deck": deck_result.payload["deck"]})
        return deck_result, preview_result

    deck_result, preview_result = asyncio.run(run())

    assert deck_result.payload["deck"]["title"] == "AI Strategy"
    assert deck_result.payload["deck"]["revision"] == 2
    assert preview_result.payload["html"].startswith("<!doctype html>")
    assert "AI Strategy" in preview_result.payload["html"]


def test_default_registry_updates_adds_and_removes_slides():
    registry = build_default_registry()
    deck = {
        "deck_id": "deck_001",
        "title": "AI Strategy",
        "revision": 3,
        "slides": [
            {
                "slide_id": "s1",
                "title": "Cover",
                "layout": "cover",
                "blocks": [{"type": "subtitle", "text": "Board briefing"}],
            },
            {
                "slide_id": "s2",
                "title": "Priorities",
                "layout": "content",
                "blocks": [{"type": "bullet", "text": "Focus"}],
            },
        ],
    }

    async def run():
        updated = await registry.run(
            "deck.update_slide",
            {
                "deck": deck,
                "slide_id": "s2",
                "patch": {
                    "title": "Strategic Priorities",
                    "blocks": [{"type": "bullet", "text": "Sequence the rollout"}],
                },
            },
        )
        added = await registry.run(
            "deck.add_slide",
            {
                "deck": updated.payload["deck"],
                "slide": {
                    "slide_id": "s3",
                    "title": "Roadmap",
                    "layout": "content",
                    "blocks": [{"type": "bullet", "text": "90 day launch"}],
                },
                "after_slide_id": "s1",
            },
        )
        removed = await registry.run(
            "deck.remove_slide",
            {"deck": added.payload["deck"], "slide_id": "s1"},
        )
        return updated.payload["deck"], added.payload["deck"], removed.payload["deck"]

    updated, added, removed = asyncio.run(run())

    assert updated["revision"] == 4
    assert updated["slides"][1]["title"] == "Strategic Priorities"
    assert updated["slides"][1]["blocks"][0]["text"] == "Sequence the rollout"

    assert added["revision"] == 5
    assert [slide["slide_id"] for slide in added["slides"]] == ["s1", "s3", "s2"]

    assert removed["revision"] == 6
    assert [slide["slide_id"] for slide in removed["slides"]] == ["s3", "s2"]


def test_default_registry_runs_research_and_theme_tools():
    registry = build_default_registry()
    deck = {
        "deck_id": "deck_001",
        "title": "AI Strategy",
        "revision": 1,
        "slides": [],
    }

    async def run():
        brief = await registry.run(
            "research.collect_brief",
            {
                "topic": "AI operating model",
                "audience": "executive committee",
                "constraints": ["McKinsey style", "20 slides"],
            },
        )
        themed = await registry.run(
            "design.apply_theme",
            {
                "deck": deck,
                "theme": {
                    "name": "executive-dark",
                    "background": "#111827",
                    "slide_background": "#F8FAFC",
                    "accent": "#2563EB",
                },
            },
        )
        preview = await registry.run("preview.render_html", {"deck": themed.payload["deck"]})
        return brief.payload["brief"], themed.payload["deck"], preview.payload["html"]

    brief, themed_deck, preview_html = asyncio.run(run())

    assert brief["topic"] == "AI operating model"
    assert brief["audience"] == "executive committee"
    assert brief["constraints"] == ["McKinsey style", "20 slides"]
    assert "Clarify the decision the deck must support." in brief["questions"]

    assert themed_deck["revision"] == 2
    assert themed_deck["theme"] == {
        "name": "executive-dark",
        "background": "#111827",
        "slide_background": "#F8FAFC",
        "accent": "#2563EB",
    }
    assert "--preview-background: #111827;" in preview_html
    assert "--slide-background: #F8FAFC;" in preview_html
