import asyncio
import json

from ppt_agent_studio.runtime.websocket_server import handle_client_message


def test_handle_user_message_returns_json_event_lines():
    async def run():
        return await handle_client_message(
            json.dumps(
                {
                    "type": "user.message",
                    "session_id": "session_001",
                    "deck_id": "deck_001",
                    "payload": {"text": "Make a board AI strategy deck"},
                }
            )
        )

    messages = asyncio.run(run())
    payloads = [json.loads(item) for item in messages]

    assert [item["type"] for item in payloads] == [
        "user.message",
        "plan.updated",
        "deck.updated",
        "preview.ready",
    ]
    assert payloads[-1]["deck_revision"] == 1
    assert payloads[-1]["payload"]["html"].startswith("<!doctype html>")


def test_handle_invalid_json_returns_error_event():
    async def run():
        return await handle_client_message("{")

    messages = asyncio.run(run())
    payload = json.loads(messages[0])

    assert payload["type"] == "error"
    assert payload["payload"]["message"] == "Invalid JSON"


def test_handle_unknown_message_type_returns_error_event():
    async def run():
        return await handle_client_message(json.dumps({"type": "ping"}))

    messages = asyncio.run(run())
    payload = json.loads(messages[0])

    assert payload["type"] == "error"
    assert payload["payload"]["message"] == "Unsupported message type: ping"
