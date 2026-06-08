from __future__ import annotations

import os
import re
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
        deck_title_update = self._deck_title_update_request(text)
        if self.deck is not None and deck_title_update is not None:
            async for event in self._submit_deck_title_follow_up(deck_title_update):
                yield event
            return
        deck_metadata_update = self._deck_metadata_update_request(text)
        if self.deck is not None and deck_metadata_update is not None:
            async for event in self._submit_deck_metadata_follow_up(*deck_metadata_update):
                yield event
            return
        title_update = self._slide_title_update_request(text)
        if self.deck is not None and title_update is not None:
            async for event in self._submit_update_slide_title_follow_up(*title_update):
                yield event
            return
        move_request = self._slide_move_request(text)
        if self.deck is not None and move_request is not None:
            async for event in self._submit_move_slide_follow_up(*move_request):
                yield event
            return
        if self.deck is not None and self._is_duplicate_slide_request(text):
            before_target = self._slide_insert_before_target(text)
            after_target = self._slide_insert_after_target(text)
            if before_target is None and after_target is None:
                edge_target = self._slide_edge_insert_target(text)
                if edge_target is not None:
                    position, target = edge_target
                    if position == "before":
                        before_target = target
                    else:
                        after_target = target
            async for event in self._submit_duplicate_slide_follow_up(
                self._slide_remove_target(text),
                before_target,
                after_target,
            ):
                yield event
            return
        if self.deck is not None and self._is_add_slide_request(text):
            async for event in self._submit_add_slide_follow_up(text):
                yield event
            return
        remove_target = self._slide_remove_target(text)
        if self.deck is not None and self._is_remove_slide_request(text):
            async for event in self._submit_remove_slide_follow_up(remove_target):
                yield event
            return
        if self.deck is not None:
            follow_up_theme = self._theme_follow_up_request(text)
            if follow_up_theme is not None:
                async for event in self._submit_theme_follow_up(follow_up_theme):
                    yield event
                return

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

        async for event in self._render_preview_export_and_complete(plan, outline):
            yield event

    async def _submit_add_slide_follow_up(self, text: str) -> AsyncIterator[AgentEvent]:
        if self.deck is None:
            return

        next_revision = self._deck_revision + 1
        title = self._follow_up_slide_title(text)
        before_target = self._slide_insert_before_target(text)
        after_target = self._slide_insert_after_target(text)
        if before_target is None and after_target is None:
            edge_target = self._slide_edge_insert_target(text)
            if edge_target is not None:
                position, target = edge_target
                if position == "before":
                    before_target = target
                else:
                    after_target = target
        before_slide_id = ""
        after_slide_id = ""
        outline_slides = [{"title": slide.title} for slide in self.deck.slides]
        insert_target = before_target if before_target is not None else after_target
        if insert_target is not None:
            if isinstance(insert_target, int):
                if insert_target > len(self.deck.slides):
                    yield self._event(
                        "error",
                        {"message": f"Slide {insert_target} is not available. Deck has {len(self.deck.slides)} slides."},
                    )
                    return
                insert_index = insert_target - 1
            else:
                insert_index = 0 if insert_target == "first" else len(self.deck.slides) - 1
            if before_target is not None:
                before_slide_id = self.deck.slides[insert_index].slide_id
                outline_slides.insert(insert_index, {"title": title})
            else:
                after_slide_id = self.deck.slides[insert_index].slide_id
                outline_slides.insert(insert_index + 1, {"title": title})
        else:
            outline_slides.append({"title": title})
        outline = {
            "deck_title": self.deck.title,
            "slides": outline_slides,
        }
        plan = DeckPlan.from_outline(outline, plan_id=f"{self._safe_artifact_name(self.deck_id)}-r{next_revision}-plan")
        plan.status = "running"
        plan.update_step_status("research_context", "completed")
        plan.update_step_status("structure_story", "completed")
        plan.update_step_status("draft_slides", "running")
        yield self._event("plan.updated", {"outline": outline, "plan": plan.to_dict()})

        slide = {
            "slide_id": f"s{len(self.deck.slides) + 1}",
            "title": title,
            "layout": "content",
            "blocks": [
                {
                    "type": "point",
                    "label": "Why it matters",
                    "body": f"Add executive-level context on {title}.",
                },
                {
                    "type": "point",
                    "label": "Evidence to gather",
                    "body": "Quantify impact, trade-offs, and ownership.",
                },
                {
                    "type": "point",
                    "label": "Decision lens",
                    "body": "Clarify the recommendation and next action.",
                },
            ],
            "speaker_notes": f"Use this slide to pressure-test the recommendation around {title}.",
        }
        tool_args = {"deck": self.deck.to_dict(), "slide": slide}
        if before_slide_id:
            tool_args["before_slide_id"] = before_slide_id
        if after_slide_id:
            tool_args["after_slide_id"] = after_slide_id
        deck_result = await self._tool_registry.run(
            "deck.add_slide",
            tool_args,
        )
        self.deck = self._deck_from_payload(deck_result.payload["deck"])
        self._deck_revision = self.deck.revision
        plan.update_step_status("draft_slides", "completed")
        yield self._tool_completed_event("deck.add_slide", f"Added slide: {title}.")
        yield self._deck_event("deck.updated", {"deck": self.deck.to_dict()})

        async for event in self._render_preview_export_and_complete(plan, outline):
            yield event

    async def _submit_duplicate_slide_follow_up(
        self,
        source: int | str,
        before_target: int | str | None = None,
        after_target: int | str | None = None,
    ) -> AsyncIterator[AgentEvent]:
        if self.deck is None or not self.deck.slides:
            return

        next_revision = self._deck_revision + 1
        source_slide, source_index, source_label = self._resolve_slide_target(source)
        if source_slide is None:
            yield self._event(
                "error",
                {"message": f"Slide {source} is not available. Deck has {len(self.deck.slides)} slides."},
            )
            return
        if before_target is not None and after_target is not None:
            yield self._event(
                "error",
                {"message": "Duplicate slide placement cannot include both before and after targets."},
            )
            return

        before_slide_id = ""
        after_slide_id = source_slide.slide_id
        summary = f"Duplicated {source_label}."
        insert_index = source_index + 1
        placement_target = before_target if before_target is not None else after_target
        if placement_target is not None:
            placement_slide, placement_index, placement_label = self._resolve_slide_target(placement_target)
            if placement_slide is None:
                yield self._event(
                    "error",
                    {"message": f"Slide {placement_target} is not available. Deck has {len(self.deck.slides)} slides."},
                )
                return
            position = "before" if before_target is not None else "after"
            insert_index = placement_index if before_target is not None else placement_index + 1
            before_slide_id = placement_slide.slide_id if before_target is not None else ""
            after_slide_id = placement_slide.slide_id if after_target is not None else ""
            summary = f"Duplicated {source_label} {position} {placement_label}."
        outline_slides = [{"title": slide.title} for slide in self.deck.slides]
        outline_slides.insert(insert_index, {"title": source_slide.title})
        outline = {
            "deck_title": self.deck.title,
            "slides": outline_slides,
        }
        plan = DeckPlan.from_outline(outline, plan_id=f"{self._safe_artifact_name(self.deck_id)}-r{next_revision}-plan")
        plan.status = "running"
        plan.update_step_status("research_context", "completed")
        plan.update_step_status("structure_story", "completed")
        plan.update_step_status("draft_slides", "running")
        yield self._event("plan.updated", {"outline": outline, "plan": plan.to_dict()})

        slide = source_slide.to_dict()
        slide["slide_id"] = f"s{len(self.deck.slides) + 1}"
        tool_args = {"deck": self.deck.to_dict(), "slide": slide}
        if before_slide_id:
            tool_args["before_slide_id"] = before_slide_id
        if after_slide_id:
            tool_args["after_slide_id"] = after_slide_id
        deck_result = await self._tool_registry.run("deck.add_slide", tool_args)
        self.deck = self._deck_from_payload(deck_result.payload["deck"])
        self._deck_revision = self.deck.revision
        plan.update_step_status("draft_slides", "completed")
        yield self._tool_completed_event("deck.add_slide", summary)
        yield self._deck_event("deck.updated", {"deck": self.deck.to_dict()})

        async for event in self._render_preview_export_and_complete(plan, outline):
            yield event

    async def _submit_deck_title_follow_up(self, title: str) -> AsyncIterator[AgentEvent]:
        if self.deck is None:
            return

        next_revision = self._deck_revision + 1
        outline = {
            "deck_title": title,
            "slides": [{"title": slide.title} for slide in self.deck.slides],
        }
        plan = DeckPlan.from_outline(outline, plan_id=f"{self._safe_artifact_name(self.deck_id)}-r{next_revision}-plan")
        plan.status = "running"
        plan.update_step_status("research_context", "completed")
        plan.update_step_status("structure_story", "completed")
        plan.update_step_status("draft_slides", "running")
        yield self._event("plan.updated", {"outline": outline, "plan": plan.to_dict()})

        deck_result = await self._tool_registry.run(
            "deck.update_deck",
            {
                "deck": self.deck.to_dict(),
                "patch": {"title": title},
            },
        )
        self.deck = self._deck_from_payload(deck_result.payload["deck"])
        self._deck_revision = self.deck.revision
        plan.update_step_status("draft_slides", "completed")
        yield self._tool_completed_event("deck.update_deck", f"Renamed deck: {title}.")
        yield self._deck_event("deck.updated", {"deck": self.deck.to_dict()})

        async for event in self._render_preview_export_and_complete(plan, outline):
            yield event

    async def _submit_deck_metadata_follow_up(self, key: str, value: str) -> AsyncIterator[AgentEvent]:
        if self.deck is None:
            return

        next_revision = self._deck_revision + 1
        metadata = dict(self.deck.metadata)
        metadata[key] = value
        outline = {
            "deck_title": self.deck.title,
            "metadata": metadata,
            "slides": [{"title": slide.title} for slide in self.deck.slides],
        }
        plan = DeckPlan.from_outline(outline, plan_id=f"{self._safe_artifact_name(self.deck_id)}-r{next_revision}-plan")
        plan.status = "running"
        plan.update_step_status("research_context", "completed")
        plan.update_step_status("structure_story", "completed")
        plan.update_step_status("draft_slides", "running")
        yield self._event("plan.updated", {"outline": outline, "plan": plan.to_dict()})

        deck_result = await self._tool_registry.run(
            "deck.update_deck",
            {
                "deck": self.deck.to_dict(),
                "patch": {"metadata": {key: value}},
            },
        )
        self.deck = self._deck_from_payload(deck_result.payload["deck"])
        self._deck_revision = self.deck.revision
        plan.update_step_status("draft_slides", "completed")
        yield self._tool_completed_event("deck.update_deck", f"Updated deck {key}: {value}.")
        yield self._deck_event("deck.updated", {"deck": self.deck.to_dict()})

        async for event in self._render_preview_export_and_complete(plan, outline):
            yield event

    async def _submit_move_slide_follow_up(
        self,
        source: int | str,
        position: str,
        target: int | str,
    ) -> AsyncIterator[AgentEvent]:
        if self.deck is None or not self.deck.slides:
            return

        source_slide, source_index, source_label = self._resolve_slide_target(source)
        target_slide, _, target_label = self._resolve_slide_target(target)
        if source_slide is None:
            yield self._event(
                "error",
                {"message": f"Slide {source} is not available. Deck has {len(self.deck.slides)} slides."},
            )
            return
        if target_slide is None:
            yield self._event(
                "error",
                {"message": f"Slide {target} is not available. Deck has {len(self.deck.slides)} slides."},
            )
            return
        if source_slide.slide_id == target_slide.slide_id:
            yield self._event("error", {"message": "Cannot move a slide relative to itself."})
            return

        next_revision = self._deck_revision + 1
        outline_slides = [{"title": slide.title} for slide in self.deck.slides]
        moving_outline = outline_slides.pop(source_index)
        remaining_slides = [slide for slide in self.deck.slides if slide.slide_id != source_slide.slide_id]
        target_index = next(
            index for index, slide in enumerate(remaining_slides) if slide.slide_id == target_slide.slide_id
        )
        outline_slides.insert(target_index if position == "before" else target_index + 1, moving_outline)
        outline = {
            "deck_title": self.deck.title,
            "slides": outline_slides,
        }
        plan = DeckPlan.from_outline(outline, plan_id=f"{self._safe_artifact_name(self.deck_id)}-r{next_revision}-plan")
        plan.status = "running"
        plan.update_step_status("research_context", "completed")
        plan.update_step_status("structure_story", "completed")
        plan.update_step_status("draft_slides", "running")
        yield self._event("plan.updated", {"outline": outline, "plan": plan.to_dict()})

        tool_args = {"deck": self.deck.to_dict(), "slide_id": source_slide.slide_id}
        tool_args[f"{position}_slide_id"] = target_slide.slide_id
        deck_result = await self._tool_registry.run("deck.move_slide", tool_args)
        self.deck = self._deck_from_payload(deck_result.payload["deck"])
        self._deck_revision = self.deck.revision
        plan.update_step_status("draft_slides", "completed")
        yield self._tool_completed_event("deck.move_slide", f"Moved {source_label} {position} {target_label}.")
        yield self._deck_event("deck.updated", {"deck": self.deck.to_dict()})

        async for event in self._render_preview_export_and_complete(plan, outline):
            yield event

    async def _submit_update_slide_title_follow_up(self, target: int | str, title: str) -> AsyncIterator[AgentEvent]:
        if self.deck is None or not self.deck.slides:
            return

        next_revision = self._deck_revision + 1
        if isinstance(target, int):
            if target > len(self.deck.slides):
                yield self._event(
                    "error",
                    {"message": f"Slide {target} is not available. Deck has {len(self.deck.slides)} slides."},
                )
                return
            target_slide = self.deck.slides[target - 1]
            target_label = f"slide {target}"
        else:
            target_slide = self.deck.slides[0] if target == "first" else self.deck.slides[-1]
            target_label = f"{target} slide"
        outline_slides = [
            {"title": title if slide.slide_id == target_slide.slide_id else slide.title}
            for slide in self.deck.slides
        ]
        outline = {
            "deck_title": self.deck.title,
            "slides": outline_slides,
        }
        plan = DeckPlan.from_outline(outline, plan_id=f"{self._safe_artifact_name(self.deck_id)}-r{next_revision}-plan")
        plan.status = "running"
        plan.update_step_status("research_context", "completed")
        plan.update_step_status("structure_story", "completed")
        plan.update_step_status("draft_slides", "running")
        yield self._event("plan.updated", {"outline": outline, "plan": plan.to_dict()})

        deck_result = await self._tool_registry.run(
            "deck.update_slide",
            {
                "deck": self.deck.to_dict(),
                "slide_id": target_slide.slide_id,
                "patch": {"title": title},
            },
        )
        self.deck = self._deck_from_payload(deck_result.payload["deck"])
        self._deck_revision = self.deck.revision
        plan.update_step_status("draft_slides", "completed")
        yield self._tool_completed_event("deck.update_slide", f"Renamed {target_label}: {title}.")
        yield self._deck_event("deck.updated", {"deck": self.deck.to_dict()})

        async for event in self._render_preview_export_and_complete(plan, outline):
            yield event

    async def _submit_remove_slide_follow_up(self, target: int | str) -> AsyncIterator[AgentEvent]:
        if self.deck is None or not self.deck.slides:
            return

        next_revision = self._deck_revision + 1
        if isinstance(target, int):
            if target > len(self.deck.slides):
                yield self._event(
                    "error",
                    {"message": f"Slide {target} is not available. Deck has {len(self.deck.slides)} slides."},
                )
                return
            target_slide = self.deck.slides[target - 1]
            target_label = f"slide {target}"
        else:
            target_slide = self.deck.slides[0] if target == "first" else self.deck.slides[-1]
            target_label = f"{target} slide"
        outline = {
            "deck_title": self.deck.title,
            "slides": [{"title": slide.title} for slide in self.deck.slides if slide.slide_id != target_slide.slide_id],
        }
        plan = DeckPlan.from_outline(outline, plan_id=f"{self._safe_artifact_name(self.deck_id)}-r{next_revision}-plan")
        plan.status = "running"
        plan.update_step_status("research_context", "completed")
        plan.update_step_status("structure_story", "completed")
        plan.update_step_status("draft_slides", "running")
        yield self._event("plan.updated", {"outline": outline, "plan": plan.to_dict()})

        deck_result = await self._tool_registry.run(
            "deck.remove_slide",
            {"deck": self.deck.to_dict(), "slide_id": target_slide.slide_id},
        )
        self.deck = self._deck_from_payload(deck_result.payload["deck"])
        self._deck_revision = self.deck.revision
        plan.update_step_status("draft_slides", "completed")
        yield self._tool_completed_event("deck.remove_slide", f"Removed {target_label}.")
        yield self._deck_event("deck.updated", {"deck": self.deck.to_dict()})

        async for event in self._render_preview_export_and_complete(plan, outline):
            yield event

    async def _submit_theme_follow_up(self, theme: dict[str, str]) -> AsyncIterator[AgentEvent]:
        if self.deck is None:
            return

        next_revision = self._deck_revision + 1
        outline = {
            "deck_title": self.deck.title,
            "theme": theme,
            "slides": [{"title": slide.title} for slide in self.deck.slides],
        }
        plan = DeckPlan.from_outline(outline, plan_id=f"{self._safe_artifact_name(self.deck_id)}-r{next_revision}-plan")
        plan.status = "running"
        plan.update_step_status("research_context", "completed")
        plan.update_step_status("structure_story", "completed")
        plan.update_step_status("draft_slides", "running")
        yield self._event("plan.updated", {"outline": outline, "plan": plan.to_dict()})

        deck_result = await self._tool_registry.run(
            "design.apply_theme",
            {"deck": self.deck.to_dict(), "theme": theme},
        )
        self.deck = self._deck_from_payload(deck_result.payload["deck"])
        self._deck_revision = self.deck.revision
        plan.update_step_status("draft_slides", "completed")
        yield self._tool_completed_event("design.apply_theme", f"Applied theme: {theme.get('name', 'theme')}.")
        yield self._deck_event("deck.updated", {"deck": self.deck.to_dict()})

        async for event in self._render_preview_export_and_complete(plan, outline):
            yield event

    async def _render_preview_export_and_complete(
        self,
        plan: DeckPlan,
        outline: dict[str, object],
    ) -> AsyncIterator[AgentEvent]:
        if self.deck is None:
            return

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
                "theme_name": str(self.deck.theme.get("name") or ""),
            },
        )

        pptx_path = self._artifact_dir / f"{self._safe_artifact_name(self.deck_id)}-r{self._deck_revision}.pptx"
        pptx_result = await self._tool_registry.run(
            "pptx.export",
            {"deck": self.deck.to_dict(), "output_path": str(pptx_path)},
        )
        plan.update_step_status("export_pptx", "completed")
        yield self._tool_completed_event("pptx.export", "Exported editable PPTX artifact.")
        pptx_payload = dict(pptx_result.payload)
        pptx_payload["deck_title"] = self.deck.title
        pptx_payload["theme_name"] = str(self.deck.theme.get("name") or "")
        yield self._deck_event("pptx.ready", pptx_payload)

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

    def _resolve_slide_target(self, target: int | str) -> tuple[SlideSpec | None, int, str]:
        if self.deck is None or not self.deck.slides:
            return None, -1, f"slide {target}"
        if isinstance(target, int):
            target_label = f"slide {target}"
            if target > len(self.deck.slides):
                return None, -1, target_label
            return self.deck.slides[target - 1], target - 1, target_label
        target_index = 0 if target == "first" else len(self.deck.slides) - 1
        return self.deck.slides[target_index], target_index, f"{target} slide"

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
    def _is_add_slide_request(prompt: str) -> bool:
        if re.search(r"\b(add|append)\b", prompt, flags=re.IGNORECASE):
            return True
        if re.search(r"\bcreate\b.*\b(slide|page)\b", prompt, flags=re.IGNORECASE):
            return True
        return any(token in prompt for token in ["新增", "增加", "加一页", "加一张", "加一个"])

    @staticmethod
    def _is_duplicate_slide_request(prompt: str) -> bool:
        return re.search(r"\b(duplicate|copy)\b.*\b(slide|page)\b", prompt, flags=re.IGNORECASE) is not None

    @staticmethod
    def _slide_remove_target(prompt: str) -> int | str:
        match = re.search(r"\b(?:slide|page)\s+(?P<number>\d+)\b", prompt, flags=re.IGNORECASE)
        if match is not None:
            return max(1, int(match.group("number")))
        ordinal = AgentSession._ordinal_slide_target(prompt)
        if ordinal is not None:
            return ordinal
        return "first" if re.search(r"\bfirst\b", prompt, flags=re.IGNORECASE) else "last"

    @staticmethod
    def _slide_insert_after_target(prompt: str) -> int | str | None:
        match = re.search(
            r"\bafter\s+(?:the\s+)?(?:(?P<target>first|last)\s+(?:slide|page)|(?P<ordinal>second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth)\s+(?:slide|page)|(?:slide|page)\s+(?P<number>\d+))\b",
            prompt,
            flags=re.IGNORECASE,
        )
        if match is None:
            return None
        number = match.group("number")
        if number is not None:
            return max(1, int(number))
        ordinal = match.group("ordinal")
        if ordinal is not None:
            return AgentSession._ordinal_value(ordinal)
        return match.group("target").casefold()

    @staticmethod
    def _slide_insert_before_target(prompt: str) -> int | str | None:
        match = re.search(
            r"\bbefore\s+(?:the\s+)?(?:(?P<target>first|last)\s+(?:slide|page)|(?P<ordinal>second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth)\s+(?:slide|page)|(?:slide|page)\s+(?P<number>\d+))\b",
            prompt,
            flags=re.IGNORECASE,
        )
        if match is None:
            return None
        number = match.group("number")
        if number is not None:
            return max(1, int(number))
        ordinal = match.group("ordinal")
        if ordinal is not None:
            return AgentSession._ordinal_value(ordinal)
        return match.group("target").casefold()

    @staticmethod
    def _slide_edge_insert_target(prompt: str) -> tuple[str, str] | None:
        match = re.search(
            r"\b(?:to|at)\s+(?:the\s+)?(?P<edge>beginning|start|front|end|back)\b",
            prompt,
            flags=re.IGNORECASE,
        )
        if match is None:
            return None
        edge = match.group("edge").casefold()
        if edge in {"beginning", "start", "front"}:
            return "before", "first"
        return "after", "last"

    @staticmethod
    def _ordinal_slide_target(prompt: str) -> int | None:
        match = re.search(
            r"\b(?P<ordinal>second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth)\s+(?:slide|page)\b",
            prompt,
            flags=re.IGNORECASE,
        )
        if match is None:
            return None
        return AgentSession._ordinal_value(match.group("ordinal"))

    @staticmethod
    def _ordinal_value(ordinal: str) -> int:
        return {
            "second": 2,
            "third": 3,
            "fourth": 4,
            "fifth": 5,
            "sixth": 6,
            "seventh": 7,
            "eighth": 8,
            "ninth": 9,
            "tenth": 10,
        }[ordinal.casefold()]

    @staticmethod
    def _is_remove_slide_request(prompt: str) -> bool:
        if re.search(r"\b(remove|delete)\b", prompt, flags=re.IGNORECASE):
            return True
        return any(token in prompt for token in ["删除", "移除", "删掉"])

    @staticmethod
    def _is_dark_theme_request(prompt: str) -> bool:
        if re.search(r"\b(make\s+(?:it|the\s+deck|the\s+presentation)\s+darker|darken\s+(?:it|the\s+deck|the\s+presentation)|darker)\b", prompt, flags=re.IGNORECASE):
            return True
        if re.search(r"\b(dark|deep|night)\b.*\b(theme|style|look)\b", prompt, flags=re.IGNORECASE):
            return True
        if re.search(r"\b(theme|style|look)\b.*\b(dark|deep|night)\b", prompt, flags=re.IGNORECASE):
            return True
        return any(token in prompt for token in ["深色", "暗色", "黑色主题", "深色风格"])

    @staticmethod
    def _is_light_theme_request(prompt: str) -> bool:
        if re.search(r"\b(make\s+(?:it|the\s+deck|the\s+presentation)\s+(?:brighter|lighter)|lighten\s+(?:it|the\s+deck|the\s+presentation)|brighter|lighter)\b", prompt, flags=re.IGNORECASE):
            return True
        if re.search(r"\b(light|clean|bright)\b.*\b(theme|style|look)\b", prompt, flags=re.IGNORECASE):
            return True
        if re.search(r"\b(theme|style|look)\b.*\b(light|clean|bright)\b", prompt, flags=re.IGNORECASE):
            return True
        if re.search(r"\b(consulting|executive-consulting)\b.*\b(theme|style|look)\b", prompt, flags=re.IGNORECASE):
            return True
        return False

    @classmethod
    def _theme_follow_up_request(cls, prompt: str) -> dict[str, str] | None:
        if cls._is_dark_theme_request(prompt):
            return {
                "name": "executive-dark",
                "background": "#0B1220",
                "slide_background": "#111827",
                "text": "#F9FAFB",
                "accent": "#38BDF8",
            }
        if cls._is_light_theme_request(prompt):
            return {
                "name": "executive-consulting",
                "background": "#EEF2F7",
                "slide_background": "#FFFFFF",
                "text": "#111827",
                "accent": "#2563EB",
            }
        return None

    @staticmethod
    def _slide_move_request(prompt: str) -> tuple[int | str, str, int | str] | None:
        target_pattern = (
            r"(?:(?P<{prefix}_target>first|last)\s+(?:slide|page)|"
            r"(?P<{prefix}_ordinal>second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth)\s+(?:slide|page)|"
            r"(?:slide|page)\s+(?P<{prefix}_number>\d+))"
        )
        match = re.search(
            r"\bmove\s+(?:the\s+)?"
            + target_pattern.format(prefix="source")
            + r"\s+(?P<position>before|after)\s+(?:the\s+)?"
            + target_pattern.format(prefix="target")
            + r"\b",
            prompt,
            flags=re.IGNORECASE,
        )
        if match is None:
            match = re.search(
                r"\bmove\s+(?:the\s+)?"
                + target_pattern.format(prefix="source")
                + r"\s+to\s+(?:the\s+)?(?P<edge>beginning|start|front|end|back)\b",
                prompt,
                flags=re.IGNORECASE,
            )
            if match is None:
                return None
            edge = match.group("edge").casefold()
            return (
                AgentSession._slide_target_from_match(match, "source"),
                "before" if edge in {"beginning", "start", "front"} else "after",
                "first" if edge in {"beginning", "start", "front"} else "last",
            )
        return (
            AgentSession._slide_target_from_match(match, "source"),
            match.group("position").casefold(),
            AgentSession._slide_target_from_match(match, "target"),
        )

    @staticmethod
    def _slide_target_from_match(match: re.Match[str], prefix: str) -> int | str:
        number = match.group(f"{prefix}_number")
        if number is not None:
            return max(1, int(number))
        ordinal = match.group(f"{prefix}_ordinal")
        if ordinal is not None:
            return AgentSession._ordinal_value(ordinal)
        return match.group(f"{prefix}_target").casefold()

    @staticmethod
    def _deck_title_update_request(prompt: str) -> str | None:
        match = re.search(
            r"\b(?:rename|update)\s+(?:the\s+)?(?:deck|presentation|powerpoint|ppt)\s+(?:title\s+)?(?:to|as)\s+(?P<title>.+)$",
            prompt,
            flags=re.IGNORECASE,
        )
        if match is None:
            match = re.search(
                r"\bchange\s+(?:the\s+)?(?:deck|presentation|powerpoint|ppt)\s+title\s+to\s+(?P<title>.+)$",
                prompt,
                flags=re.IGNORECASE,
            )
        if match is None:
            return None
        title = match.group("title").strip(" .:-")
        return title[:80] if title else None

    @staticmethod
    def _deck_metadata_update_request(prompt: str) -> tuple[str, str] | None:
        match = re.search(
            r"\b(?:set|update|change)\s+(?:the\s+)?(?:(?:deck|presentation|powerpoint|ppt)\s+)?(?P<key>audience|style)\s+(?:to|as)\s+(?P<value>.+)$",
            prompt,
            flags=re.IGNORECASE,
        )
        if match is None:
            return None
        value = match.group("value").strip(" .:-")
        if not value:
            return None
        return match.group("key").casefold(), value[:80]

    @staticmethod
    def _slide_title_update_request(prompt: str) -> tuple[int | str, str] | None:
        match = re.search(
            r"\b(?:update|rename)\s+(?:the\s+)?(?:(?P<target>first|last)\s+slide|(?P<ordinal>second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth)\s+(?:slide|page)|(?:slide|page)\s+(?P<number>\d+))\s+(?:title\s+)?(?:to|as)\s+(?P<title>.+)$",
            prompt,
            flags=re.IGNORECASE,
        )
        if match is None:
            return None

        title = match.group("title").strip(" .:-")
        if not title:
            return None
        number = match.group("number")
        if number is not None:
            return max(1, int(number)), title[:80]
        ordinal = match.group("ordinal")
        if ordinal is not None:
            return AgentSession._ordinal_value(ordinal), title[:80]
        return match.group("target").casefold(), title[:80]

    @staticmethod
    def _follow_up_slide_title(prompt: str) -> str:
        prompt = re.sub(
            r"\b(?:after|before)\s+(?:the\s+)?(?:(?:first|last)\s+(?:slide|page)|(?:second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth)\s+(?:slide|page)|(?:slide|page)\s+\d+)\b",
            " ",
            prompt,
            flags=re.IGNORECASE,
        )
        prompt = re.sub(
            r"\b(?:to|at)\s+(?:the\s+)?(?:beginning|start|front|end|back)\b",
            " ",
            prompt,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(
            r"\b(please|add|append|create|a|an|slide|page|about)\b",
            " ",
            prompt,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" .:-")
        return cleaned.title()[:80] if cleaned else "Additional Insight"

    @staticmethod
    def _safe_artifact_name(value: str) -> str:
        cleaned = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in value.strip())
        return cleaned or "deck"
