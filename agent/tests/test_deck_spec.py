from ppt_agent_studio.deck.spec import DeckSpec, SlideSpec, deck_from_outline


def test_deck_from_outline_preserves_slide_intent_and_revision():
    outline = {
        "deck_title": "Board AI Strategy",
        "slides": [
            {
                "title": "Board AI Strategy",
                "subtitle": "2026 operating model",
                "prototype_hint": "cover",
                "speaker_notes": "Open by framing the board decision and the expected outcome.",
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
        "metadata": {
            "audience": "executive committee",
            "style": "McKinsey",
        },
    }

    deck = deck_from_outline(outline, deck_id="deck_001", revision=3)

    assert deck.deck_id == "deck_001"
    assert deck.revision == 3
    assert deck.title == "Board AI Strategy"
    assert deck.metadata == {"audience": "executive committee", "style": "McKinsey"}
    assert deck.slides[0].layout == "cover"
    assert deck.slides[0].speaker_notes == "Open by framing the board decision and the expected outcome."
    assert deck.slides[1].blocks[0]["type"] == "point"
    assert deck.slides[1].blocks[0]["label"] == "Efficiency"


def test_deck_from_outline_preserves_theme_tokens():
    outline = {
        "deck_title": "Board AI Strategy",
        "theme": {
            "name": "executive-dark",
            "background": "#111827",
            "slide_background": "#F8FAFC",
            "text": "#0F172A",
            "accent": "#2563EB",
        },
        "slides": [],
    }

    deck = deck_from_outline(outline, deck_id="deck_theme", revision=1)
    payload = deck.to_dict()

    assert deck.theme["name"] == "executive-dark"
    assert payload["theme"]["accent"] == "#2563EB"


def test_deck_from_outline_preserves_metadata_text_aliases():
    outline = {
        "deck_title": "AI Strategy",
        "metadata": {
            "audience": {"text": "CFO leadership"},
            "style": {"value": "investor narrative"},
        },
        "slides": [],
    }

    deck = deck_from_outline(outline, deck_id="deck_metadata_aliases", revision=1)

    assert deck.metadata == {"audience": "CFO leadership", "style": "investor narrative"}


def test_deck_from_outline_preserves_model_content_fields():
    outline = {
        "deck_title": "AI Strategy",
        "slides": [
            {
                "title": "Decision",
                "content": "Approve a phased rollout.",
                "bullets": [
                    {"text": "Start with finance"},
                    {"body": "Measure adoption weekly"},
                ],
                "summary_items": [{"text": "Decision needed"}],
            }
        ],
    }

    deck = deck_from_outline(outline, deck_id="deck_content", revision=1)

    assert deck.slides[0].blocks == [
        {"type": "text", "text": "Approve a phased rollout."},
        {"type": "bullet", "text": "Start with finance"},
        {"type": "bullet", "text": "Measure adoption weekly"},
        {"type": "summary_item", "text": "Decision needed"},
    ]


def test_deck_from_outline_preserves_model_body_content_aliases():
    outline = {
        "deck_title": "AI Strategy",
        "slides": [
            {"title": "Decision", "body": "Approve a phased rollout."},
            {"title": "Message", "key_message": "Adoption risk is manageable."},
        ],
    }

    deck = deck_from_outline(outline, deck_id="deck_content_aliases", revision=1)

    assert deck.slides[0].blocks == [{"type": "text", "text": "Approve a phased rollout."}]
    assert deck.slides[1].blocks == [{"type": "text", "text": "Adoption risk is manageable."}]


def test_deck_from_outline_preserves_model_list_item_text_aliases():
    outline = {
        "deck_title": "AI Strategy",
        "slides": [
            {
                "title": "Agenda",
                "toc_items": [{"title": "Decision context"}],
                "bullets": [
                    {"content": "Start with finance"},
                    {"value": "Measure adoption weekly"},
                ],
                "summary_items": [{"label": "Decision needed"}],
            }
        ],
    }

    deck = deck_from_outline(outline, deck_id="deck_list_aliases", revision=1)

    assert deck.slides[0].blocks == [
        {"type": "toc_item", "text": "Decision context"},
        {"type": "bullet", "text": "Start with finance"},
        {"type": "bullet", "text": "Measure adoption weekly"},
        {"type": "summary_item", "text": "Decision needed"},
    ]


def test_deck_from_outline_preserves_model_point_text_aliases():
    outline = {
        "deck_title": "AI Strategy",
        "slides": [
            {
                "title": "Decision",
                "points": [
                    "Fund the initial rollout.",
                    {"text": "Sequence adoption by function."},
                    {"title": "Impact", "content": "Reduce recurring analysis work."},
                ],
            }
        ],
    }

    deck = deck_from_outline(outline, deck_id="deck_point_aliases", revision=1)

    assert deck.slides[0].blocks == [
        {"type": "point", "label": "", "body": "Fund the initial rollout."},
        {"type": "point", "label": "", "body": "Sequence adoption by function."},
        {"type": "point", "label": "Impact", "body": "Reduce recurring analysis work."},
    ]


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
                speaker_notes="Keep this to 60 seconds.",
            )
        ],
        metadata={"audience": "board", "style": "consulting"},
    )

    payload = deck.to_dict()

    assert payload["deck_id"] == "deck_002"
    assert payload["slides"][0]["slide_id"] == "s1"
    assert payload["slides"][0]["blocks"][0]["text"] == "Executive readout"
    assert payload["slides"][0]["speaker_notes"] == "Keep this to 60 seconds."
    assert payload["metadata"] == {"audience": "board", "style": "consulting"}
