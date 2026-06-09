import asyncio
import json
from pathlib import Path

from ppt_agent_studio.runtime.demo import format_summary, run_demo


def test_run_demo_expands_user_artifact_directory(monkeypatch, tmp_path):
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))

    summary = asyncio.run(
        run_demo(
            prompt="Make a demo",
            artifact_dir="~/ppt-agent-demo",
            session_id="demo-session",
            deck_id="demo-deck",
        )
    )

    expected_dir = Path("~/ppt-agent-demo").expanduser()
    assert summary.preview_html_path.parent == expected_dir
    assert summary.pptx_path.parent == expected_dir
    assert summary.summary_json_path.parent == expected_dir
    assert summary.summary_markdown_path.parent == expected_dir


def test_run_demo_writes_preview_and_pptx(tmp_path):
    async def run():
        return await run_demo(
            prompt="Make a 5 slide board AI strategy deck in McKinsey style",
            artifact_dir=tmp_path,
            session_id="demo-session",
            deck_id="demo-deck",
        )

    summary = asyncio.run(run())

    assert summary.session_id == "demo-session"
    assert summary.deck_id == "demo-deck"
    assert summary.deck_revision == 1
    assert summary.deck_title == "Board AI Strategy"
    assert summary.theme_name == "executive-consulting"
    assert summary.slide_count == 5
    assert summary.event_count == 11
    assert summary.preview_html_path.exists()
    assert summary.preview_html_path.read_text(encoding="utf-8").startswith("<!doctype html>")
    assert summary.pptx_path.exists()
    assert summary.pptx_path.name == "demo-deck-r1.pptx"
    assert summary.summary_json_path.name == "demo-deck-r1-summary.json"
    assert summary.summary_markdown_path.name == "demo-deck-r1-summary.md"
    assert summary.summary_markdown_path.exists()
    assert "# PPT Agent Studio Demo Summary" in summary.summary_markdown_path.read_text(encoding="utf-8")
    assert json.loads(summary.summary_json_path.read_text(encoding="utf-8")) == {
        "session_id": "demo-session",
        "deck_id": "demo-deck",
        "deck_revision": 1,
        "deck_title": "Board AI Strategy",
        "prompt": "Make a 5 slide board AI strategy deck in McKinsey style",
        "follow_up": "",
        "theme_name": "executive-consulting",
        "slide_count": 5,
        "event_count": 11,
        "event_types": [
            "user.message",
            "plan.updated",
            "tool.completed",
            "plan.updated",
            "tool.completed",
            "deck.updated",
            "tool.completed",
            "preview.ready",
            "tool.completed",
            "pptx.ready",
            "plan.updated",
        ],
        "preview_html_path": str(summary.preview_html_path),
        "pptx_path": str(summary.pptx_path),
        "summary_json_path": str(summary.summary_json_path),
        "summary_markdown_path": str(summary.summary_markdown_path),
    }
    assert "Title: Board AI Strategy" in format_summary(summary)
    assert "Theme: executive-consulting" in format_summary(summary)
    assert "Slides: 5" in format_summary(summary)


def test_run_demo_can_apply_follow_up_turn(tmp_path):
    follow_up = "Create an executive summary slide at the beginning"

    async def run():
        return await run_demo(
            prompt="Make a 5 slide board AI strategy deck in McKinsey style",
            follow_up=follow_up,
            artifact_dir=tmp_path,
            session_id="demo-session",
            deck_id="demo-deck",
        )

    summary = asyncio.run(run())

    assert summary.deck_revision == 2
    assert summary.follow_up == follow_up
    assert summary.slide_count == 6
    assert summary.event_count == 20
    assert summary.preview_html_path.name == "demo-deck-r2.html"
    preview_html = summary.preview_html_path.read_text(encoding="utf-8")
    assert "Executive Summary" in preview_html
    assert "At The Beginning" not in preview_html
    assert summary.pptx_path.name == "demo-deck-r2.pptx"
    assert summary.summary_json_path.name == "demo-deck-r2-summary.json"
    assert summary.summary_markdown_path.name == "demo-deck-r2-summary.md"
    summary_markdown = summary.summary_markdown_path.read_text(encoding="utf-8")
    assert "Follow-up: Create an executive summary slide at the beginning" in summary_markdown
    assert "Event flow: user.message -> plan.updated" in summary_markdown
    assert "pptx.ready -> plan.updated" in summary_markdown
    assert "Preview HTML:" in summary_markdown
    assert "Editable PPTX:" in summary_markdown
    assert f"Follow-up: {follow_up}" in format_summary(summary)
