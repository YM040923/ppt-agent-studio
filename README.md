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

The first runtime increments include a deterministic local `AgentSession`. It accepts a user message, emits ordered Agent events, collects a safe research brief, builds a starter `DeckSpec`, renders a full HTML preview document, and exposes a basic `pptx.export` tool. Follow-up add/create/update/rename/remove slide and dark/light-theme requests mutate the existing DeckSpec through `deck.add_slide`, `deck.update_slide`, `deck.remove_slide`, or `design.apply_theme`, refresh the preview, and export a new revision instead of rebuilding the deck from scratch. Deck rename follow-ups update the deck title. Audience/style follow-ups update deck metadata. Add/create follow-ups can insert before or after first/last, ordinal, or numbered slide targets. Add/create follow-ups can also send new slides to the beginning or end. Duplicate follow-ups copy first/last, ordinal, or numbered slide targets before or after a target. Duplicate follow-ups can also send copied slides to the beginning or end. Move follow-ups reposition slides before or after first/last, ordinal, or numbered targets. Move follow-ups can also send slides to the beginning or end. Update/rename and remove follow-ups honor first/last, ordinal, and numbered slide targets, with removal defaulting to the last slide when no target is specified. Explicit dark theme and light/clean theme requests, plus plain follow-ups such as `Make it darker` and `Make it brighter`, use the same theme tool path. The runtime also emits safe `tool.completed` progress events so the WinUI chat pane can show what the Agent has just finished without exposing raw tool payloads or secrets. This gives the WinUI client a stable event contract before live model calls are added.

The runtime now has a planner boundary. By default it uses the deterministic fallback planner. Set `PPT_AGENT_PLANNER=llm` to route outline planning through the model-backed planner. Cloud endpoints still require a valid OpenAI-compatible API key. Local endpoints can run the LLM planner without an API key when the local server accepts anonymous requests.

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

On startup the desktop app probes `runtime.config` and shows the configured model endpoint, whether it came from environment variables, `.env.local`, or defaults, whether an API key is present, which planner is active, where PPTX artifacts are written, and which env file is being checked. The Settings dialog includes an Open Env Folder action that selects an existing `.env.local` or opens its parent folder when the file is missing, plus a Create Env File action that writes a safe template when `.env.local` is missing and does not overwrite an existing file. The key value is never displayed.

The Python runtime keeps Agent session state by `session_id` and `deck_id`, so repeated desktop turns can advance DeckSpec revisions instead of restarting from revision 1. When the user starts a new deck, the desktop app sends `session.reset` for the current deck before advancing to the next runtime deck identity.

The desktop app filters deck-scoped runtime events by the active deck id. This keeps delayed messages from an older deck from overwriting the current preview or latest PPTX export after a reset.

When the desktop app starts the runtime sidecar, it pins `PPT_AGENT_ARTIFACTS_DIR` to the repository `artifacts/decks` directory so generated PPTX files land in a predictable project-local location.

After a deck is generated, the `Open PPTX` command locates the latest editable PowerPoint export in File Explorer. The same action is also surfaced as an inline chat button on the export-ready assistant message, but only appears when `pptx.ready` includes a usable export path. The desktop app clears stale export actions when a newer Agent turn or deck revision starts, and clears the missing path if the exported file was moved or deleted.

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

It runs the Python tests, offline demo smoke under `artifacts\verify-demo`, desktop tests, desktop app build, and an 8-second WinUI startup smoke. To run checks individually:

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

Add `--follow-up "Create an executive summary slide at the beginning"` to generate a second revision that demonstrates cached follow-up editing and slide placement.
The demo writes preview HTML, editable PPTX, a summary JSON file, and a Markdown summary into the artifact directory; with the follow-up example, the summary files are `demo-deck-r2-summary.json` and `demo-deck-r2-summary.md`. The summary JSON includes the prompt, optional follow-up prompt, final `deck_title`, final `theme_name`, slide count, event count, event type flow, and artifact paths including `summary_json_path` and `summary_markdown_path`.

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

It reports the configured endpoint, whether that endpoint looks local or cloud-hosted, whether the endpoint requires an API key, where core settings came from, model, active planner mode, PPTX artifact directory, env file path/existence, whether an API key is present, and whether extra provider headers are configured without returning secret values.
Loopback URLs, private-network IPs, link-local IPs, and `.local` hostnames are shown as local endpoints; public hostnames remain cloud-hosted.

The Python runtime includes an injectable OpenAI-compatible chat client and an LLM outline planner. The planner accepts fenced JSON or prose-wrapped JSON from compatible providers, fills in a safe DeckSpec theme when the model omits one, backfills deterministic slides when the model returns fewer slides than the user explicitly requested, falls back to deterministic slides if the model returns no usable slides, and caps oversized model outlines at 30 slides for MVP responsiveness. The default Agent turn still uses the deterministic fallback planner unless `PPT_AGENT_PLANNER=llm` is set and either an API key is configured or the endpoint is classified as local, so the MVP remains testable without a network call or API key.

The core Agent system prompt lives in `ppt_agent_studio.prompts` and scopes the assistant to presentation work, DeckSpec revisions, live preview updates, editable PPTX artifacts, and secret-safe configuration reporting.
