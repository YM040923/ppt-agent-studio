from ppt_agent_studio.deck.spec import DeckSpec, SlideSpec
from ppt_agent_studio.preview.html_renderer import render_preview_html


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
    assert "<single vendor>" not in html


def test_preview_html_includes_revision_for_webview_diffing():
    deck = DeckSpec(deck_id="deck_004", title="Ops", revision=9, slides=[])

    html = render_preview_html(deck)

    assert 'data-deck-id="deck_004"' in html
    assert 'data-revision="9"' in html
