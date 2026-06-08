from ppt_agent_studio.prompts.system import PPT_AGENT_SYSTEM_PROMPT


def test_system_prompt_scopes_agent_to_presentations():
    prompt = PPT_AGENT_SYSTEM_PROMPT

    assert "presentation" in prompt.lower()
    assert "ppt" in prompt.lower()
    assert "not a general-purpose agent" in prompt.lower()
    assert "executive" in prompt.lower()
    assert "strategy" in prompt.lower()


def test_system_prompt_includes_preview_pptx_and_iteration_rules():
    prompt = PPT_AGENT_SYSTEM_PROMPT

    assert "DeckSpec" in prompt
    assert "preview.ready" in prompt
    assert "pptx.ready" in prompt
    assert ".pptx" in prompt
    assert "speaker_notes" in prompt
    assert "iterate" in prompt.lower()
    assert "revision" in prompt.lower()


def test_system_prompt_names_deck_title_and_slide_move_edits():
    prompt = PPT_AGENT_SYSTEM_PROMPT

    assert "deck title edits" in prompt
    assert "slide moves" in prompt
    assert "deck.update_deck" in prompt
    assert "deck.move_slide" in prompt


def test_system_prompt_requires_theme_tokens_for_deckspec():
    prompt = PPT_AGENT_SYSTEM_PROMPT

    assert "theme" in prompt
    assert "background" in prompt
    assert "slide_background" in prompt
    assert "accent" in prompt
    assert "hex" in prompt.lower()


def test_system_prompt_requires_json_outline_output():
    prompt = PPT_AGENT_SYSTEM_PROMPT

    assert "JSON object" in prompt
    assert "deck_title" in prompt
    assert "slides" in prompt
    assert "Do not wrap" in prompt


def test_system_prompt_forbids_secret_exposure():
    prompt = PPT_AGENT_SYSTEM_PROMPT

    assert "API key" in prompt
    assert "never reveal" in prompt.lower()
