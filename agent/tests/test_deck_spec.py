from ppt_agent_studio.deck.spec import DeckSpec, SlideSpec, deck_from_outline


def test_deck_from_outline_preserves_slide_intent_and_revision():
    outline = {
        "deck_title": "Board AI Strategy",
        "slides": [
            {
                "title": "Board AI Strategy",
                "subtitle": "2026 operating model",
                "prototype_hint": "cover",
            },
            {
                "title": "Three bets",
                "points": [
                    {"label": "Efficiency", "body": "Automate recurring analysis work."},
                    {"label": "Growth", "body": "Create AI-native customer workflows."},
                ],
                "prototype_hint": "content",
            },
        ],
    }

    deck = deck_from_outline(outline, deck_id="deck_001", revision=3)

    assert deck.deck_id == "deck_001"
    assert deck.revision == 3
    assert deck.title == "Board AI Strategy"
    assert deck.slides[0].layout == "cover"
    assert deck.slides[1].blocks[0]["type"] == "point"
    assert deck.slides[1].blocks[0]["label"] == "Efficiency"


def test_slide_spec_rejects_empty_title():
    try:
        SlideSpec(slide_id="s1", title="   ", layout="content", blocks=[])
    except ValueError as exc:
        assert "title" in str(exc)
    else:
        raise AssertionError("SlideSpec accepted an empty title")


def test_deck_to_dict_is_json_ready():
    deck = DeckSpec(
        deck_id="deck_002",
        title="Market Review",
        revision=1,
        slides=[
            SlideSpec(
                slide_id="s1",
                title="Market Review",
                layout="cover",
                blocks=[{"type": "subtitle", "text": "Executive readout"}],
            )
        ],
    )

    payload = deck.to_dict()

    assert payload["deck_id"] == "deck_002"
    assert payload["slides"][0]["slide_id"] == "s1"
    assert payload["slides"][0]["blocks"][0]["text"] == "Executive readout"
