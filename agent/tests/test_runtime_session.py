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


class ThemedOutlinePlanner:
    async def create_outline(self, prompt):
        return {
            "deck_title": "Themed Deck",
            "theme": {
                "name": "executive-consulting",
                "background": "#EEF2F7",
                "slide_background": "#FFFFFF",
                "text": "#111827",
                "accent": "#2563EB",
            },
            "slides": [
                {
                    "title": "Themed Deck",
                    "subtitle": "Generated with a planner theme",
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
        "tool.completed",
        "deck.updated",
        "tool.completed",
        "preview.ready",
        "tool.completed",
        "pptx.ready",
        "plan.updated",
    ]
    assert [event.seq for event in events] == list(range(1, 10))
    assert events[1].payload["plan"]["plan_id"] == "deck_001-r1-plan"
    assert events[1].payload["plan"]["status"] == "running"
    assert events[1].payload["plan"]["slide_count"] == 5
    assert events[1].payload["plan"]["steps"][0]["status"] == "completed"
    assert events[1].payload["plan"]["steps"][1]["status"] == "completed"
    assert events[1].payload["plan"]["steps"][2]["step_id"] == "draft_slides"
    assert events[1].payload["plan"]["steps"][2]["title"] == "Draft 5 slides"
    assert events[1].payload["plan"]["steps"][2]["status"] == "running"
    assert events[8].payload["plan"]["status"] == "completed"
    assert all(step["status"] == "completed" for step in events[8].payload["plan"]["steps"])
    assert events[2].payload == {
        "tool_name": "deck.create_from_outline",
        "status": "completed",
        "summary": "Created deck from outline.",
    }
    assert events[2].deck_revision == 1
    assert events[3].deck_revision == 1
    assert events[4].payload == {
        "tool_name": "preview.render_html",
        "status": "completed",
        "summary": "Rendered live preview HTML.",
    }
    assert events[5].payload["html"].startswith("<!doctype html>")
    assert "board AI strategy" in events[5].payload["html"]
    assert events[6].payload == {
        "tool_name": "pptx.export",
        "status": "completed",
        "summary": "Exported editable PPTX artifact.",
    }
    assert events[7].payload["path"].endswith("deck_001-r1.pptx")
    assert events[7].payload["slide_count"] == 5
    assert len(Presentation(events[7].payload["path"]).slides) == 5


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
    assert events[3].payload["deck"]["title"] == "Planner Deck"
    assert "Planner Deck" in events[5].payload["html"]
    assert events[7].payload["slide_count"] == 1


def test_agent_session_preserves_planner_theme_for_preview_and_export(tmp_path):
    session = AgentSession(
        session_id="session_themed",
        deck_id="deck_themed",
        outline_planner=ThemedOutlinePlanner(),
        artifact_dir=tmp_path,
    )

    async def collect():
        return [event async for event in session.submit_user_message("Make an executive deck")]

    events = asyncio.run(collect())
    presentation = Presentation(events[7].payload["path"])

    assert events[3].payload["deck"]["theme"]["name"] == "executive-consulting"
    assert "--slide-accent: #2563EB;" in events[5].payload["html"]
    assert str(presentation.slides[0].shapes[0].fill.fore_color.rgb) == "2563EB"


def test_agent_session_preserves_prompt_metadata_for_preview_and_export(tmp_path):
    session = AgentSession(session_id="session_metadata", deck_id="deck_metadata", artifact_dir=tmp_path)

    async def collect():
        return [
            event
            async for event in session.submit_user_message(
                "Make a 3 page AI strategy deck for the executive committee, style McKinsey"
            )
        ]

    events = asyncio.run(collect())
    presentation = Presentation(events[7].payload["path"])

    assert events[3].payload["deck"]["metadata"] == {
        "audience": "executive committee",
        "style": "McKinsey",
    }
    assert '<meta name="ppt-agent-audience" content="executive committee" />' in events[5].payload["html"]
    assert presentation.core_properties.subject == "executive committee"
    assert presentation.core_properties.keywords == "McKinsey"


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
    assert events[3].payload["deck"]["title"] == "Custom Deck"
    assert events[5].payload["html"] == "<!doctype html><title>Custom</title>"
    assert events[7].payload["path"].endswith("deck_004-r1.pptx")
