# PPT Agent Studio MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a new E-drive open-source monorepo for a Windows-native PPT-focused AI Agent with a WinUI 3 shell and a Python Agent runtime foundation.

**Architecture:** The desktop app is a WinUI 3 front end with a chat area and WebView2 preview pane. The Python runtime owns Agent state, DeckSpec data, OpenAI-compatible configuration, preview HTML rendering, and future PPTX export.

**Tech Stack:** WinUI 3, Windows App SDK, WebView2, .NET, Python 3.11+, pytest, python-pptx, websockets/httpx/pydantic.

---

### Task 1: Repository Skeleton

**Files:**
- Create: `README.md`
- Create: `LICENSE`
- Create: `.gitignore`
- Create: `.github/workflows/ci.yml`
- Create: `docs/architecture.md`

- [ ] Create an open-source repository skeleton under `E:\MyProjects\ppt-agent-studio`.
- [ ] Add MIT license, README, gitignore, architecture notes, and CI for Python tests plus .NET build.
- [ ] Verify: `git status --short` shows only intended new files.

### Task 2: WinUI 3 Desktop Shell

**Files:**
- Create: `desktop/PptAgentStudio.App/`
- Modify: `desktop/PptAgentStudio.App/MainWindow.xaml`
- Modify: `desktop/PptAgentStudio.App/MainWindow.xaml.cs`

- [ ] Generate a WinUI 3 MVVM app using `dotnet new winui-mvvm`.
- [ ] Replace the first screen with a Manus-style layout: left chat column, right preview column, command bar, Mica backdrop.
- [ ] Add WebView2 package reference if the template does not include it.
- [ ] Verify: `dotnet build desktop/PptAgentStudio.App/PptAgentStudio.App.csproj`.

### Task 3: Python Runtime Foundation

**Files:**
- Create: `agent/pyproject.toml`
- Create: `agent/src/ppt_agent_studio/deck/spec.py`
- Create: `agent/src/ppt_agent_studio/protocol/events.py`
- Create: `agent/tests/test_deck_spec.py`
- Create: `agent/tests/test_events.py`

- [ ] Write failing tests for DeckSpec normalization and event envelopes.
- [ ] Implement minimal DeckSpec and AgentEvent models.
- [ ] Verify: `python -m pytest agent/tests -q`.

### Task 4: Preview Renderer

**Files:**
- Create: `agent/src/ppt_agent_studio/preview/html_renderer.py`
- Create: `agent/tests/test_preview_renderer.py`

- [ ] Write failing tests for escaped HTML preview output and slide count rendering.
- [ ] Implement a deterministic HTML renderer from DeckSpec.
- [ ] Verify: `python -m pytest agent/tests -q`.

### Task 5: OpenAI-Compatible Configuration

**Files:**
- Create: `.env.example`
- Create: `agent/src/ppt_agent_studio/llm/config.py`
- Create: `agent/tests/test_llm_config.py`

- [ ] Write tests proving `OPENAI_BASE_URL`, `OPENAI_API_KEY`, and `OPENAI_MODEL` are loaded without printing secrets.
- [ ] Implement config loading with third-party OpenAI-compatible endpoints.
- [ ] Verify: `python -m pytest agent/tests -q`.

### Task 6: Final Verification

**Files:**
- Modify only files created in prior tasks.

- [ ] Run Python tests: `python -m pytest agent/tests -q`.
- [ ] Run .NET build: `dotnet build desktop/PptAgentStudio.App/PptAgentStudio.App.csproj`.
- [ ] Run `git status --short`.
- [ ] Commit the first MVP scaffold when verification passes.
