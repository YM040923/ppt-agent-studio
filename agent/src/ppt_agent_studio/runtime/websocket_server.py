from __future__ import annotations

import argparse
import asyncio
import json
from collections.abc import Iterable
from typing import Any

from ppt_agent_studio.protocol.events import AgentEvent
from ppt_agent_studio.runtime.session import AgentSession


def _event_json(event: AgentEvent) -> str:
    return json.dumps(event.to_dict(), ensure_ascii=False)


def _error_json(message: str, seq: int = 1, session_id: str = "session") -> str:
    event = AgentEvent(seq=seq, session_id=session_id, type="error", payload={"message": message})
    return _event_json(event)


async def handle_client_message(raw_message: str) -> list[str]:
    try:
        message = json.loads(raw_message)
    except json.JSONDecodeError:
        return [_error_json("Invalid JSON")]
    if not isinstance(message, dict):
        return [_error_json("Message must be a JSON object")]

    message_type = str(message.get("type") or "").strip()
    if message_type != "user.message":
        return [_error_json(f"Unsupported message type: {message_type or '<empty>'}")]

    payload = message.get("payload") if isinstance(message.get("payload"), dict) else {}
    text = str(payload.get("text") or "")
    session_id = str(message.get("session_id") or "session")
    deck_id = str(message.get("deck_id") or "deck")
    session = AgentSession(session_id=session_id, deck_id=deck_id)

    out: list[str] = []
    async for event in session.submit_user_message(text):
        out.append(_event_json(event))
    return out


async def websocket_handler(websocket: Any) -> None:
    async for raw_message in websocket:
        for response in await handle_client_message(str(raw_message)):
            await websocket.send(response)


async def serve(host: str = "127.0.0.1", port: int = 8765) -> None:
    import websockets

    async with websockets.serve(websocket_handler, host, port):
        await asyncio.Future()


def main(argv: Iterable[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run the PPT Agent Studio runtime WebSocket server.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(list(argv) if argv is not None else None)
    asyncio.run(serve(host=args.host, port=args.port))


if __name__ == "__main__":
    main()
