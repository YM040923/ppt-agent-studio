import pytest

from ppt_agent_studio.planning.plan import DeckPlan


def test_deck_plan_from_outline_creates_default_steps():
    outline = {
        "deck_title": "AI Strategy",
        "slides": [
            {"title": "AI Strategy"},
            {"title": "Operating Model"},
        ],
    }

    plan = DeckPlan.from_outline(outline, plan_id="plan_001")

    assert plan.to_dict() == {
        "plan_id": "plan_001",
        "title": "AI Strategy",
        "status": "pending",
        "slide_count": 2,
        "steps": [
            {
                "step_id": "research_context",
                "title": "Research context",
                "status": "pending",
                "detail": "Gather audience, objective, market, and source context.",
            },
            {
                "step_id": "structure_story",
                "title": "Structure story",
                "status": "pending",
                "detail": "Shape the executive narrative and slide sequence.",
            },
            {
                "step_id": "draft_slides",
                "title": "Draft 2 slides",
                "status": "pending",
                "detail": "Create DeckSpec slides from the approved outline.",
            },
            {
                "step_id": "render_preview",
                "title": "Render preview",
                "status": "pending",
                "detail": "Refresh the live HTML preview from DeckSpec.",
            },
            {
                "step_id": "export_pptx",
                "title": "Export editable PPTX",
                "status": "pending",
                "detail": "Write the editable PowerPoint artifact.",
            },
        ],
    }


def test_deck_plan_updates_step_status():
    plan = DeckPlan.from_outline({"deck_title": "Sales Plan", "slides": []}, plan_id="plan_002")

    plan.update_step_status("draft_slides", "running")

    draft_step = next(step for step in plan.to_dict()["steps"] if step["step_id"] == "draft_slides")
    assert draft_step["status"] == "running"

    with pytest.raises(ValueError, match="Unknown plan step"):
        plan.update_step_status("missing", "done")
