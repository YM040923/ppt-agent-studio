import asyncio
import json

import pytest

from ppt_agent_studio.planning.outline import FallbackOutlinePlanner, LLMOutlinePlanner
from ppt_agent_studio.protocol.events import AgentEvent
from ppt_agent_studio.runtime.websocket_server import _clear_agent_sessions
from ppt_agent_studio.runtime.websocket_server import _build_outline_planner, handle_client_message
from ppt_agent_studio.runtime.websocket_server import iter_client_responses


@pytest.fixture(autouse=True)
def clear_agent_session_cache():
    _clear_agent_sessions()
    yield
    _clear_agent_sessions()


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
        "tool.completed",
        "plan.updated",
        "tool.completed",
        "deck.updated",
        "tool.completed",
        "preview.ready",
        "tool.completed",
        "pptx.ready",
        "plan.updated",
    ]
    assert payloads[2]["payload"]["tool_name"] == "research.collect_brief"
    assert payloads[3]["payload"]["research_brief"]["topic"] == "Board AI Strategy"
    assert payloads[4]["payload"]["tool_name"] == "deck.create_from_outline"
    assert payloads[5]["deck_revision"] == 1
    assert payloads[6]["payload"]["tool_name"] == "preview.render_html"
    assert payloads[7]["payload"]["deck_title"] == "Board AI Strategy"
    assert payloads[7]["payload"]["slide_count"] == 3
    assert payloads[7]["payload"]["html"].startswith("<!doctype html>")
    assert payloads[8]["payload"]["tool_name"] == "pptx.export"
    assert payloads[9]["payload"]["path"].endswith("deck_001-r1.pptx")
    assert payloads[10]["payload"]["plan"]["status"] == "completed"


def test_handle_user_message_reuses_session_state_for_same_deck(monkeypatch, tmp_path):
    monkeypatch.setenv("PPT_AGENT_ARTIFACTS_DIR", str(tmp_path))

    async def run_turn(text: str):
        messages = await handle_client_message(
            json.dumps(
                {
                    "type": "user.message",
                    "session_id": "session_stateful",
                    "deck_id": "deck_stateful",
                    "payload": {"text": text},
                }
            )
        )
        return [json.loads(item) for item in messages]

    first_turn = asyncio.run(run_turn("Make a 2 page AI strategy deck"))
    second_turn = asyncio.run(run_turn("Revise it for the board"))

    assert first_turn[0]["seq"] == 1
    assert first_turn[5]["deck_revision"] == 1
    assert first_turn[9]["payload"]["path"].endswith("deck_stateful-r1.pptx")
    assert second_turn[0]["seq"] == 12
    assert second_turn[5]["deck_revision"] == 2
    assert second_turn[9]["payload"]["path"].endswith("deck_stateful-r2.pptx")


def test_handle_user_message_follow_up_adds_slide_to_cached_deck(monkeypatch, tmp_path):
    monkeypatch.setenv("PPT_AGENT_ARTIFACTS_DIR", str(tmp_path))

    async def run_turn(text: str):
        messages = await handle_client_message(
            json.dumps(
                {
                    "type": "user.message",
                    "session_id": "session_followup",
                    "deck_id": "deck_followup",
                    "payload": {"text": text},
                }
            )
        )
        return [json.loads(item) for item in messages]

    first_turn = asyncio.run(run_turn("Make a 2 page AI strategy deck"))
    second_turn = asyncio.run(run_turn("Add a risk mitigation slide"))

    assert first_turn[5]["payload"]["deck"]["revision"] == 1
    assert len(first_turn[5]["payload"]["deck"]["slides"]) == 2
    assert [event["type"] for event in second_turn] == [
        "user.message",
        "plan.updated",
        "tool.completed",
        "deck.updated",
        "tool.completed",
        "preview.ready",
        "tool.completed",
        "pptx.ready",
        "plan.updated",
    ]
    assert second_turn[2]["payload"]["tool_name"] == "deck.add_slide"
    assert second_turn[2]["payload"]["summary"] == "Added slide: Risk Mitigation."
    assert second_turn[3]["deck_revision"] == 2
    assert second_turn[3]["payload"]["deck"]["revision"] == 2
    assert len(second_turn[3]["payload"]["deck"]["slides"]) == 3
    assert second_turn[5]["payload"]["slide_count"] == 3
    assert second_turn[7]["payload"]["path"].endswith("deck_followup-r2.pptx")


