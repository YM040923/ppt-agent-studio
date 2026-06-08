# Tool Catalog

The Python runtime exposes a presentation-specific tool catalog through
`ppt_agent_studio.tools.catalog.core_tool_definitions()` and the WebSocket
`runtime.tools` message. Tools are intentionally scoped to DeckSpec, preview,
research, design, and PPTX export work. The MVP does not expose a general shell
or browser tool.

## `deck.create_from_outline`

Creates a `DeckSpec` from a structured presentation outline.

Required input:

```json
{
  "outline": {},
  "deck_id": "desktop-deck"
}
```

Optional input:

```json
{
  "revision": 1
}
```

Output:

```json
{
  "deck": {}
}
```

## `deck.update_slide`

Updates one slide in the current `DeckSpec` by `slide_id`.

Required input:

```json
{
  "deck": {},
  "slide_id": "s2",
  "patch": {}
}
```

Output:

```json
{
  "deck": {}
}
```

## `deck.add_slide`

Appends or inserts a slide into the current `DeckSpec`.

Required input:

```json
{
  "deck": {},
  "slide": {}
}
```

Optional input:

```json
{
  "after_slide_id": "s1",
  "before_slide_id": "s2"
}
```

Output:

```json
{
  "deck": {}
}
```

## `deck.move_slide`

Repositions a slide inside the current `DeckSpec` by `slide_id`.

Required input:

```json
{
  "deck": {},
  "slide_id": "s2"
}
```

Optional input:

```json
{
  "after_slide_id": "s4",
  "before_slide_id": "s1"
}
```

Output:

```json
{
  "deck": {}
}
```

## `deck.remove_slide`

Removes a slide from the current `DeckSpec` by `slide_id`.

Required input:

```json
{
  "deck": {},
  "slide_id": "s2"
}
```

Output:

```json
{
  "deck": {}
}
```

## `preview.render_html`

Renders the current `DeckSpec` as a full HTML preview document for WebView2.

Required input:

```json
{
  "deck": {}
}
```

Output:

```json
{
  "html": "<!doctype html>..."
}
```

## `pptx.export`

Exports the current `DeckSpec` to an editable PowerPoint file.

Required input:

```json
{
  "deck": {},
  "output_path": "artifacts/decks/desktop-deck-r1.pptx"
}
```

Output:

```json
{
  "path": "artifacts/decks/desktop-deck-r1.pptx",
  "slide_count": 5
}
```

## `research.collect_brief`

Collects a concise research brief for the deck topic and audience. The MVP
handler is deterministic and safe; future model-backed research should keep
secret and source payloads out of chat progress events.

Required input:

```json
{
  "topic": "AI operating model",
  "audience": "executive committee"
}
```

Optional input:

```json
{
  "constraints": ["Style: McKinsey", "Slides: 20"]
}
```

Output:

```json
{
  "brief": {
    "topic": "AI operating model",
    "audience": "executive committee",
    "constraints": ["Style: McKinsey"],
    "questions": [],
    "source_suggestions": [
      "Recent reports, filings, and investor materials related to AI operating model.",
      "Industry benchmarks and analyst research tailored to executive committee.",
      "Internal performance, customer, financial, and operating metrics."
    ],
    "evidence_needs": [
      "Market context and size of the opportunity.",
      "Current-state baseline, pain points, and root causes.",
      "Decision options with value, risk, timing, and ownership implications."
    ]
  }
}
```

## `design.apply_theme`

Applies a presentation theme token set to the `DeckSpec`.

Required input:

```json
{
  "deck": {},
  "theme": {
    "name": "executive-consulting",
    "background": "#EEF2F7",
    "slide_background": "#FFFFFF",
    "text": "#111827",
    "accent": "#2563EB"
  }
}
```

Output:

```json
{
  "deck": {}
}
```
