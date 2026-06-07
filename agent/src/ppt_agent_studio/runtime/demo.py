from __future__ import annotations

import argparse
import asyncio
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from ppt_agent_studio.runtime.session import AgentSession


DEFAULT_PROMPT = "Make a 5 slide board AI strategy deck in McKinsey style."


@dataclass(frozen=True)
class DemoRunSummary:
    session_id: str
    deck_id: str
    deck_revision: int
    follow_up: str
    slide_count: int
    event_count: int
    preview_html_path: Path
    pptx_path: Path
    summary_json_path: Path


async def run_demo(
    prompt: str = DEFAULT_PROMPT,
    follow_up: str = "",
    artifact_dir: str | os.PathLike[str] = "artifacts/demo",
    session_id: str = "demo-session",
    deck_id: str = "demo-deck",
) -> DemoRunSummary:
    output_dir = Path(artifact_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    session = AgentSession(session_id=session_id, deck_id=deck_id, artifact_dir=output_dir)
    preview_html = ""
    pptx_path: Path | None = None
    deck_revision = 0
    slide_count = 0
    event_count = 0

    async def consume_turn(text: str) -> None:
        nonlocal deck_revision, event_count, preview_html, pptx_path, slide_count
        async for event in session.submit_user_message(text):
            event_count += 1
            if event.deck_revision is not None:
                deck_revision = event.deck_revision
            if event.type == "preview.ready":
                preview_html = str(event.payload.get("html") or "")
            if event.type == "pptx.ready":
                pptx_path = Path(str(event.payload.get("path") or ""))
                slide_count = int(event.payload.get("slide_count") or 0)

    await consume_turn(prompt)
    normalized_follow_up = follow_up.strip()
    if normalized_follow_up:
        await consume_turn(normalized_follow_up)

    if not preview_html:
        raise RuntimeError("Demo run did not produce preview HTML.")
    if pptx_path is None:
        raise RuntimeError("Demo run did not produce a PPTX artifact.")

    preview_html_path = output_dir / f"{_safe_artifact_name(deck_id)}-r{deck_revision}.html"
    preview_html_path.write_text(preview_html, encoding="utf-8")
    summary_json_path = output_dir / f"{_safe_artifact_name(deck_id)}-r{deck_revision}-summary.json"

    summary = DemoRunSummary(
        session_id=session_id,
        deck_id=deck_id,
        deck_revision=deck_revision,
        follow_up=normalized_follow_up,
        slide_count=slide_count,
        event_count=event_count,
        preview_html_path=preview_html_path,
        pptx_path=pptx_path,
        summary_json_path=summary_json_path,
    )
    summary_json_path.write_text(
        json.dumps(
            {
                "session_id": summary.session_id,
                "deck_id": summary.deck_id,
                "deck_revision": summary.deck_revision,
                "follow_up": summary.follow_up,
                "slide_count": summary.slide_count,
                "event_count": summary.event_count,
                "preview_html_path": str(summary.preview_html_path),
                "pptx_path": str(summary.pptx_path),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return summary


def format_summary(summary: DemoRunSummary) -> str:
    lines = [
        "PPT Agent Studio demo deck generated.",
        f"Session: {summary.session_id}",
        f"Deck: {summary.deck_id} r{summary.deck_revision}",
    ]
    if summary.follow_up:
        lines.append(f"Follow-up: {summary.follow_up}")
    lines.extend(
        [
            f"Slides: {summary.slide_count}",
            f"Events: {summary.event_count}",
            f"Preview HTML: {summary.preview_html_path}",
            f"Editable PPTX: {summary.pptx_path}",
            f"Run summary: {summary.summary_json_path}",
        ]
    )
    return "\n".join(lines)


def main(argv: Iterable[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Generate an offline PPT Agent Studio demo deck.")
    parser.add_argument("--prompt", default=DEFAULT_PROMPT)
    parser.add_argument("--follow-up", default="")
    parser.add_argument("--artifact-dir", default="artifacts/demo")
    parser.add_argument("--session-id", default="demo-session")
    parser.add_argument("--deck-id", default="demo-deck")
    args = parser.parse_args(list(argv) if argv is not None else None)

    summary = asyncio.run(
        run_demo(
            prompt=args.prompt,
            follow_up=args.follow_up,
            artifact_dir=args.artifact_dir,
            session_id=args.session_id,
            deck_id=args.deck_id,
        )
    )
    print(format_summary(summary))


def _safe_artifact_name(value: str) -> str:
    cleaned = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in value.strip())
    return cleaned or "deck"


if __name__ == "__main__":
    main()
