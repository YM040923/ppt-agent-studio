import asyncio

from pptx import Presentation

from ppt_agent_studio.tools.deck_tools import build_default_registry


def test_pptx_export_tool_writes_editable_deck(tmp_path):
    registry = build_default_registry()
    deck = {
        "deck_id": "deck_001",
        "title": "AI Strategy",
        "revision": 1,
        "slides": [
            {
                "slide_id": "s1",
                "title": "AI Strategy",
                "layout": "cover",
                "blocks": [{"type": "subtitle", "text": "Board briefing"}],
            },
            {
                "slide_id": "s2",
                "title": "Priorities",
                "layout": "content",
                "blocks": [
                    {"type": "bullet", "text": "Focus the operating model."},
                    {"type": "point", "label": "Sequence", "body": "Ship in measurable waves."},
                ],
            },
        ],
    }
    output_path = tmp_path / "ai-strategy.pptx"

    async def run():
        return await registry.run("pptx.export", {"deck": deck, "output_path": str(output_path)})

    result = asyncio.run(run())
    presentation = Presentation(str(output_path))
    text = "\n".join(
        shape.text
        for slide in presentation.slides
        for shape in slide.shapes
        if hasattr(shape, "text")
    )

    assert result.payload["path"] == str(output_path)
    assert result.payload["slide_count"] == 2
    assert len(presentation.slides) == 2
    assert "AI Strategy" in text
    assert "Board briefing" in text
    assert "Focus the operating model." in text
    assert "Sequence" in text
    assert "Ship in measurable waves." in text
