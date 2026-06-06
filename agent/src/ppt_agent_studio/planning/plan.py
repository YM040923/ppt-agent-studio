from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PlanStep:
    step_id: str
    title: str
    detail: str
    status: str = "pending"

    def to_dict(self) -> dict[str, str]:
        return {
            "step_id": self.step_id,
            "title": self.title,
            "status": self.status,
            "detail": self.detail,
        }


@dataclass
class DeckPlan:
    plan_id: str
    title: str
    slide_count: int
    steps: list[PlanStep]
    status: str = "pending"

    @classmethod
    def from_outline(cls, outline: dict[str, object], plan_id: str) -> DeckPlan:
        title = str(outline.get("deck_title") or "Untitled Deck")
        raw_slides = outline.get("slides")
        slide_count = len(raw_slides) if isinstance(raw_slides, list) else 0
        return cls(
            plan_id=plan_id,
            title=title,
            slide_count=slide_count,
            steps=[
                PlanStep(
                    step_id="research_context",
                    title="Research context",
                    detail="Gather audience, objective, market, and source context.",
                ),
                PlanStep(
                    step_id="structure_story",
                    title="Structure story",
                    detail="Shape the executive narrative and slide sequence.",
                ),
                PlanStep(
                    step_id="draft_slides",
                    title=f"Draft {slide_count} slides",
                    detail="Create DeckSpec slides from the approved outline.",
                ),
                PlanStep(
                    step_id="render_preview",
                    title="Render preview",
                    detail="Refresh the live HTML preview from DeckSpec.",
                ),
                PlanStep(
                    step_id="export_pptx",
                    title="Export editable PPTX",
                    detail="Write the editable PowerPoint artifact.",
                ),
            ],
        )

    def update_step_status(self, step_id: str, status: str) -> None:
        for step in self.steps:
            if step.step_id == step_id:
                step.status = status
                return
        raise ValueError(f"Unknown plan step: {step_id}")

    def to_dict(self) -> dict[str, object]:
        return {
            "plan_id": self.plan_id,
            "title": self.title,
            "status": self.status,
            "slide_count": self.slide_count,
            "steps": [step.to_dict() for step in self.steps],
        }
