import asyncio
import json

from ppt_agent_studio.runtime.demo import format_summary, run_demo


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
    assert summary.slide_count == 5
    assert summary.event_count == 11
    assert summary.preview_html_path.exists()
    assert summary.preview_html_path.read_text(encoding="utf-8").startswith("<!doctype html>")
    assert summary.pptx_path.exists()
    assert summary.pptx_path.name == "demo-deck-r1.pptx"
    assert summary.summary_json_path.name == "demo-deck-r1-summary.json"
    assert json.loads(summary.summary_json_path.read_text(encoding="utf-8")) == {
        "session_id": "demo-session",
        "deck_id": "demo-deck",
        "deck_revision": 1,
        "prompt": "Make a 5 slide board AI strategy deck in McKinsey style",
        "follow_up": "",
        "slide_count": 5,
        "event_count": 11,
        "preview_html_path": str(summary.preview_html_path),
        "pptx_path": str(summary.pptx_path),
    }
    assert "Slides: 5" in format_summary(summary)


def test_run_demo_can_apply_follow_up_turn(tmp_path):
    async def run():
        return await run_demo(
            prompt="Make a 5 slide board AI strategy deck in McKinsey style",
            follow_up="Add a risk mitigation slide",
            artifact_dir=tmp_path,
            session_id="demo-session",
            deck_id="demo-deck",
        )

    summary = asyncio.run(run())

    assert summary.deck_revision == 2
    assert summary.follow_up == "Add a risk mitigation slide"
    assert summary.slide_count == 6
    assert summary.event_count == 20
    assert summary.preview_html_path.name == "demo-deck-r2.html"
    assert summary.pptx_path.name == "demo-deck-r2.pptx"
    assert summary.summary_json_path.name == "demo-deck-r2-summary.json"
    assert "Follow-up: Add a risk mitigation slide" in format_summary(summary)
