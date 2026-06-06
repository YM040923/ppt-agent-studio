from __future__ import annotations

from collections.abc import AsyncIterator

from ppt_agent_studio.deck.spec import DeckSpec, deck_from_outline
from ppt_agent_studio.preview.html_renderer import render_preview_document
from ppt_agent_studio.protocol.events import AgentEvent


class AgentSession:
    def __init__(self, session_id: str, deck_id: str):
        self.session_id = session_id
        self.deck_id = deck_id
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
        self.deck = deck_from_outline(outline, deck_id=self.deck_id, revision=self._deck_revision)
        yield self._deck_event("deck.updated", {"deck": self.deck.to_dict()})
        yield self._deck_event("preview.ready", {"html": render_preview_document(self.deck)})

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
