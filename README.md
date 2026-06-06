# PPT Agent Studio

PPT Agent Studio is a Windows-native, presentation-focused AI Agent. It is inspired by autonomous Agent systems such as OpenManus, but it is scoped to one product workflow: plan, draft, preview, revise, and export editable PowerPoint decks.

## Product Shape

- WinUI 3 desktop shell with Fluent Design, Mica, and a Manus-style split workspace.
- Left pane: chat-first Agent interaction.
- Right pane: live PPT preview rendered through WebView2.
- Python Agent runtime for planning, tool calling, DeckSpec state, preview rendering, and future PPTX export.
- OpenAI-compatible configuration, including third-party endpoints via `OPENAI_BASE_URL`, `OPENAI_API_KEY`, and `OPENAI_MODEL`.

## Repository Layout

```text
desktop/PptAgentStudio.App/   WinUI 3 desktop app
agent/                        Python Agent runtime
docs/                         Architecture and implementation notes
```

## Local Checks

```powershell
python -m pytest agent\tests -q
dotnet build desktop\PptAgentStudio.App\PptAgentStudio.App.csproj
```

## Configuration

Create `.env.local` or set environment variables locally:

```text
OPENAI_BASE_URL=https://your-provider.example/v1
OPENAI_API_KEY=your-secret-key
OPENAI_MODEL=your-compatible-model
```

Do not commit `.env.local`.