def test_handle_user_message_follow_up_updates_and_removes_cached_deck(monkeypatch, tmp_path):
    monkeypatch.setenv("PPT_AGENT_ARTIFACTS_DIR", str(tmp_path))

    async def run_turn(text: str):
        messages = await handle_client_message(
            json.dumps(
                {
                    "type": "user.message",
                    "session_id": "session_followup_edit",
                    "deck_id": "deck_followup_edit",
                    "payload": {"text": text},
                }
            )
        )
        return [json.loads(item) for item in messages]

    first_turn = asyncio.run(run_turn("Make a 3 page AI strategy deck"))
    second_turn = asyncio.run(run_turn("Update the first slide title to Executive AI Roadmap"))
    third_turn = asyncio.run(run_turn("Remove the last slide"))

    assert len(first_turn[5]["payload"]["deck"]["slides"]) == 3
    assert second_turn[2]["payload"]["tool_name"] == "deck.update_slide"
    assert second_turn[2]["payload"]["summary"] == "Renamed first slide: Executive AI Roadmap."
    assert second_turn[3]["deck_revision"] == 2
    assert second_turn[3]["payload"]["deck"]["slides"][0]["title"] == "Executive AI Roadmap"
    assert second_turn[7]["payload"]["path"].endswith("deck_followup_edit-r2.pptx")

    assert third_turn[2]["payload"]["tool_name"] == "deck.remove_slide"
    assert third_turn[2]["payload"]["summary"] == "Removed last slide."
    assert third_turn[3]["deck_revision"] == 3
    assert len(third_turn[3]["payload"]["deck"]["slides"]) == 2
    assert third_turn[5]["payload"]["slide_count"] == 2
    assert third_turn[7]["payload"]["path"].endswith("deck_followup_edit-r3.pptx")


def test_handle_user_message_follow_up_applies_dark_theme(monkeypatch, tmp_path):
    monkeypatch.setenv("PPT_AGENT_ARTIFACTS_DIR", str(tmp_path))

    async def run_turn(text: str):
        messages = await handle_client_message(
            json.dumps(
                {
                    "type": "user.message",
                    "session_id": "session_followup_theme",
                    "deck_id": "deck_followup_theme",
                    "payload": {"text": text},
                }
            )
        )
        return [json.loads(item) for item in messages]

    first_turn = asyncio.run(run_turn("Make a 3 page AI strategy deck"))
    second_turn = asyncio.run(run_turn("Apply a dark executive theme"))

    assert first_turn[5]["payload"]["deck"]["revision"] == 1
    assert second_turn[2]["payload"]["tool_name"] == "design.apply_theme"
    assert second_turn[2]["payload"]["summary"] == "Applied theme: executive-dark."
    assert second_turn[3]["deck_revision"] == 2
    assert second_turn[3]["payload"]["deck"]["theme"]["name"] == "executive-dark"
    assert second_turn[5]["payload"]["theme_name"] == "executive-dark"
    assert "--slide-background: #111827;" in second_turn[5]["payload"]["html"]
    assert second_turn[7]["payload"]["path"].endswith("deck_followup_theme-r2.pptx")
    assert second_turn[7]["payload"]["deck_title"] == "AI Strategy"
    assert second_turn[7]["payload"]["theme_name"] == "executive-dark"


def test_handle_session_reset_clears_cached_deck(monkeypatch, tmp_path):
    monkeypatch.setenv("PPT_AGENT_ARTIFACTS_DIR", str(tmp_path))

    async def run_turn(text: str):
        messages = await handle_client_message(
            json.dumps(
                {
                    "type": "user.message",
                    "session_id": "session_reset",
                    "deck_id": "deck_reset",
                    "payload": {"text": text},
                }
            )
        )
        return [json.loads(item) for item in messages]

    async def reset_deck():
        messages = await handle_client_message(
            json.dumps(
                {
                    "type": "session.reset",
                    "session_id": "session_reset",
                    "deck_id": "deck_reset",
                }
            )
        )
        return [json.loads(item) for item in messages]

    first_turn = asyncio.run(run_turn("Make a 2 page AI strategy deck"))
    reset_events = asyncio.run(reset_deck())
    second_turn = asyncio.run(run_turn("Make a fresh 2 page AI strategy deck"))

    assert first_turn[0]["seq"] == 1
    assert first_turn[5]["deck_revision"] == 1
    assert reset_events == [
        {
            "seq": 1,
            "session_id": "session_reset",
            "type": "session.reset",
            "payload": {
                "deck_id": "deck_reset",
                "cleared": True,
            },
        }
    ]
    assert second_turn[0]["seq"] == 1
    assert second_turn[5]["deck_revision"] == 1
    assert second_turn[9]["payload"]["path"].endswith("deck_reset-r1.pptx")


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


