from __future__ import annotations

import argparse
import asyncio
import json
import os
from collections.abc import Iterable
from typing import Any

from ppt_agent_studio.llm.config import OpenAICompatibleConfig
from ppt_agent_studio.planning.outline import FallbackOutlinePlanner, LLMOutlinePlanner, OutlinePlanner
from ppt_agent_studio.protocol.events import AgentEvent
from ppt_agent_studio.runtime.session import AgentSession


def _event_json(event: AgentEvent) -> str:
    return json.dumps(event.to_dict(), ensure_ascii=False)


def _error_json(message: str, seq: int = 1, session_id: str = "session") -> str:
    event = AgentEvent(seq=seq, session_id=session_id, type="error", payload={"message": message})
    return _event_json(event)


def _build_outline_planner() -> OutlinePlanner:
    config = OpenAICompatibleConfig.from_env()
    if _active_planner_mode(config) == "llm":
        return LLMOutlinePlanner()
    return FallbackOutlinePlanner()


def _planner_summary(config: OpenAICompatibleConfig) -> dict[str, str]:
    return {
        "requested": _requested_planner_mode(),
        "active": _active_planner_mode(config),
    }


def _requested_planner_mode() -> str:
    return os.getenv("PPT_AGENT_PLANNER", "fallback").strip().lower() or "fallback"


def _active_planner_mode(config: OpenAICompatibleConfig) -> str:
    return "llm" if _requested_planner_mode() == "llm" and config.has_api_key else "fallback"


def _agent_error_message(error: Exception) -> str:
    return f"Agent turn failed: {type(error).__name__}"


async def handle_client_message(raw_message: str) -> list[str]:
    try:
        message = json.loads(raw_message)
    except json.JSONDecodeError:
        return [_error_json("Invalid JSON")]
    if not isinstance(message, dict):
        return [_error_json("Message must be a JSON object")]

    message_type = str(message.get("type") or "").strip()
    session_id = str(message.get("session_id") or "session")

    if message_type == "runtime.config":
        config = OpenAICompatibleConfig.from_env()
        event = AgentEvent(
            seq=1,
            session_id=session_id,
            type="runtime.config",
            payload={"llm": config.safe_summary(), "planner": _planner_summary(config)},
        )
        return [_event_json(event)]

    if message_type != "user.message":
        return [_error_json(f"Unsupported message type: {message_type or '<empty>'}")]

    payload = message.get("payload") if isinstance(message.get("payload"), dict) else {}
    text = str(payload.get("text") or "")
    deck_id = str(message.get("deck_id") or "deck")
    session = AgentSession(session_id=session_id, deck_id=deck_id, outline_planner=_build_outline_planner())

    out: list[str] = []
    try:
        async for event in session.submit_user_message(text):
            out.append(_event_json(event))
    except Exception as error:
        out.append(_error_json(_agent_error_message(error), seq=len(out) + 1, session_id=session_id))
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
