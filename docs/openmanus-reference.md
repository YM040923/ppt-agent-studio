# OpenManus Reference Strategy

PPT Agent Studio uses OpenManus as an architectural reference, not as an upstream fork. The product scope is narrower: autonomous presentation creation, live preview, and editable PPTX output for Windows desktop users.

## Sources Reviewed

- Current OpenManus repository: [FoundationAgents/OpenManus](https://github.com/FoundationAgents/OpenManus)
- Early archived reference: [mannaandpoem/OpenManus_Archive](https://github.com/mannaandpoem/OpenManus_Archive)
- Agent loop references: [`app/agent/base.py`](https://github.com/FoundationAgents/OpenManus/blob/main/app/agent/base.py), [`app/agent/react.py`](https://github.com/FoundationAgents/OpenManus/blob/main/app/agent/react.py), [`app/agent/toolcall.py`](https://github.com/FoundationAgents/OpenManus/blob/main/app/agent/toolcall.py)
- Planning references: [`app/flow/planning.py`](https://github.com/FoundationAgents/OpenManus/blob/main/app/flow/planning.py), [`app/tool/planning.py`](https://github.com/FoundationAgents/OpenManus/blob/main/app/tool/planning.py)
- Tool references: [`app/tool`](https://github.com/FoundationAgents/OpenManus/tree/main/app/tool), including tool collection, shell, browser, editor, search, and planning tools.

## Mapping To PPT Agent Studio

| OpenManus concept | What to borrow | PPT Agent Studio mapping |
| --- | --- | --- |
| `BaseAgent` state, memory, and step loop | Explicit state transitions, bounded steps, duplicate/stuck detection | `AgentSession` owns turn execution; future `AgentRunState` should track `idle/running/finished/error`, step count, and retries. |
| `ReActAgent.think()` / `act()` split | Separate reasoning from tool execution | Current `OutlinePlanner` handles planning; future `DeckAgent` should emit tool intents, execute them through `ToolRegistry`, then observe DeckSpec changes. |
| `ToolCallAgent` | Function/tool-call loop, special terminate tool, robust tool result formatting | `ToolRegistry` and `ToolDefinition` are the stable local equivalent. Tool outputs should become typed events and DeckSpec deltas, not generic text only. |
| `PlanningFlow` and `PlanningTool` | Plan creation, step status, executor selection | Add a deck-specific `DeckPlan` with steps like research, outline, narrative, visual direction, slide generation, QA, export. Emit `plan.updated` after every status change. |
| Multi-agent executor selection | Route different plan steps to specialized agents | Future roles: `ResearchAgent`, `StorylineAgent`, `VisualDesignAgent`, `DeckBuildAgent`, `CritiqueAgent`, `ExportAgent`. Keep one user-visible session and one DeckSpec source of truth. |
| Sandbox/code tools | Isolated execution for code, browser, and file work | Do not expose general shell/computer tools in the desktop MVP. Prefer presentation-safe tools: chart rendering, layout solving, image lookup, citation extraction, PPTX export. |
| Tool collection abstraction | Register tools with names, schemas, and handlers | Continue extending `ppt_agent_studio.tools` with JSON-schema-like inputs and deterministic tests before wiring live LLM tool calls. |

## Deliberate Differences

PPT Agent Studio should be less general than OpenManus:

- The Agent must stay inside the presentation workflow unless the user asks for configuration or export help.
- DeckSpec is the source of truth. Every meaningful tool action should update DeckSpec or an artifact derived from it.
- The desktop event contract matters as much as the Python loop: `plan.updated`, `deck.updated`, `pptx.ready`, and `preview.ready` are product-level synchronization points.
- CodeAct-style execution should be domain constrained. A future Python execution tool can calculate charts or layout metrics, but should not become a general autonomous shell by default.
- Multi-agent collaboration should be internal orchestration. The Windows UI should show a clean turn timeline, not raw agent chatter.

## Implementation Roadmap

1. Replace `FallbackOutlinePlanner` with a model-backed planner when `PPT_AGENT_PLANNER=llm` is active.
2. Add a `DeckPlan` model with step statuses, plan IDs, and a `plan.updated` event payload stable enough for UI rendering.
3. Introduce a tool-calling loop that can choose among deck tools, run them through `ToolRegistry`, and append observations to turn memory.
4. Add domain-specific specialist agents only after the single-agent tool loop is stable.
5. Add safe sandboxed helpers for charts, citation extraction, and layout scoring before any broader CodeAct capability.
6. Keep tests at every boundary: planner parsing, tool schemas, DeckSpec mutations, preview output, PPTX artifacts, and desktop event handling.
