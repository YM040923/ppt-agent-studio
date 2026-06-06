import asyncio
import json

from ppt_agent_studio.planning.outline import FallbackOutlinePlanner, LLMOutlinePlanner
from ppt_agent_studio.runtime.websocket_server import _build_outline_planner, handle_client_message


class FailingOutlinePlanner:
    async def create_outline(self, prompt: str):
        raise RuntimeError("secret-value from provider")


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
        "pptx.ready",
        "plan.updated",
        "preview.ready",
    ]
    assert payloads[-1]["deck_revision"] == 1
    assert payloads[-1]["payload"]["html"].startswith("<!doctype html>")
    assert payloads[-2]["payload"]["plan"]["status"] == "completed"
    assert payloads[-3]["payload"]["path"].endswith("deck_001-r1.pptx")


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
