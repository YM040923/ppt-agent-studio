from ppt_agent_studio.deck.spec import DeckSpec, SlideSpec
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


def test_preview_document_wraps_deck_html_for_webview2():
    deck = DeckSpec(
        deck_id="deck_005",
        title="Ops",
        revision=1,
        slides=[SlideSpec(slide_id="s1", title="Ops", layout="cover", blocks=[])],
    )

    document = render_preview_document(deck)

    assert document.startswith("<!doctype html>")
    assert "<style>" in document
    assert 'class="deck"' in document
    assert "font-family: Segoe UI" in document


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
