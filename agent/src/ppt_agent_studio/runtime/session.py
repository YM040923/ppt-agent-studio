from __future__ import annotations

import os
from pathlib import Path
from collections.abc import AsyncIterator

from ppt_agent_studio.deck.spec import DeckSpec, SlideSpec
from ppt_agent_studio.planning.outline import FallbackOutlinePlanner, OutlinePlanner
from ppt_agent_studio.planning.plan import DeckPlan
from ppt_agent_studio.protocol.events import AgentEvent
from ppt_agent_studio.tools.base import ToolRegistry
from ppt_agent_studio.tools.deck_tools import build_default_registry


class AgentSession:
    def __init__(
        self,
        session_id: str,
        deck_id: str,
        tool_registry: ToolRegistry | None = None,
        outline_planner: OutlinePlanner | None = None,
        artifact_dir: str | os.PathLike[str] | None = None,
    ):
        self.session_id = session_id
        self.deck_id = deck_id
        self._tool_registry = tool_registry or build_default_registry()
        self._outline_planner = outline_planner or FallbackOutlinePlanner()
        self._artifact_dir = Path(artifact_dir or os.getenv("PPT_AGENT_ARTIFACTS_DIR", "artifacts/decks"))
        self._seq = 0
        self._deck_revision = 0
        self.deck: DeckSpec | None = None

    async def submit_user_message(self, message: str) -> AsyncIterator[AgentEvent]:
        text = message.strip()
        if not text:
            yield self._event("error", {"message": "User message is required"})
            return

        yield self._event("user.message", {"text": text})
        outline = await self._outline_planner.create_outline(text)
        next_revision = self._deck_revision + 1
        plan = DeckPlan.from_outline(outline, plan_id=f"{self._safe_artifact_name(self.deck_id)}-r{next_revision}-plan")
        plan.status = "running"
        plan.update_step_status("research_context", "running")
        plan.update_step_status("structure_story", "completed")
        yield self._event("plan.updated", {"outline": outline, "plan": plan.to_dict()})

        research_result = await self._tool_registry.run(
            "research.collect_brief",
            self._research_arguments(outline, text),
        )
        research_brief = research_result.payload.get("brief") if isinstance(research_result.payload.get("brief"), dict) else {}
        plan.update_step_status("research_context", "completed")
        plan.update_step_status("draft_slides", "running")
        yield self._event(
            "tool.completed",
            {
                "tool_name": "research.collect_brief",
                "status": "completed",
                "summary": "Collected research brief.",
            },
        )
        yield self._event("plan.updated", {"outline": outline, "research_brief": research_brief, "plan": plan.to_dict()})

        self._deck_revision = next_revision
        deck_result = await self._tool_registry.run(
            "deck.create_from_outline",
            {"outline": outline, "deck_id": self.deck_id, "revision": self._deck_revision},
        )
        deck_payload = deck_result.payload["deck"]
        self.deck = self._deck_from_payload(deck_payload)
        plan.update_step_status("draft_slides", "completed")
        yield self._tool_completed_event("deck.create_from_outline", "Created deck from outline.")
        yield self._deck_event("deck.updated", {"deck": self.deck.to_dict()})

        preview_result = await self._tool_registry.run("preview.render_html", {"deck": self.deck.to_dict()})
        plan.update_step_status("render_preview", "completed")
        yield self._tool_completed_event("preview.render_html", "Rendered live preview HTML.")
        yield self._deck_event(
            "preview.ready",
            {
                "html": str(preview_result.payload["html"]),
                "deck_id": self.deck.deck_id,
                "revision": self.deck.revision,
                "deck_title": self.deck.title,
                "slide_count": len(self.deck.slides),
            },
        )

        pptx_path = self._artifact_dir / f"{self._safe_artifact_name(self.deck_id)}-r{self._deck_revision}.pptx"
        pptx_result = await self._tool_registry.run(
            "pptx.export",
            {"deck": self.deck.to_dict(), "output_path": str(pptx_path)},
        )
        plan.update_step_status("export_pptx", "completed")
        yield self._tool_completed_event("pptx.export", "Exported editable PPTX artifact.")
        yield self._deck_event("pptx.ready", dict(pptx_result.payload))

        plan.status = "completed"
        yield self._event("plan.updated", {"outline": outline, "plan": plan.to_dict()})

    def _event(self, event_type: str, payload: dict[str, object]) -> AgentEvent:
        self._seq += 1
        return AgentEvent(
            seq=self._seq,
            session_id=self.session_id,
            type=event_type,
            payload=payload,
        )

    def _deck_event(self, event_type: str, payload: dict[str, object]) -> AgentEvent:
        self._seq += 1
        return AgentEvent(
            seq=self._seq,
            session_id=self.session_id,
            type=event_type,
            deck_id=self.deck_id,
            deck_revision=self._deck_revision,
            payload=payload,
        )

    def _tool_completed_event(self, tool_name: str, summary: str) -> AgentEvent:
        return self._deck_event(
            "tool.completed",
            {
                "tool_name": tool_name,
                "status": "completed",
                "summary": summary,
            },
        )

    @staticmethod
    def _deck_from_payload(payload: object) -> DeckSpec:
        if not isinstance(payload, dict):
            raise ValueError("deck tool must return a deck object")
        raw_slides = payload.get("slides") if isinstance(payload.get("slides"), list) else []
        slides = [
            SlideSpec(
                slide_id=str(raw_slide.get("slide_id") or f"s{index}"),
                title=str(raw_slide.get("title") or f"Slide {index}"),
                layout=str(raw_slide.get("layout") or "content"),
                blocks=raw_slide.get("blocks") if isinstance(raw_slide.get("blocks"), list) else [],
                speaker_notes=str(raw_slide.get("speaker_notes") or ""),
            )
            for index, raw_slide in enumerate(raw_slides, start=1)
            if isinstance(raw_slide, dict)
        ]
        return DeckSpec(
            deck_id=str(payload.get("deck_id") or "deck"),
            title=str(payload.get("title") or "Untitled Deck"),
            revision=int(payload.get("revision") or 0),
            slides=slides,
            theme=payload.get("theme") if isinstance(payload.get("theme"), dict) else {},
            metadata=payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {},
        )

    @staticmethod
    def _research_arguments(outline: dict[str, object], prompt: str) -> dict[str, object]:
        metadata = outline.get("metadata") if isinstance(outline.get("metadata"), dict) else {}
        topic = str(outline.get("deck_title") or outline.get("title") or prompt).strip() or prompt
        audience = str(metadata.get("audience") or "").strip() or "general business audience"
        style = str(metadata.get("style") or "").strip()
        constraints = [f"Style: {style}"] if style else []
        raw_slides = outline.get("slides")
        if isinstance(raw_slides, list) and raw_slides:
            constraints.append(f"Slides: {len(raw_slides)}")
        return {
            "topic": topic,
            "audience": audience,
            "constraints": constraints,
        }

    @staticmethod
    def _safe_artifact_name(value: str) -> str:
        cleaned = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in value.strip())
        return cleaned or "deck"
