from ppt_agent_studio.protocol.events import AgentEvent


def test_agent_event_envelope_contains_ordering_and_deck_revision():
    event = AgentEvent(
        seq=7,
        session_id="session_001",
        type="preview.ready",
        deck_id="deck_001",
        deck_revision=4,
        payload={"html": "<section></section>"},
    )

    payload = event.to_dict()

    assert payload["seq"] == 7
    assert payload["type"] == "preview.ready"
    assert payload["deck_revision"] == 4
    assert payload["payload"]["html"].startswith("<section")


def test_agent_event_rejects_negative_sequence():
    try:
        AgentEvent(seq=-1, session_id="s", type="error", payload={})
    except ValueError as exc:
        assert "seq" in str(exc)
    else:
        raise AssertionError("AgentEvent accepted a negative sequence")
