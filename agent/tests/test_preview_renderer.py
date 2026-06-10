from ppt_agent_studio.deck.spec import DeckSpec, SlideSpec, deck_from_outline
from ppt_agent_studio.preview.html_renderer import render_preview_document, render_preview_html


def test_preview_html_escapes_text_and_renders_all_slides():
    deck = DeckSpec(
        deck_id="deck_003",
        title="Risk < Review",
        revision=2,
        slides=[
            SlideSpec(
                slide_id="s1",
                title="Risk < Review",
                layout="cover",
                blocks=[{"type": "subtitle", "text": "Q2 & Q3"}],
                speaker_notes="Open with the risk trade-off, not the appendix.",
            ),
            SlideSpec(
                slide_id="s2",
                title="Actions",
                layout="content",
                blocks=[{"type": "bullet", "text": "Reduce dependency on <single vendor>"}],
            ),
        ],
    )

    html = render_preview_html(deck)

    assert html.count('class="slide') == 2
    assert "Risk &lt; Review" in html
    assert "Q2 &amp; Q3" in html
    assert "\u2022 Reduce dependency on &lt;single vendor&gt;" in html
    assert 'class="speaker-notes"' in html
    assert "Open with the risk trade-off" in html
    assert "<single vendor>" not in html


def test_preview_html_escapes_speaker_notes():
    deck = DeckSpec(
        deck_id="deck_notes",
        title="Notes",
        revision=1,
        slides=[
            SlideSpec(
                slide_id="s1",
                title="Notes",
                layout="content",
                blocks=[],
                speaker_notes="Mention <sensitive> trade-offs & next steps.",
            )
        ],
    )

    html = render_preview_html(deck)

    assert "Mention &lt;sensitive&gt; trade-offs &amp; next steps." in html
    assert "<sensitive>" not in html


def test_preview_html_includes_revision_for_webview_diffing():
    deck = DeckSpec(deck_id="deck_004", title="Ops", revision=9, slides=[])

    html = render_preview_html(deck)

    assert 'data-deck-id="deck_004"' in html
    assert 'data-revision="9"' in html


def test_preview_html_includes_stable_slide_ids_for_sync():
    deck = DeckSpec(
        deck_id="deck_sync",
        title="Sync",
        revision=3,
        slides=[
            SlideSpec(slide_id="s<intro>", title="Intro", layout="cover", blocks=[]),
            SlideSpec(slide_id="s2", title="Next", layout="content", blocks=[]),
        ],
    )

    html = render_preview_html(deck)

    assert 'data-slide-id="s&lt;intro&gt;"' in html
    assert 'data-slide-id="s2"' in html
    assert 'data-slide-index="1"' in html


def test_preview_html_uses_unique_slide_ids_from_model_outline():
    deck = deck_from_outline(
        {
            "deck_title": "Sync",
            "slides": [
                {"slide_id": "intro", "title": "Intro"},
                {"slide_id": "intro", "title": "Decision"},
                {"slide_id": "   ", "title": "Roadmap"},
            ],
        },
        deck_id="deck_outline_sync",
        revision=1,
    )

    html = render_preview_html(deck)

    assert 'data-slide-id="intro"' in html
    assert 'data-slide-id="s2"' in html
    assert 'data-slide-id="s3"' in html
    assert html.count('data-slide-id="intro"') == 1


def test_preview_document_wraps_deck_html_for_webview2():
    deck = DeckSpec(
        deck_id="deck_005",
        title="Ops",
        revision=1,
        slides=[SlideSpec(slide_id="s1", title="Ops", layout="cover", blocks=[])],
        theme={"name": "executive <dark>"},
        metadata={"audience": "Board <committee>", "style": "McKinsey & concise"},
    )

    document = render_preview_document(deck)

    assert document.startswith("<!doctype html>")
    assert "<style>" in document
    assert 'class="deck"' in document
    assert "font-family: Segoe UI" in document
    assert '<meta name="ppt-agent-theme" content="executive &lt;dark&gt;" />' in document
    assert '<meta name="ppt-agent-audience" content="Board &lt;committee&gt;" />' in document
    assert '<meta name="ppt-agent-style" content="McKinsey &amp; concise" />' in document


def test_preview_document_exposes_webview_interaction_api():
    deck = DeckSpec(
        deck_id="deck_controls",
        title="Controls",
        revision=1,
        slides=[
            SlideSpec(slide_id="s1", title="One", layout="cover", blocks=[]),
            SlideSpec(slide_id="s2", title="Two", layout="content", blocks=[]),
        ],
    )

    document = render_preview_document(deck)

    assert "window.pptAgentPreview" in document
    assert "slideCount" in document
    assert "showSlide(index)" in document
    assert "showSlideById(slideId)" in document
    assert "slide.dataset.slideId" in document
    assert "setZoom(zoom)" in document
    assert "document.querySelectorAll('.slide')" in document


def test_preview_document_applies_safe_theme_color_tokens():
    deck = DeckSpec(
        deck_id="deck_theme",
        title="Ops",
        revision=2,
        theme={
            "background": "#111827",
            "slide_background": "#F8FAFC",
            "text": "#0F172A",
            "accent": "#2563EB",
            "unsafe": "red;body{display:none}",
        },
        slides=[SlideSpec(slide_id="s1", title="Ops", layout="cover", blocks=[])],
    )

    document = render_preview_document(deck)

    assert "--preview-background: #111827;" in document
    assert "--slide-background: #F8FAFC;" in document
    assert "--slide-text: #0F172A;" in document
    assert "--slide-accent: #2563EB;" in document
    assert "display:none" not in document
