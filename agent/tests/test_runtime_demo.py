import asyncio

from ppt_agent_studio.runtime.demo import run_demo


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
    assert summary.event_count == 11
    assert summary.preview_html_path.exists()
    assert summary.preview_html_path.read_text(encoding="utf-8").startswith("<!doctype html>")
    assert summary.pptx_path.exists()
    assert summary.pptx_path.name == "demo-deck-r1.pptx"
