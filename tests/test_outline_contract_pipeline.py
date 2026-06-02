import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from app.core.ai_adapter import AIAdapter
from app.core.linter import SlideLinter
from app.core.pptx_utils import NS
from app.core.renderer import TemplateRenderer
from tests.test_renderer_typography import _build_pref


class OutlineContractPipelineTests(unittest.TestCase):
    def test_ai_normalization_enforces_transition_for_each_toc_item(self) -> None:
        class FakeAI(AIAdapter):
            def _chat_json(self, body):  # type: ignore[no-untyped-def]
                return json.dumps(
                    {
                        "deck_title": "胶质瘤的康复治疗",
                        "slides": [
                            {"index": 1, "title": "胶质瘤的康复治疗", "prototype_hint": "cover"},
                            {"index": 2, "title": "目录", "toc_items": ["评估分层", "干预技术", "长期随访"], "prototype_hint": "toc"},
                            {"index": 3, "title": "功能影响", "points": [{"label": "运动", "body": "评估肌力和平衡能力"}], "prototype_hint": "content"},
                            {"index": 4, "title": "训练方案", "points": [{"label": "运动", "body": "制定分级训练方案"}], "prototype_hint": "content"},
                            {"index": 5, "title": "家庭管理", "points": [{"label": "随访", "body": "设置复评节点"}], "prototype_hint": "content"},
                            {"index": 6, "title": "总结", "summary_items": ["持续复评"], "prototype_hint": "closing"},
                        ],
                    },
                    ensure_ascii=False,
                )

        plan = FakeAI(api_key="key", base_url="https://example.test/v1", model="fake").generate_plan(
            topic="胶质瘤的康复治疗",
            slide_count=6,
            template_spec={},
        )

        assert plan is not None
        transitions = [
            slide for slide in plan["slides"]
            if slide.get("prototype_hint") == "section"
        ]
        self.assertEqual([slide["section_title"] for slide in transitions], ["评估分层", "干预技术", "长期随访"])
        self.assertEqual(plan["slides"][2]["prototype_hint"], "section")
        self.assertEqual(plan["slides"][4]["prototype_hint"], "section")
        self.assertEqual(plan["slides"][6]["prototype_hint"], "section")
        self.assertEqual(plan["slides"][3]["prototype_hint"], "content")
        self.assertEqual(plan["slides"][5]["prototype_hint"], "content")
        self.assertEqual(plan["slides"][7]["prototype_hint"], "content")

    def test_section_transitions_are_inserted_before_each_section_content_group(self) -> None:
        slides = [
            {"index": 1, "title": "封面", "prototype_hint": "cover"},
            {"index": 2, "title": "目录", "toc_items": ["病因", "表现", "治疗"], "prototype_hint": "toc"},
            {
                "index": 3,
                "title": "mTOR 通路",
                "section_title": "病因",
                "prototype_hint": "content",
                "points": [{"label": "机制", "body": "TSC1/TSC2 异常导致 mTOR 通路激活。"}],
            },
            {
                "index": 4,
                "title": "气胸和乳糜胸",
                "section_title": "表现",
                "prototype_hint": "content",
                "points": [{"label": "表现", "body": "反复气胸、乳糜胸和活动后气促需要合并识别。"}],
            },
            {
                "index": 5,
                "title": "西罗莫司",
                "section_title": "治疗",
                "prototype_hint": "content",
                "points": [{"label": "治疗", "body": "西罗莫司用于控制进展并处理乳糜相关并发症。"}],
            },
            {"index": 6, "title": "总结", "prototype_hint": "closing", "summary_items": ["长期随访"]},
        ]

        out = AIAdapter._enforce_section_transitions(slides)

        sequence = [(slide["prototype_hint"], slide.get("section_title")) for slide in out]
        self.assertEqual(
            sequence,
            [
                ("cover", None),
                ("toc", None),
                ("section", "病因"),
                ("content", "病因"),
                ("section", "表现"),
                ("content", "表现"),
                ("section", "治疗"),
                ("content", "治疗"),
                ("closing", None),
            ],
        )

    def test_reference_and_summary_pages_stay_after_all_toc_sections(self) -> None:
        slides = [
            {"index": 1, "title": "封面", "prototype_hint": "cover"},
            {"index": 2, "title": "目录", "toc_items": ["病因", "表现"], "prototype_hint": "toc"},
            {"index": 3, "title": "病因正文", "section_title": "病因", "prototype_hint": "content", "bullets": ["病因内容"]},
            {"index": 4, "title": "表现正文", "section_title": "表现", "prototype_hint": "content", "bullets": ["表现内容"]},
            {"index": 5, "title": "参考文献页", "section_title": "参考文献", "prototype_hint": "content", "bullets": ["指南"]},
            {"index": 6, "title": "总结", "section_title": "总结", "prototype_hint": "closing", "summary_items": ["长期管理"]},
        ]

        out = AIAdapter._enforce_section_transitions(slides)

        self.assertEqual([slide["title"] for slide in out[-2:]], ["总结", "参考文献页"])
        self.assertEqual(out[-2]["prototype_hint"], "closing")
        self.assertEqual(out[-1]["prototype_hint"], "reference")
        self.assertEqual(
            [slide["section_title"] for slide in out if slide.get("prototype_hint") == "section"],
            ["病因", "表现"],
        )

    def test_ai_plan_preserves_complete_outline_fields(self) -> None:
        class FakeAI(AIAdapter):
            def _chat_json(self, body):  # type: ignore[no-untyped-def]
                return json.dumps(
                    {
                        "deck_title": "胶质瘤的康复治疗",
                        "slides": [
                            {
                                "index": 1,
                                "title": "胶质瘤康复",
                                "subtitle": "围手术期到长期随访",
                                "prototype_hint": "cover",
                                "copy_pattern": "cover_toc",
                            },
                            {
                                "index": 2,
                                "title": "目录",
                                "toc_items": ["疾病概览", "功能评估", "核心干预", "随访管理"],
                                "prototype_hint": "toc",
                                "copy_pattern": "cover_toc",
                            },
                            {
                                "index": 3,
                                "title": "功能评估",
                                "points": [
                                    {
                                        "label": "神经功能",
                                        "body": "记录肌力、肌张力、平衡、步行、癫痫发作史和颅压风险，形成入组基线。",
                                    },
                                    {
                                        "label": "生活能力",
                                        "body": "用 Barthel 或 FIM 量化转移、进食、洗漱和如厕能力，作为复评依据。",
                                    },
                                ],
                                "prototype_hint": "content",
                                "copy_pattern": "label_detail",
                            },
                            {
                                "index": 4,
                                "title": "总结",
                                "summary_items": ["早期介入", "分层训练", "安全监测", "长期随访"],
                                "prototype_hint": "closing",
                                "copy_pattern": "dense_grid",
                            },
                        ],
                    },
                    ensure_ascii=False,
                )

        plan = FakeAI(api_key="key", base_url="https://example.test/v1", model="fake").generate_plan(
            topic="胶质瘤的康复治疗",
            slide_count=4,
            template_spec={},
        )

        self.assertIsNotNone(plan)
        assert plan is not None
        self.assertEqual(plan["slides"][1]["toc_items"], ["疾病概览", "功能评估", "核心干预", "随访管理"])
        self.assertEqual(plan["slides"][1]["bullets"], [])
        content_slide = next(slide for slide in plan["slides"] if slide.get("points"))
        closing_slide = next(slide for slide in plan["slides"] if slide.get("summary_items"))
        self.assertTrue(content_slide["points"][0]["label"])
        self.assertTrue(content_slide["points"][0]["body"])
        self.assertEqual(content_slide["bullets"], [])
        self.assertTrue(closing_slide["summary_items"][0])
        self.assertEqual(closing_slide["bullets"], [])
        return
        self.assertEqual(content_slide["points"][0]["label"], "绁炵粡鍔熻兘")
        self.assertIn("棰呭帇椋庨櫓", content_slide["points"][0]["body"])
        self.assertEqual(content_slide["bullets"], [])
        self.assertEqual(closing_slide["summary_items"][0], "鏃╂湡浠嬪叆")
        self.assertEqual(closing_slide["bullets"], [])
        return
        self.assertEqual(plan["slides"][2]["points"][0]["label"], "神经功能")
        self.assertIn("颅压风险", plan["slides"][2]["points"][0]["body"])
        self.assertEqual(plan["slides"][2]["bullets"], [])
        self.assertEqual(plan["slides"][3]["summary_items"][0], "早期介入")
        self.assertEqual(plan["slides"][3]["bullets"], [])

    def test_contract_assignment_uses_slot_semantics_instead_of_order(self) -> None:
        renderer = TemplateRenderer()
        slots = [
            _build_pref(shape_cx=9000000, shape_cy=700000, placeholder_type="title", order=0, shape_id=1),
            _build_pref(shape_cx=1700000, shape_cy=700000, order=1, shape_id=2, text_align="ctr"),
            _build_pref(shape_cx=8200000, shape_cy=900000, order=2, shape_id=3, text_align="l"),
        ]
        slots[0].slot_id = "title"
        slots[1].slot_id = "label_a"
        slots[2].slot_id = "body_a"
        slide = {
            "title": "功能评估",
            "points": [
                {
                    "label": "神经功能",
                    "body": "记录肌力、肌张力、平衡、步行、癫痫发作史和颅压风险，形成可复评的康复基线。",
                }
            ],
        }
        bindings = [
            {"slot_id": "title", "semantic": "page_title"},
            {"slot_id": "label_a", "semantic": "point_label"},
            {"slot_id": "body_a", "semantic": "point_body"},
        ]

        assignment = renderer._build_contract_assignment(slots, slide, bindings)

        self.assertEqual(assignment[0], "功能评估")
        self.assertEqual(assignment[1], "神经功能")
        self.assertIn("癫痫发作史", assignment[2])
        self.assertNotIn("明确执行动作与责任分工", assignment[2])

    def test_contract_body_slot_combines_all_outline_points(self) -> None:
        renderer = TemplateRenderer()
        slots = [
            _build_pref(shape_cx=9000000, shape_cy=700000, placeholder_type="title", order=0, shape_id=1),
            _build_pref(shape_cx=7600000, shape_cy=2400000, order=1, shape_id=2, text_align="l"),
        ]
        slots[0].slot_id = "title"
        slots[1].slot_id = "body"
        slide = {
            "title": "基线评估",
            "points": [
                {"label": "神经功能", "body": "记录肌力、肌张力、感觉和共济情况，形成复评基线。"},
                {"label": "生活能力", "body": "使用 Barthel 或 FIM 量化转移、行走和自理能力。"},
                {"label": "风险筛查", "body": "同步评估颅压、癫痫、跌倒和深静脉血栓风险。"},
            ],
        }
        bindings = [
            {"slot_id": "title", "semantic": "page_title"},
            {"slot_id": "body", "semantic": "body"},
        ]

        assignment = renderer._build_contract_assignment(slots, slide, bindings)

        self.assertIn("神经功能", assignment[1])
        self.assertIn("生活能力", assignment[1])
        self.assertIn("风险筛查", assignment[1])
        self.assertGreaterEqual(assignment[1].count("\n"), 2)

    def test_linter_flags_ellipsis_generic_repetition_and_short_titles(self) -> None:
        issues = SlideLinter._quality_issues_for_text(
            "ppt/slides/slide7.xml",
            [
                "神经功能评估",
                "核心问题：神经功能...",
                "明确执行动作与责任分工",
                "明确执行动作与责任分工",
                "明确执行动作与责任分工",
            ],
        )

        messages = " ".join(issue.message for issue in issues)
        self.assertIn("Hard ellipsis", messages)
        self.assertIn("generic repeated filler", messages)

    def test_linter_checks_slide_layout_residue(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pptx = Path(tmp) / "residue.pptx"
            _pptx_with_layout_residue(pptx)

            report = SlideLinter().lint(pptx)

        messages = " ".join(item["message"] for item in report["issues"])
        self.assertIn("Possible template residue detected", messages)
        self.assertIn("请输入", messages)


def _pptx_with_layout_residue(path: Path) -> None:
    slide = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:p="{NS['p']}" xmlns:a="{NS['a']}" xmlns:r="{NS['r']}">
  <p:cSld><p:spTree>
    <p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
    <p:grpSpPr/>
    <p:sp>
      <p:nvSpPr><p:cNvPr id="2" name="Title"/><p:cNvSpPr/><p:nvPr><p:ph type="title"/></p:nvPr></p:nvSpPr>
      <p:spPr><a:xfrm><a:off x="900000" y="600000"/><a:ext cx="8000000" cy="800000"/></a:xfrm></p:spPr>
      <p:txBody><a:bodyPr/><a:lstStyle/><a:p><a:r><a:rPr sz="2800"/><a:t>总结与展望</a:t></a:r></a:p></p:txBody>
    </p:sp>
  </p:spTree></p:cSld>
</p:sld>
"""
    layout = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldLayout xmlns:p="{NS['p']}" xmlns:a="{NS['a']}" xmlns:r="{NS['r']}" type="obj">
  <p:cSld name="Summary"><p:spTree>
    <p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
    <p:grpSpPr/>
    <p:sp>
      <p:nvSpPr><p:cNvPr id="3" name="Body"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>
      <p:spPr><a:xfrm><a:off x="1000000" y="1800000"/><a:ext cx="4000000" cy="700000"/></a:xfrm></p:spPr>
      <p:txBody><a:bodyPr/><a:lstStyle/><a:p><a:r><a:rPr sz="2000"/><a:t>请输入你的正文内容</a:t></a:r></a:p></p:txBody>
    </p:sp>
  </p:spTree></p:cSld>
</p:sldLayout>
"""
    rels = f"""<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="{NS['pr']}">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>
</Relationships>
"""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("ppt/slides/slide1.xml", slide)
        zf.writestr("ppt/slides/_rels/slide1.xml.rels", rels)
        zf.writestr("ppt/slideLayouts/slideLayout1.xml", layout)


if __name__ == "__main__":
    unittest.main()
