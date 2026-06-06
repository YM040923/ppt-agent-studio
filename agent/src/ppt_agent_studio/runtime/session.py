from __future__ import annotations

from collections.abc import AsyncIterator

from ppt_agent_studio.deck.spec import DeckSpec, SlideSpec
from ppt_agent_studio.protocol.events import AgentEvent
from ppt_agent_studio.tools.base import ToolRegistry
from ppt_agent_studio.tools.deck_tools import build_default_registry


class AgentSession:
    def __init__(self, session_id: str, deck_id: str, tool_registry: ToolRegistry | None = None):
        self.session_id = session_id
        self.deck_id = deck_id
        self._tool_registry = tool_registry or build_default_registry()
        self._seq = 0
        self._deck_revision = 0
        self.deck: DeckSpec | None = None

    async def submit_user_message(self, message: str) -> AsyncIterator[AgentEvent]:
        text = message.strip()
        if not text:
            yield self._event("error", {"message": "User message is required"})
            return

        yield self._event("user.message", {"text": text})
        outline = self._fallback_outline(text)
        yield self._event("plan.updated", {"outline": outline})

        self._deck_revision += 1
        deck_result = await self._tool_registry.run(
            "deck.create_from_outline",
            {"outline": outline, "deck_id": self.deck_id, "revision": self._deck_revision},
        )
        deck_payload = deck_result.payload["deck"]
        self.deck = self._deck_from_payload(deck_payload)
        yield self._deck_event("deck.updated", {"deck": self.deck.to_dict()})

        preview_result = await self._tool_registry.run("preview.render_html", {"deck": self.deck.to_dict()})
        yield self._deck_event("preview.ready", {"html": str(preview_result.payload["html"])})

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

    @staticmethod
    def _fallback_outline(prompt: str) -> dict[str, object]:
        topic = prompt.removesuffix(".").strip()
        return {
            "deck_title": topic,
            "slides": [
                {
                    "title": topic,
                    "subtitle": "Executive presentation draft",
                    "prototype_hint": "cover",
                },
                {
                    "title": "Strategic context",
                    "prototype_hint": "content",
                    "points": [
                        {
                            "label": "Objective",
                            "body": "Clarify the decision, audience, and expected business outcome.",
                        },
                        {
                            "label": "Signal",
                            "body": "Frame the core trend and why it matters now.",
                        },
                    ],
                },
                {
                    "title": "Recommended path",
                    "prototype_hint": "content",
                    "bullets": [
                        "Define the target operating model.",
                        "Prioritize high-leverage use cases.",
                        "Sequence rollout with measurable checkpoints.",
                    ],
                },
            ],
        }

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
            )
            for index, raw_slide in enumerate(raw_slides, start=1)
            if isinstance(raw_slide, dict)
        ]
        return DeckSpec(
            deck_id=str(payload.get("deck_id") or "deck"),
            title=str(payload.get("title") or "Untitled Deck"),
            revision=int(payload.get("revision") or 0),
            slides=slides,
        )
