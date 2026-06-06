import asyncio

from ppt_agent_studio.runtime.session import AgentSession


def test_agent_session_turn_emits_ordered_preview_events():
    session = AgentSession(session_id="session_001", deck_id="deck_001")

    async def collect():
        return [event async for event in session.submit_user_message("Make a 5 slide board AI strategy deck")]

    events = asyncio.run(collect())

    assert [event.type for event in events] == [
        "user.message",
        "plan.updated",
        "deck.updated",
        "preview.ready",
    ]
    assert [event.seq for event in events] == [1, 2, 3, 4]
    assert events[2].deck_revision == 1
    assert events[3].payload["html"].startswith("<!doctype html>")
    assert "board AI strategy" in events[3].payload["html"]


def test_agent_session_ignores_empty_user_message():
    session = AgentSession(session_id="session_002", deck_id="deck_002")

    async def collect():
        return [event async for event in session.submit_user_message("   ")]

    events = asyncio.run(collect())

    assert len(events) == 1
    assert events[0].type == "error"
    assert events[0].payload["message"] == "User message is required"
