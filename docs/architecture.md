# Architecture

PPT Agent Studio is a two-process desktop application.

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
```

This sequence is intentionally small. It proves state ordering and preview synchronization before adding live model calls, tool execution, and cancellation.

The runtime WebSocket server listens on `127.0.0.1:8765` by default. The desktop client sends:

```json
{
  "type": "user.message",
  "session_id": "desktop-session",
  "deck_id": "desktop-deck",
  "payload": { "text": "Make a board AI strategy deck" }
}
```

The server streams one JSON event per WebSocket message. The desktop client closes the turn after receiving `preview.ready` or `error`.

During development the WinUI app starts the sidecar automatically if `127.0.0.1:8765` is not already listening. The locator walks up from the app base directory until it finds `agent/src`, and `PPT_AGENT_RUNTIME_ROOT` can override the repository root. The Python executable defaults to `python`; set `PPT_AGENT_PYTHON` to use a specific interpreter.

The desktop app or a test client can ask for a redacted runtime configuration summary:

```json
{ "type": "runtime.config", "session_id": "desktop-session" }
```

The response is a single `runtime.config` event. It includes `base_url`, `model`, and `has_api_key`, but never returns the API key value.

## Preview Pane

The WinUI app hosts the live preview with the WebView2 control bundled through Windows App SDK. Do not add a separate `Microsoft.Web.WebView2` package reference unless a future Windows App SDK release explicitly requires it; the first scaffold verified that the extra package can conflict with WinUI runtime startup. The desktop app initializes WebView2 with `EnsureCoreWebView2Async` before calling `NavigateToString`.

## DeckSpec

`DeckSpec` is the source of truth for preview and export. The Agent modifies DeckSpec through tools; the preview renderer and PPTX exporter both consume the same state to avoid drift between what the user sees and what gets exported.

## OpenAI-Compatible Providers

The runtime uses OpenAI-compatible configuration keys:

- `OPENAI_BASE_URL`
- `OPENAI_API_KEY`
- `OPENAI_MODEL`

This supports official OpenAI endpoints and third-party compatible providers without changing desktop code.
