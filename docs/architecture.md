# Architecture

PPT Agent Studio is a two-process desktop application.

The OpenManus adaptation notes live in [`openmanus-reference.md`](openmanus-reference.md). They define what this project borrows from OpenManus and what stays presentation-specific.

```text
WinUI 3 Desktop App
  - Chat workspace
  - WebView2 preview pane
  - Agent session client

Python Agent Runtime
  - OpenAI-compatible LLM provider
  - Planning and tool-calling loop
  - DeckSpec state store
  - HTML preview renderer
  - PPTX exporter
```

## Runtime Contract

The desktop app and Python runtime communicate through ordered Agent events. Every event carries a `seq`, `session_id`, `type`, and `payload`. Deck-related events also carry `deck_id` and `deck_revision`, so the UI can ignore stale preview updates.

The deterministic MVP session emits this turn sequence:

```text
user.message
plan.updated
deck.updated
preview.ready
pptx.ready
plan.updated
```

This sequence is intentionally small. It proves state ordering, live preview synchronization, editable artifact creation, and completed-plan reporting before adding richer tool execution and cancellation.

`plan.updated` carries both the raw outline and a deck-specific `DeckPlan`. The outline preserves the planner result for debugging, while `DeckPlan` gives the desktop app future-ready step IDs, titles, statuses, and slide counts for progress UI.

The runtime WebSocket server listens on `127.0.0.1:8765` by default. The desktop client sends:

```json
{
  "type": "user.message",
  "session_id": "desktop-session",
  "deck_id": "desktop-deck",
  "payload": { "text": "Make a board AI strategy deck" }
}
```

The server streams one JSON event per WebSocket message. The desktop client closes the turn after receiving `error` or a final `plan.updated` event whose plan status is `completed`.

During development the WinUI app starts the sidecar automatically if `127.0.0.1:8765` is not already listening. The locator walks up from the app base directory until it finds `agent/src`, and `PPT_AGENT_RUNTIME_ROOT` can override the repository root. The Python executable defaults to `python`; set `PPT_AGENT_PYTHON` to use a specific interpreter. PPTX artifacts are written to `artifacts/decks` by default; set `PPT_AGENT_ARTIFACTS_DIR` to use another directory.

The desktop app or a test client can ask for a redacted runtime configuration summary:

```json
{ "type": "runtime.config", "session_id": "desktop-session" }
```

The response is a single `runtime.config` event. It includes `base_url`, `model`, `has_api_key`, planner `requested`/`active` modes, and the PPTX artifact directory, but never returns the API key value.

The WinUI startup flow calls this probe after the Python sidecar is ready and shows a concise status line with the configured model endpoint, key presence, and active planner. The Settings dialog also shows the project-local PPTX artifact directory so users can find exported decks quickly.

Runtime outline planning is selected through `PPT_AGENT_PLANNER`. The default is `fallback`, which keeps local development deterministic and offline. Set `PPT_AGENT_PLANNER=llm` and provide `OPENAI_API_KEY` to use the model-backed `LLMOutlinePlanner`; if the key is missing, the runtime keeps using the fallback planner instead of failing the desktop turn.

## Preview Pane

The WinUI app hosts the live preview with the WebView2 control bundled through Windows App SDK. Do not add a separate `Microsoft.Web.WebView2` package reference unless a future Windows App SDK release explicitly requires it; the first scaffold verified that the extra package can conflict with WinUI runtime startup. The desktop app initializes WebView2 with `EnsureCoreWebView2Async` before calling `NavigateToString`.

## DeckSpec

`DeckSpec` is the source of truth for preview and export. The Agent modifies DeckSpec through tools; the preview renderer and PPTX exporter both consume the same state to avoid drift between what the user sees and what gets exported.

## Tool System

The Python runtime exposes tool definitions through `ppt_agent_studio.tools`. `ToolRegistry` owns executable handlers and the core catalog defines MVP interfaces for deck creation, slide edits, preview rendering, PPTX export, research briefs, and theme application. The registry validates `input_schema.required` before invoking handlers, so future LLM tool calls fail early with a clear tool argument error. The deterministic `AgentSession` already calls the registry for `deck.create_from_outline` and `preview.render_html`, and the default registry can execute slide update/add/remove tools, deterministic research briefs, theme application, and `pptx.export` for editable PowerPoint output. This gives future ReAct/Tool Calling loops a stable execution boundary without changing the desktop event contract.

## OpenAI-Compatible Providers

The runtime uses OpenAI-compatible configuration keys:

- `OPENAI_BASE_URL`
- `OPENAI_API_KEY`
- `OPENAI_MODEL`
- `PPT_AGENT_PLANNER`

This supports official OpenAI endpoints and third-party compatible providers without changing desktop code.

The Python runtime reads these values from process environment variables first, then falls back to `.env.local` in the repository root. Set `PPT_AGENT_ENV_FILE` to point at a different local env file when needed.

`OpenAICompatibleChatClient` posts to `{OPENAI_BASE_URL}/chat/completions` with the configured model and bearer token. It accepts an injected `httpx.AsyncClient`, so runtime tests can use `httpx.MockTransport` and avoid real network calls or secret exposure. The `LLMOutlinePlanner` uses this client plus the core system prompt to request a JSON DeckSpec outline, while `FallbackOutlinePlanner` remains the default for offline MVP runs.

The core system prompt is stored in `ppt_agent_studio.prompts`. It scopes the Agent to presentation work, requires DeckSpec-backed revisions, ties deck mutations to `preview.ready` and `pptx.ready`, and forbids revealing API keys or hidden configuration.
