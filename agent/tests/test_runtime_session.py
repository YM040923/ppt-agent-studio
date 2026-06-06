import asyncio

from pptx import Presentation

from ppt_agent_studio.runtime.session import AgentSession
from ppt_agent_studio.tools.base import ToolDefinition, ToolRegistry, ToolResult


class FakeOutlinePlanner:
    def __init__(self):
        self.prompts = []

    async def create_outline(self, prompt):
        self.prompts.append(prompt)
        return {
            "deck_title": "Planner Deck",
            "slides": [
                {
                    "title": "Planner Deck",
                    "subtitle": "Generated through an injected planner",
                    "prototype_hint": "cover",
                }
            ],
        }


def test_agent_session_turn_emits_ordered_preview_and_pptx_events(tmp_path):
    session = AgentSession(session_id="session_001", deck_id="deck_001", artifact_dir=tmp_path)

    async def collect():
        return [event async for event in session.submit_user_message("Make a 5 slide board AI strategy deck")]

    events = asyncio.run(collect())

    assert [event.type for event in events] == [
        "user.message",
        "plan.updated",
        "deck.updated",
        "pptx.ready",
        "preview.ready",
    ]
    assert [event.seq for event in events] == [1, 2, 3, 4, 5]
    assert events[1].payload["plan"]["plan_id"] == "deck_001-r1-plan"
    assert events[1].payload["plan"]["slide_count"] == 3
    assert events[1].payload["plan"]["steps"][2]["step_id"] == "draft_slides"
    assert events[2].deck_revision == 1
    assert events[3].payload["path"].endswith("deck_001-r1.pptx")
    assert events[3].payload["slide_count"] == 3
    assert len(Presentation(events[3].payload["path"]).slides) == 3
    assert events[4].payload["html"].startswith("<!doctype html>")
    assert "board AI strategy" in events[4].payload["html"]


def test_agent_session_ignores_empty_user_message():
    session = AgentSession(session_id="session_002", deck_id="deck_002")

    async def collect():
        return [event async for event in session.submit_user_message("   ")]

    events = asyncio.run(collect())

    assert len(events) == 1
    assert events[0].type == "error"
    assert events[0].payload["message"] == "User message is required"


def test_agent_session_uses_injected_outline_planner(tmp_path):
    planner = FakeOutlinePlanner()
    session = AgentSession(
        session_id="session_003",
        deck_id="deck_003",
        outline_planner=planner,
        artifact_dir=tmp_path,
    )

    async def collect():
        return [event async for event in session.submit_user_message("Make a CFO margin story")]

    events = asyncio.run(collect())

    assert planner.prompts == ["Make a CFO margin story"]
    assert events[1].payload["outline"]["deck_title"] == "Planner Deck"
    assert events[2].payload["deck"]["title"] == "Planner Deck"
    assert events[3].payload["slide_count"] == 1
    assert "Planner Deck" in events[4].payload["html"]


def test_agent_session_uses_tool_registry_for_deck_and_preview():
    calls = []
    registry = ToolRegistry()

    def create_deck(args):
        calls.append(("deck.create_from_outline", args["deck_id"]))
        return ToolResult(
            payload={
                "deck": {
                    "deck_id": args["deck_id"],
                    "title": "Custom Deck",
                    "revision": args["revision"],
                    "slides": [],
                }
            }
        )

    def render_preview(args):
        calls.append(("preview.render_html", args["deck"]["title"]))
        return ToolResult(payload={"html": "<!doctype html><title>Custom</title>"})

    registry.register(
        ToolDefinition(
            name="deck.create_from_outline",
            description="Create a deck.",
            input_schema={"type": "object"},
        ),
        create_deck,
    )
    registry.register(
        ToolDefinition(
            name="preview.render_html",
            description="Render preview HTML.",
            input_schema={"type": "object"},
        ),
        render_preview,
    )
    registry.register(
        ToolDefinition(
            name="pptx.export",
            description="Export a deck.",
            input_schema={"type": "object"},
        ),
        lambda args: ToolResult(payload={"path": args["output_path"], "slide_count": 0}),
    )
    session = AgentSession(session_id="session_004", deck_id="deck_004", tool_registry=registry)

    async def collect():
        return [event async for event in session.submit_user_message("Make a sales deck")]

    events = asyncio.run(collect())

    assert calls == [
        ("deck.create_from_outline", "deck_004"),
        ("preview.render_html", "Custom Deck"),
    ]
    assert events[2].payload["deck"]["title"] == "Custom Deck"
    assert events[3].payload["path"].endswith("deck_004-r1.pptx")
    assert events[4].payload["html"] == "<!doctype html><title>Custom</title>"
