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

## DeckSpec

`DeckSpec` is the source of truth for preview and export. The Agent modifies DeckSpec through tools; the preview renderer and PPTX exporter both consume the same state to avoid drift between what the user sees and what gets exported.

## OpenAI-Compatible Providers

The runtime uses OpenAI-compatible configuration keys:

- `OPENAI_BASE_URL`
- `OPENAI_API_KEY`
- `OPENAI_MODEL`

This supports official OpenAI endpoints and third-party compatible providers without changing desktop code.
