import asyncio
import json

from ppt_agent_studio.planning.outline import FallbackOutlinePlanner, LLMOutlinePlanner
from ppt_agent_studio.protocol.events import AgentEvent
from ppt_agent_studio.runtime.websocket_server import _build_outline_planner, handle_client_message
from ppt_agent_studio.runtime.websocket_server import iter_client_responses


class FailingOutlinePlanner:
    async def create_outline(self, prompt: str):
        raise RuntimeError("secret-value from provider")


class BlockingSession:
    def __init__(self, release_next_event: asyncio.Event):
        self._release_next_event = release_next_event

    async def submit_user_message(self, message: str):
        yield AgentEvent(
            seq=1,
            session_id="session_001",
            type="user.message",
            payload={"text": message},
        )
        await self._release_next_event.wait()
        yield AgentEvent(
            seq=2,
            session_id="session_001",
            type="plan.updated",
            payload={"plan": {"status": "completed"}},
        )


def test_iter_client_responses_streams_events_without_waiting_for_full_turn(monkeypatch):
    release_next_event = asyncio.Event()
    monkeypatch.setattr(
        "ppt_agent_studio.runtime.websocket_server._build_agent_session",
        lambda session_id, deck_id: BlockingSession(release_next_event),
    )

    async def run():
        stream = iter_client_responses(
            json.dumps(
                {
                    "type": "user.message",
                    "session_id": "session_001",
                    "deck_id": "deck_001",
                    "payload": {"text": "Make a strategy deck"},
                }
            )
        )
        first = await asyncio.wait_for(anext(stream), timeout=0.1)
        second_task = asyncio.create_task(anext(stream))
        await asyncio.sleep(0.01)
        second_waiting_on_release = not second_task.done()
        release_next_event.set()
        second = await asyncio.wait_for(second_task, timeout=0.1)
        return json.loads(first), second_waiting_on_release, json.loads(second)

    first, second_waiting_on_release, second = asyncio.run(run())

    assert first["type"] == "user.message"
    assert second_waiting_on_release is True
    assert second["type"] == "plan.updated"
    assert second["payload"]["plan"]["status"] == "completed"


def test_handle_user_message_returns_json_event_lines(monkeypatch, tmp_path):
    monkeypatch.setenv("PPT_AGENT_ARTIFACTS_DIR", str(tmp_path))

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
        "pptx.ready",
        "plan.updated",
    ]
    assert payloads[3]["deck_revision"] == 1
    assert payloads[3]["payload"]["html"].startswith("<!doctype html>")
    assert payloads[4]["payload"]["path"].endswith("deck_001-r1.pptx")
    assert payloads[5]["payload"]["plan"]["status"] == "completed"


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


def test_handle_user_message_returns_error_when_agent_turn_fails(monkeypatch):
    monkeypatch.setattr(
        "ppt_agent_studio.runtime.websocket_server._build_outline_planner",
        lambda: FailingOutlinePlanner(),
    )

    async def run():
        return await handle_client_message(
            json.dumps(
                {
                    "type": "user.message",
                    "session_id": "session_001",
                    "deck_id": "deck_001",
                    "payload": {"text": "Make a strategy deck"},
                }
            )
        )

    messages = asyncio.run(run())
    payloads = [json.loads(item) for item in messages]

    assert [item["type"] for item in payloads] == ["user.message", "error"]
    assert payloads[1]["seq"] == 2
    assert payloads[1]["session_id"] == "session_001"
    assert payloads[1]["payload"]["message"] == "Agent turn failed: RuntimeError"
    assert "secret-value" not in messages[1]


def test_handle_runtime_config_returns_redacted_model_summary(monkeypatch):
    monkeypatch.setenv("OPENAI_BASE_URL", "https://provider.example/v1/")
    monkeypatch.setenv("OPENAI_API_KEY", "secret-value")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-compatible-model")
    monkeypatch.setenv("PPT_AGENT_PLANNER", "llm")

    async def run():
        return await handle_client_message(
            json.dumps(
                {
                    "type": "runtime.config",
                    "session_id": "session_001",
                }
            )
        )

    messages = asyncio.run(run())
    assert len(messages) == 1
    payload = json.loads(messages[0])

    assert payload["type"] == "runtime.config"
    assert payload["session_id"] == "session_001"
    assert payload["payload"] == {
        "llm": {
            "base_url": "https://provider.example/v1",
            "model": "gpt-compatible-model",
            "has_api_key": True,
        },
        "planner": {
            "requested": "llm",
            "active": "llm",
        }
    }
    assert "secret-value" not in messages[0]


def test_handle_runtime_config_reports_fallback_when_llm_key_is_missing(monkeypatch, tmp_path):
    monkeypatch.setenv("PPT_AGENT_PLANNER", "llm")
    monkeypatch.setenv("PPT_AGENT_ENV_FILE", str(tmp_path / "missing.env"))
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    async def run():
        return await handle_client_message(
            json.dumps(
                {
                    "type": "runtime.config",
                    "session_id": "session_001",
                }
            )
        )

    messages = asyncio.run(run())
    payload = json.loads(messages[0])

    assert payload["payload"]["planner"] == {
        "requested": "llm",
        "active": "fallback",
    }


def test_build_outline_planner_defaults_to_fallback(monkeypatch, tmp_path):
    monkeypatch.delenv("PPT_AGENT_PLANNER", raising=False)
    monkeypatch.setenv("PPT_AGENT_ENV_FILE", str(tmp_path / "missing.env"))
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    planner = _build_outline_planner()

    assert isinstance(planner, FallbackOutlinePlanner)


def test_build_outline_planner_uses_llm_when_enabled_and_key_present(monkeypatch):
    monkeypatch.setenv("PPT_AGENT_PLANNER", "llm")
    monkeypatch.setenv("OPENAI_API_KEY", "secret-value")

    planner = _build_outline_planner()

    assert isinstance(planner, LLMOutlinePlanner)


def test_build_outline_planner_falls_back_when_llm_enabled_without_key(monkeypatch, tmp_path):
    monkeypatch.setenv("PPT_AGENT_PLANNER", "llm")
    monkeypatch.setenv("PPT_AGENT_ENV_FILE", str(tmp_path / "missing.env"))
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    planner = _build_outline_planner()

    assert isinstance(planner, FallbackOutlinePlanner)
