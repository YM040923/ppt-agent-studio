# PPT Agent Studio

PPT Agent Studio is a Windows-native, presentation-focused AI Agent. It is inspired by autonomous Agent systems such as OpenManus, but it is scoped to one product workflow: plan, draft, preview, revise, and export editable PowerPoint decks.

## Product Shape

- WinUI 3 desktop shell with Fluent Design, Mica, and a Manus-style split workspace.
- Left pane: chat-first Agent interaction.
- Right pane: live PPT preview rendered through WebView2.
- Chat messages render Markdown and code blocks, and can expose inline actions such as `Demo Deck` on the starter message and `Open PPTX` when an editable export is ready.
- The command bar can start a new deck, run a demo deck, cancel an in-flight Agent turn, show the latest PPTX export, and open runtime settings.
- Python Agent runtime for planning, tool calling, DeckSpec state, preview rendering, and editable PPTX export.
- OpenAI-compatible configuration, including third-party endpoints via `OPENAI_BASE_URL`, `OPENAI_API_KEY`, and `OPENAI_MODEL`.

## Current MVP Runtime

The first runtime increments include a deterministic local `AgentSession`. It accepts a user message, emits ordered Agent events, collects a safe research brief, builds a starter `DeckSpec`, renders a full HTML preview document, and exposes a basic `pptx.export` tool. Follow-up add/update/remove slide and dark-theme requests mutate the existing DeckSpec through `deck.add_slide`, `deck.update_slide`, `deck.remove_slide`, or `design.apply_theme`, refresh the preview, and export a new revision instead of rebuilding the deck from scratch. The runtime also emits safe `tool.completed` progress events so the WinUI chat pane can show what the Agent has just finished without exposing raw tool payloads or secrets. This gives the WinUI client a stable event contract before live model calls are added.

The runtime now has a planner boundary. By default it uses the deterministic fallback planner. Set `PPT_AGENT_PLANNER=llm` together with a valid OpenAI-compatible API key to route outline planning through the model-backed planner.

Each successful Agent turn exports an editable PPTX artifact before refreshing the preview. Slide-level `speaker_notes` are kept in DeckSpec and exported into PowerPoint speaker notes. Deck-level `metadata.audience` and `metadata.style` are preserved through preview sync and written into PowerPoint document properties. By default artifacts are written under `artifacts/decks`; set `PPT_AGENT_ARTIFACTS_DIR` to use a different local output directory.

The WinUI app starts the local runtime automatically in development. To run the runtime manually for protocol testing:

```powershell
$env:PYTHONPATH=(Resolve-Path .\agent\src).Path
python -m ppt_agent_studio.runtime.websocket_server --host 127.0.0.1 --port 8765
```

Then run the desktop app:

```powershell
dotnet run --project desktop\PptAgentStudio.App\PptAgentStudio.App.csproj
```

On startup the desktop app probes `runtime.config` and shows the configured model endpoint, whether it came from environment variables, `.env.local`, or defaults, whether an API key is present, which planner is active, where PPTX artifacts are written, and which env file is being checked. The key value is never displayed.

The Python runtime keeps Agent session state by `session_id` and `deck_id`, so repeated desktop turns can advance DeckSpec revisions instead of restarting from revision 1. When the user starts a new deck, the desktop app sends `session.reset` for the current deck before advancing to the next runtime deck identity.

The desktop app filters deck-scoped runtime events by the active deck id. This keeps delayed messages from an older deck from overwriting the current preview or latest PPTX export after a reset.

When the desktop app starts the runtime sidecar, it pins `PPT_AGENT_ARTIFACTS_DIR` to the repository `artifacts/decks` directory so generated PPTX files land in a predictable project-local location.

After a deck is generated, the `Open PPTX` command locates the latest editable PowerPoint export in File Explorer. The same action is also surfaced as an inline chat button on the export-ready assistant message.

## Repository Layout

