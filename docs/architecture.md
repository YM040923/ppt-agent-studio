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
tool.completed
plan.updated
tool.completed
deck.updated
tool.completed
preview.ready
tool.completed
pptx.ready
plan.updated
```

This sequence is intentionally small. It proves state ordering, research brief collection, live preview synchronization, editable artifact creation, and completed-plan reporting before adding richer tool execution.

`plan.updated` carries both the raw outline and a deck-specific `DeckPlan`. The outline preserves the planner result for debugging, while `DeckPlan` gives the desktop app future-ready step IDs, titles, statuses, and slide counts for progress UI.

The first `tool.completed` in a turn reports `research.collect_brief`; the following `plan.updated` carries the safe research brief and moves the draft step to running. Later tool events report DeckSpec creation, preview rendering, and PPTX export.

`tool.completed` is a safe progress event emitted after a deterministic tool succeeds and before the related product sync event. Its payload includes `tool_name`, `status`, and a short `summary`; it does not carry raw tool outputs or secrets. The desktop app displays it in chat but keeps the turn open until `error` or the final completed `plan.updated`.

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

`preview.ready` is the live-preview synchronization event. Its payload includes rendered `html`, `deck_id`, `revision`, `deck_title`, `slide_count`, and `theme_name`; the desktop preview pane uses the HTML, while chat/status summaries can show the title, slide count, and active theme without parsing the preview document.

The `pptx.ready` payload includes the exported PowerPoint `path`, `deck_title`, `slide_count`, and `theme_name` so the desktop export-ready message can match the active preview title and theme without inspecting the PPTX file.

Runtime Agent sessions are cached by `(session_id, deck_id)` inside the Python process. This lets the desktop client reconnect for each user turn while preserving DeckSpec revision numbers, event ordering, and the latest deck state for that workspace.

When a follow-up message clearly asks to add, append, create, duplicate, move, update, rename, remove, or delete a slide, the runtime mutates the cached DeckSpec with `deck.add_slide`, `deck.move_slide`, `deck.update_slide`, or `deck.remove_slide`. Add/create follow-ups can insert before or after first/last, ordinal, or numbered slide targets. Duplicate follow-ups copy first/last, ordinal, or numbered slide targets. Move follow-ups reposition slides before or after first/last, ordinal, or numbered targets. Update/rename and remove/delete follow-ups honor first/last, ordinal, and numbered slide targets, with removal defaulting to the last slide when no target is specified; invalid numbered targets emit an `error` event without mutating the cached deck. Clear dark theme and light/clean theme follow-ups, including plain `Make it darker` and `Make it brighter` requests, use `design.apply_theme` against the cached DeckSpec. Both paths emit a new `deck.updated` revision, refresh `preview.ready`, and export a new `pptx.ready` artifact. Other follow-up prompts still run through the planner path until richer edit-intent routing is added.

The desktop app filters deck-scoped runtime events by the active deck id before mutating preview or export state. This protects the UI when a user starts a new deck or cancels a turn while delayed messages from an older deck are still in flight.

When the desktop app starts a new deck workspace, it first asks the runtime to discard the current cached deck session:

```json
{
  "type": "session.reset",
  "session_id": "desktop-session",
  "deck_id": "desktop-deck"
}
```

The response is a single `session.reset` event with payload `{ "deck_id": "...", "cleared": true|false }`. If the runtime is offline, the desktop still clears local UI state and advances to a new deck identity.

During development the WinUI app starts the sidecar automatically if `127.0.0.1:8765` is not already listening. The locator walks up from the app base directory until it finds `agent/src`, and `PPT_AGENT_RUNTIME_ROOT` can override the repository root. The Python executable defaults to `python`; set `PPT_AGENT_PYTHON` to use a specific interpreter. PPTX artifacts are written to `artifacts/decks` by default; set `PPT_AGENT_ARTIFACTS_DIR` to use another directory.

The desktop client passes a cancellation token into the current WebSocket turn. The `Cancel` command requests cancellation immediately, and starting a new deck also cancels the in-flight turn before clearing local UI state.

The desktop app or a test client can ask for a redacted runtime configuration summary:

```json
{ "type": "runtime.config", "session_id": "desktop-session" }
```

The response is a single `runtime.config` event. It includes `base_url`, `model`, `endpoint_kind`, `requires_api_key`, a per-field `source` summary, `has_api_key`, `has_extra_headers`, planner `requested`/`active` modes, the PPTX artifact directory, and the env file `path`/`exists` status, but never returns API key or header values. Loopback URLs, private-network IPs, link-local IPs, and `.local` hostnames are classified as local endpoints; public hostnames remain cloud-hosted.

The WinUI startup flow calls this probe after the Python sidecar is ready and shows a concise status line with the configured model endpoint, key presence, and active planner. The Settings dialog also shows whether the endpoint is local or cloud-hosted, whether each core config value came from process environment, `.env.local`, or defaults, the project-local PPTX artifact directory, and env file status so users can find exported decks and confirm whether `.env.local` is being picked up. Its Open Env Folder action selects an existing `.env.local` in Explorer or opens the parent folder when the env file is missing. Its Create Env File action writes a safe template when `.env.local` is missing and does not overwrite an existing env file.

Runtime outline planning is selected through `PPT_AGENT_PLANNER`. The default is `fallback`, which keeps local development deterministic and offline. Set `PPT_AGENT_PLANNER=llm` to use the model-backed `LLMOutlinePlanner`; cloud endpoints require `OPENAI_API_KEY`, while local endpoints can run without one when the local server accepts anonymous requests. If a cloud endpoint key is missing, the runtime keeps using the fallback planner instead of failing the desktop turn.

## Preview Pane

The WinUI app hosts the live preview with the WebView2 control bundled through Windows App SDK. Do not add a separate `Microsoft.Web.WebView2` package reference unless a future Windows App SDK release explicitly requires it; the first scaffold verified that the extra package can conflict with WinUI runtime startup. The desktop app initializes WebView2 with `EnsureCoreWebView2Async` before calling `NavigateToString`.

## DeckSpec

`DeckSpec` is the source of truth for preview and export. The Agent modifies DeckSpec through tools; the preview renderer and PPTX exporter both consume the same state to avoid drift between what the user sees and what gets exported. Slide-level `speaker_notes` stay on DeckSpec slides, are exposed as hidden preview metadata, and are written into PowerPoint speaker notes during export. Deck-level `metadata.audience` and `metadata.style` are extracted from prompts when possible, included in hidden preview meta tags, and written into PowerPoint document properties during export. The active theme name is also exposed in hidden preview metadata so standalone preview HTML keeps the same style context as `preview.ready`.

## Tool System

The Python runtime exposes tool definitions through `ppt_agent_studio.tools`. `ToolRegistry` owns executable handlers and the core catalog defines MVP interfaces for deck creation, slide edits, preview rendering, PPTX export, research briefs, and theme application. The registry validates `input_schema.required` before invoking handlers, so future LLM tool calls fail early with a clear tool argument error. The deterministic `AgentSession` already calls the registry for `deck.create_from_outline`, `preview.render_html`, and `pptx.export`, and emits `tool.completed` after each successful call. The default registry can execute slide update/add/remove tools, deterministic research briefs, theme application, and editable PowerPoint output. This gives future ReAct/Tool Calling loops a stable execution boundary without changing the desktop event contract.

## OpenAI-Compatible Providers

The runtime uses OpenAI-compatible configuration keys:

- `OPENAI_BASE_URL`
- `OPENAI_API_KEY`
- `OPENAI_MODEL`
- `OPENAI_EXTRA_HEADERS`
- `PPT_AGENT_PLANNER`

This supports official OpenAI endpoints and third-party compatible providers without changing desktop code.

The Python runtime reads these values from process environment variables first, then falls back to `.env.local` in the repository root. Set `PPT_AGENT_ENV_FILE` to point at a different local env file when needed.

`OPENAI_EXTRA_HEADERS` is an optional JSON object for provider-specific request headers. `runtime.config` only returns the boolean `has_extra_headers`; header names and values are treated as hidden configuration.

`OpenAICompatibleChatClient` posts to `{OPENAI_BASE_URL}/chat/completions` with the configured model, bearer token, and optional extra headers. It accepts standard message content strings, text content blocks, and legacy compatible `choices[].text` responses. It also accepts an injected `httpx.AsyncClient`, so runtime tests can use `httpx.MockTransport` and avoid real network calls or secret exposure. The `LLMOutlinePlanner` uses this client plus the core system prompt to request a JSON DeckSpec outline, while `FallbackOutlinePlanner` remains the default for offline MVP runs.

The core system prompt is stored in `ppt_agent_studio.prompts`. It scopes the Agent to presentation work, requires DeckSpec-backed revisions, ties deck mutations to `preview.ready` and `pptx.ready`, and forbids revealing API keys or hidden configuration.
