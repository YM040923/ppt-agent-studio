# Contributing

Thanks for helping build PPT Agent Studio. The project is still in MVP shape, so the best contributions are small, focused, and easy to verify.

## Local Setup

Use Windows 11 or a recent Windows runner with .NET 10 SDK, Python 3.11, and WebView2 installed.

Install the Python runtime in editable mode:

```powershell
python -m pip install --upgrade pip
python -m pip install -e agent[dev]
```

For model-backed planning, copy `.env.example` to `.env.local` and fill in an OpenAI-compatible provider. Never commit `.env.local`, API keys, or generated artifacts.

## Checks

Run Python tests:

```powershell
python -m pytest agent\tests -q
```

Run desktop tests:

```powershell
dotnet test desktop\PptAgentStudio.App.Tests\PptAgentStudio.App.Tests.csproj
```

Run the offline demo smoke:

```powershell
python -m ppt_agent_studio.runtime.demo --artifact-dir artifacts\demo --follow-up "Add a risk mitigation slide"
```

Build the desktop app:

```powershell
dotnet build PptAgentStudio.slnx
```

## Pull Requests

Keep each change narrow and include the relevant verification output in the PR description. For UI changes, run the app when feasible and check the chat, preview, settings, export, and reset flows before marking the work ready.