```text
desktop/PptAgentStudio.App/   WinUI 3 desktop app
agent/                        Python Agent runtime
docs/                         Architecture and implementation notes
```

See `docs/openmanus-reference.md` for how this project maps OpenManus architecture ideas into a presentation-specific Agent without forking the upstream project.

## Local Checks

Run the main Windows verification script:

```powershell
.\scripts\verify.ps1
```

It runs the Python tests, desktop tests, desktop app build, and an 8-second WinUI startup smoke. To run checks individually:

```powershell
python -m pytest agent\tests -q
dotnet test desktop\PptAgentStudio.App.Tests\PptAgentStudio.App.Tests.csproj
dotnet build PptAgentStudio.slnx
```

Generate an offline demo deck without calling a model:

```powershell
$env:PYTHONPATH=(Resolve-Path .\agent\src).Path
python -m ppt_agent_studio.runtime.demo --artifact-dir artifacts\demo
```

Add `--follow-up "Add a risk mitigation slide"` to generate a second revision that demonstrates cached follow-up editing.
The demo writes preview HTML, editable PPTX, and a summary JSON file into the artifact directory; with the follow-up example, the summary file is `demo-deck-r2-summary.json`.

## Packaging

Create an unsigned sideload MSIX package locally:

```powershell
dotnet build desktop\PptAgentStudio.App\PptAgentStudio.App.csproj -c Release -p:GenerateAppxPackageOnBuild=true -p:AppxPackageSigningEnabled=false -p:UapAppxPackageBuildMode=SideloadOnly -p:AppxBundle=Never -p:PublishTrimmed=false
```

The package is written under `desktop\PptAgentStudio.App\AppPackages`. CI runs the same packaging smoke and uploads a zipped AppPackages artifact named `ppt-agent-studio-msix.zip`.

## Configuration

Copy `.env.example` to `.env.local`, then fill in your local or third-party OpenAI-compatible provider. The Python runtime loads `.env.local` from the repository root, while explicit process environment variables take priority:

```text
OPENAI_BASE_URL=https://your-provider.example/v1
OPENAI_API_KEY=your-secret-key
OPENAI_MODEL=your-compatible-model
OPENAI_EXTRA_HEADERS={"X-Provider":"tenant-id"}
PPT_AGENT_PLANNER=llm
```

`OPENAI_EXTRA_HEADERS` is optional and must be a JSON object. It is sent to the model provider, but runtime status only reports whether extra headers are configured; names and values are not displayed. Do not commit `.env.local`.

Desktop sidecar overrides such as `PPT_AGENT_RUNTIME_ROOT` and `PPT_AGENT_PYTHON` are read before Python starts, so set them in the shell that launches the WinUI app rather than inside `.env.local`.

The runtime exposes a safe configuration probe over WebSocket:

```json
{ "type": "runtime.config", "session_id": "desktop-session" }
```

It reports the configured endpoint, whether that endpoint looks local or cloud-hosted, where core settings came from, model, active planner mode, PPTX artifact directory, env file path/existence, whether an API key is present, and whether extra provider headers are configured without returning secret values.

The Python runtime includes an injectable OpenAI-compatible chat client and an LLM outline planner. The planner accepts fenced JSON or prose-wrapped JSON from compatible providers, fills in a safe DeckSpec theme when the model omits one, backfills deterministic slides when the model returns fewer slides than the user explicitly requested, falls back to deterministic slides if the model returns no usable slides, and caps oversized model outlines at 30 slides for MVP responsiveness. The default Agent turn still uses the deterministic fallback planner unless `PPT_AGENT_PLANNER=llm` and `OPENAI_API_KEY` are both configured, so the MVP remains testable without a network call or API key.

The core Agent system prompt lives in `ppt_agent_studio.prompts` and scopes the assistant to presentation work, DeckSpec revisions, live preview updates, editable PPTX artifacts, and secret-safe configuration reporting.