def test_handle_runtime_config_returns_redacted_model_summary(monkeypatch, tmp_path):
    env_file = tmp_path / ".env.local"
    env_file.write_text("OPENAI_API_KEY=secret-value", encoding="utf-8")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://provider.example/v1/")
    monkeypatch.setenv("OPENAI_API_KEY", "secret-value")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-compatible-model")
    monkeypatch.setenv("PPT_AGENT_PLANNER", "llm")
    monkeypatch.setenv("PPT_AGENT_ARTIFACTS_DIR", str(tmp_path / "decks"))
    monkeypatch.setenv("PPT_AGENT_ENV_FILE", str(env_file))

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
            "has_extra_headers": False,
            "endpoint_kind": "cloud",
            "requires_api_key": True,
            "source": {
                "base_url": "environment",
                "api_key": "environment",
                "model": "environment",
                "extra_headers": "default",
            },
        },
        "runtime": {
            "name": "ppt-agent-studio",
            "version": "0.1.0",
        },
        "planner": {
            "requested": "llm",
            "active": "llm",
        },
        "artifacts": {
            "directory": str(tmp_path / "decks"),
        },
        "env_file": {
            "path": str(env_file),
            "exists": True,
        },
    }
    assert "secret-value" not in messages[0]


def test_handle_runtime_config_reports_extra_headers_without_values(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_BASE_URL", "https://provider.example/v1/")
    monkeypatch.setenv("OPENAI_API_KEY", "secret-value")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-compatible-model")
    monkeypatch.setenv("OPENAI_EXTRA_HEADERS", '{"X-Provider":"secret-tenant"}')
    monkeypatch.setenv("PPT_AGENT_ENV_FILE", str(tmp_path / "missing.env"))

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

    assert payload["payload"]["llm"]["has_extra_headers"] is True
    assert "secret-tenant" not in messages[0]
    assert "X-Provider" not in messages[0]


def test_handle_runtime_config_reports_invalid_extra_headers_without_values(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_EXTRA_HEADERS", "secret-tenant")
    monkeypatch.setenv("PPT_AGENT_ENV_FILE", str(tmp_path / "missing.env"))

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

    assert payload["type"] == "error"
    assert payload["session_id"] == "session_001"
    assert payload["payload"]["message"] == "Invalid runtime configuration: OPENAI_EXTRA_HEADERS must be a JSON object"
    assert "secret-tenant" not in messages[0]


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


def test_handle_runtime_config_uses_llm_for_local_endpoint_without_key(monkeypatch, tmp_path):
    monkeypatch.setenv("PPT_AGENT_PLANNER", "llm")
    monkeypatch.setenv("OPENAI_BASE_URL", "http://127.0.0.1:11434/v1")
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

    assert payload["payload"]["llm"]["endpoint_kind"] == "local"
    assert payload["payload"]["llm"]["has_api_key"] is False
    assert payload["payload"]["llm"]["requires_api_key"] is False
    assert payload["payload"]["planner"] == {
        "requested": "llm",
        "active": "llm",
    }


def test_handle_runtime_config_treats_placeholder_key_as_missing(monkeypatch, tmp_path):
    monkeypatch.setenv("PPT_AGENT_PLANNER", "llm")
    monkeypatch.setenv("OPENAI_API_KEY", "replace-with-your-api-key")
    monkeypatch.setenv("PPT_AGENT_ENV_FILE", str(tmp_path / "missing.env"))

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

    assert payload["payload"]["llm"]["has_api_key"] is False
    assert payload["payload"]["planner"] == {
        "requested": "llm",
        "active": "fallback",
    }


def test_handle_runtime_tools_returns_core_tool_catalog():
    async def run():
        return await handle_client_message(
            json.dumps(
                {
                    "type": "runtime.tools",
                    "session_id": "session_001",
                }
            )
        )

    messages = asyncio.run(run())
    payload = json.loads(messages[0])
    tools = payload["payload"]["tools"]
    names = {tool["name"] for tool in tools}

    assert len(messages) == 1
    assert payload["type"] == "runtime.tools"
    assert payload["session_id"] == "session_001"
    assert "deck.create_from_outline" in names
    assert "pptx.export" in names
    assert all(tool["input_schema"]["type"] == "object" for tool in tools)


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


def test_build_outline_planner_uses_llm_for_local_endpoint_without_key(monkeypatch, tmp_path):
    monkeypatch.setenv("PPT_AGENT_PLANNER", "llm")
    monkeypatch.setenv("OPENAI_BASE_URL", "http://127.0.0.1:11434/v1")
    monkeypatch.setenv("PPT_AGENT_ENV_FILE", str(tmp_path / "missing.env"))
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    planner = _build_outline_planner()

    assert isinstance(planner, LLMOutlinePlanner)


def test_build_outline_planner_falls_back_when_llm_enabled_without_key(monkeypatch, tmp_path):
    monkeypatch.setenv("PPT_AGENT_PLANNER", "llm")
    monkeypatch.setenv("PPT_AGENT_ENV_FILE", str(tmp_path / "missing.env"))
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    planner = _build_outline_planner()

    assert isinstance(planner, FallbackOutlinePlanner)
