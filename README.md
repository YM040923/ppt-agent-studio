# PPT Agent Studio

PPT Agent Studio is a Windows-native, presentation-focused AI Agent. It is inspired by autonomous Agent systems such as OpenManus, but it is scoped to one product workflow: plan, draft, preview, revise, and export editable PowerPoint decks.

## Product Shape

- WinUI 3 desktop shell with Fluent Design, Mica, and a Manus-style split workspace.
- Left pane: chat-first Agent interaction.
- Right pane: live PPT preview rendered through WebView2.
- Python Agent runtime for planning, tool calling, DeckSpec state, preview rendering, and editable PPTX export.
- OpenAI-compatible configuration, including third-party endpoints via `OPENAI_BASE_URL`, `OPENAI_API_KEY`, and `OPENAI_MODEL`.

## Current MVP Runtime

The first runtime increments include a deterministic local `AgentSession`. It accepts a user message, emits ordered Agent events, builds a starter `DeckSpec`, renders a full HTML preview document, and exposes a basic `pptx.export` tool. This gives the WinUI client a stable event contract before live model calls are added.

The runtime now has a planner boundary. By default it uses the deterministic fallback planner. Set `PPT_AGENT_PLANNER=llm` together with a valid OpenAI-compatible API key to route outline planning through the model-backed planner.

Each successful Agent turn exports an editable PPTX artifact before refreshing the preview. By default artifacts are written under `artifacts/decks`; set `PPT_AGENT_ARTIFACTS_DIR` to use a different local output directory.

The WinUI app starts the local runtime automatically in development. To run the runtime manually for protocol testing:

```powershell
$env:PYTHONPATH="E:\MyProjects\ppt-agent-studio\agent\src"
python -m ppt_agent_studio.runtime.websocket_server --host 127.0.0.1 --port 8765
```

Then run the desktop app:

```powershell
dotnet run --project desktop\PptAgentStudio.App\PptAgentStudio.App.csproj
```

On startup the desktop app probes `runtime.config` and shows the configured model endpoint, whether an API key is present, and which planner is active. The key value is never displayed.

## Repository Layout

```text
desktop/PptAgentStudio.App/   WinUI 3 desktop app
agent/                        Python Agent runtime
docs/                         Architecture and implementation notes
```

See `docs/openmanus-reference.md` for how this project maps OpenManus architecture ideas into a presentation-specific Agent without forking the upstream project.

## Local Checks

```powershell
python -m pytest agent\tests -q
dotnet test desktop\PptAgentStudio.App.Tests\PptAgentStudio.App.Tests.csproj
dotnet build PptAgentStudio.slnx
```

## Configuration

Copy `.env.example` to `.env.local`, then fill in your local or third-party OpenAI-compatible provider. The Python runtime loads `.env.local` from the repository root, while explicit process environment variables take priority:

```text
OPENAI_BASE_URL=https://your-provider.example/v1
OPENAI_API_KEY=your-secret-key
OPENAI_MODEL=your-compatible-model
PPT_AGENT_PLANNER=llm
```

Do not commit `.env.local`.

The runtime exposes a safe configuration probe over WebSocket:

```json
{ "type": "runtime.config", "session_id": "desktop-session" }
```

It reports the configured endpoint, model, active planner mode, and whether an API key is present without returning the key.

The Python runtime includes an injectable OpenAI-compatible chat client and an LLM outline planner. The default Agent turn still uses the deterministic fallback planner unless `PPT_AGENT_PLANNER=llm` and `OPENAI_API_KEY` are both configured, so the MVP remains testable without a network call or API key.

The core Agent system prompt lives in `ppt_agent_studio.prompts` and scopes the assistant to presentation work, DeckSpec revisions, live preview updates, editable PPTX artifacts, and secret-safe configuration reporting.
