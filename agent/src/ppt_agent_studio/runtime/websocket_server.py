from __future__ import annotations

import argparse
import asyncio
import json
import os
from collections.abc import AsyncIterator, Iterable
from pathlib import Path
from typing import Any

from ppt_agent_studio.llm.config import OpenAICompatibleConfig
from ppt_agent_studio.planning.outline import FallbackOutlinePlanner, LLMOutlinePlanner, OutlinePlanner
from ppt_agent_studio.protocol.events import AgentEvent
from ppt_agent_studio.runtime.session import AgentSession


_AGENT_SESSIONS: dict[tuple[str, str], AgentSession] = {}


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


def _artifact_summary() -> dict[str, str]:
    return {
        "directory": str(Path(os.getenv("PPT_AGENT_ARTIFACTS_DIR", "artifacts/decks"))),
    }


def _env_file_summary() -> dict[str, object]:
    path = Path(os.getenv("PPT_AGENT_ENV_FILE", ".env.local")).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    resolved = path.resolve()
    return {
        "path": str(resolved),
        "exists": resolved.exists(),
    }


def _requested_planner_mode() -> str:
    return os.getenv("PPT_AGENT_PLANNER", "fallback").strip().lower() or "fallback"


def _active_planner_mode(config: OpenAICompatibleConfig) -> str:
    return "llm" if _requested_planner_mode() == "llm" and config.has_api_key else "fallback"


def _agent_error_message(error: Exception) -> str:
    return f"Agent turn failed: {type(error).__name__}"


async def handle_client_message(raw_message: str) -> list[str]:
    return [response async for response in iter_client_responses(raw_message)]


async def iter_client_responses(raw_message: str) -> AsyncIterator[str]:
    try:
        message = json.loads(raw_message)
    except json.JSONDecodeError:
        yield _error_json("Invalid JSON")
        return
    if not isinstance(message, dict):
        yield _error_json("Message must be a JSON object")
        return

    message_type = str(message.get("type") or "").strip()
    session_id = str(message.get("session_id") or "session")

    if message_type == "session.reset":
        deck_id = str(message.get("deck_id") or "deck")
        event = AgentEvent(
            seq=1,
            session_id=session_id,
            type="session.reset",
            payload={
                "deck_id": deck_id,
                "cleared": _reset_agent_session(session_id, deck_id),
            },
        )
        yield _event_json(event)
        return

    if message_type == "runtime.config":
        config = OpenAICompatibleConfig.from_env()
        event = AgentEvent(
            seq=1,
            session_id=session_id,
            type="runtime.config",
            payload={
                "llm": config.safe_summary(),
                "planner": _planner_summary(config),
                "artifacts": _artifact_summary(),
                "env_file": _env_file_summary(),
            },
        )
        yield _event_json(event)
        return

    if message_type != "user.message":
        yield _error_json(f"Unsupported message type: {message_type or '<empty>'}")
        return

    payload = message.get("payload") if isinstance(message.get("payload"), dict) else {}
    text = str(payload.get("text") or "")
    deck_id = str(message.get("deck_id") or "deck")
    session = _build_agent_session(session_id=session_id, deck_id=deck_id)

    response_count = 0
    try:
        async for event in session.submit_user_message(text):
            response_count += 1
            yield _event_json(event)
    except Exception as error:
        yield _error_json(_agent_error_message(error), seq=response_count + 1, session_id=session_id)


def _build_agent_session(session_id: str, deck_id: str) -> AgentSession:
    key = (session_id, deck_id)
    session = _AGENT_SESSIONS.get(key)
    if session is None:
        session = AgentSession(session_id=session_id, deck_id=deck_id, outline_planner=_build_outline_planner())
        _AGENT_SESSIONS[key] = session
    return session


def _reset_agent_session(session_id: str, deck_id: str) -> bool:
    return _AGENT_SESSIONS.pop((session_id, deck_id), None) is not None


def _clear_agent_sessions() -> None:
    _AGENT_SESSIONS.clear()


async def websocket_handler(websocket: Any) -> None:
    async for raw_message in websocket:
        async for response in iter_client_responses(str(raw_message)):
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
