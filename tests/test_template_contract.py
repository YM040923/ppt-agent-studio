import tempfile
import unittest
import zipfile
import json
from pathlib import Path

from app.core.ai_adapter import AIAdapter
from app.core.pptx_utils import NS
from app.core.renderer import TemplateRenderer
from app.core.template_normalizer import TemplateNormalizer
from app.service import GenerationService
from tests.test_renderer_typography import _build_pref


def _minimal_pptx(path: Path) -> None:
    slide = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:p="{NS['p']}" xmlns:a="{NS['a']}" xmlns:r="{NS['r']}">
  <p:cSld>
    <p:spTree>
      <p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
      <p:grpSpPr/>
      <p:sp>
        <p:nvSpPr><p:cNvPr id="2" name="Title"/><p:cNvSpPr/><p:nvPr><p:ph type="title"/></p:nvPr></p:nvSpPr>
        <p:spPr><a:xfrm><a:off x="900000" y="760000"/><a:ext cx="8000000" cy="900000"/></a:xfrm></p:spPr>
        <p:txBody><a:bodyPr/><a:lstStyle/><a:p><a:pPr algn="ctr"/><a:r><a:rPr sz="4400" b="1"><a:latin typeface="Aptos Display"/><a:ea typeface="微软雅黑"/></a:rPr><a:t>封面标题</a:t></a:r></a:p></p:txBody>
      </p:sp>
      <p:sp>
        <p:nvSpPr><p:cNvPr id="3" name="Reporter"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>
        <p:spPr><a:xfrm><a:off x="2600000" y="5150000"/><a:ext cx="4200000" cy="520000"/></a:xfrm></p:spPr>
        <p:txBody><a:bodyPr/><a:lstStyle/><a:p><a:pPr algn="ctr"/><a:r><a:rPr sz="1800"><a:latin typeface="Aptos"/><a:ea typeface="等线"/></a:rPr><a:t>汇报人：张三</a:t></a:r></a:p></p:txBody>
      </p:sp>
    </p:spTree>
  </p:cSld>
</p:sld>
"""
    layout = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldLayout xmlns:p="{NS['p']}" xmlns:a="{NS['a']}" type="title">
  <p:cSld name="Title Slide"><p:spTree/></p:cSld>
</p:sldLayout>
"""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("ppt/slides/slide1.xml", slide)
        zf.writestr("ppt/slideLayouts/slideLayout1.xml", layout)
        zf.writestr(
            "ppt/slides/_rels/slide1.xml.rels",
            f"""<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="{NS['pr']}">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>
</Relationships>
""",
        )


class TemplateContractTests(unittest.TestCase):
    def test_normalizer_records_text_slots_with_typography(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pptx = Path(tmp) / "template.pptx"
            _minimal_pptx(pptx)

            spec = TemplateNormalizer().normalize("tid", "template.pptx", pptx)

        prototype = spec["prototypes"][0]
        slots = prototype["text_slots"]
        self.assertEqual(len(slots), 2)
        title = slots[0]
        self.assertEqual(title["role_hint"], "cover_title")
        self.assertEqual(title["font_size_pt"], 44)
        self.assertEqual(title["font_face"], "微软雅黑")
        self.assertTrue(title["bold"])
        reporter = slots[1]
        self.assertEqual(reporter["role_hint"], "meta")
        self.assertEqual(reporter["font_size_pt"], 18)
        self.assertEqual(reporter["text"], "汇报人：张三")

    def test_ai_standardization_keeps_deck_flow_and_slot_bindings(self) -> None:
        class FakeAI(AIAdapter):
            def _chat_json(self, body):  # type: ignore[no-untyped-def]
                return """
                {
                  "summary": "已识别封面、目录、过渡页、正文页和结束页",
                  "deck_flow": ["cover", "toc", "section", "content", "closing"],
                  "layout_roles": [{"layout": "Title Slide", "role": "cover", "confidence": 0.95}],
                  "slide_routes": [{"prototype_index": 1, "role": "cover", "copy_pattern": "cover_toc"}],
                  "slot_bindings": [
                    {"prototype_index": 1, "slot_id": "s1", "semantic": "deck_title", "min_font_size_pt": 28}
                  ],
                  "content_rules": {
                    "min_body_font_size_pt": 16,
                    "toc_title_max_chars": 14,
                    "prefer_varied_content_layouts": true
                  },
                  "normalization_notes": ["封面标题保持大字号"]
                }
                """

        adapter = FakeAI(api_key="key", base_url="https://example.test/v1", model="fake")
        result = adapter.standardize_template(
            {
                "layouts": [{"name": "Title Slide", "layout_type": "title", "placeholder_count": 2}],
                "prototypes": [{"index": 1, "text_slots": [{"slot_id": "s1", "role_hint": "cover_title"}]}],
            }
        )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result["deck_flow"], ["cover", "toc", "section", "content", "closing"])
        self.assertEqual(result["slot_bindings"][0]["semantic"], "deck_title")
        self.assertEqual(result["content_rules"]["min_body_font_size_pt"], 16)

    def test_single_line_body_text_never_shrinks_below_16pt(self) -> None:
        renderer = TemplateRenderer()
        pref = _build_pref(shape_cx=1500000, shape_cy=520000, font_size=2400)

        renderer._set_paragraph_text(pref, "复杂主题下的正文小标题")

        rpr = pref.para.find(".//a:rPr", NS)
        self.assertIsNotNone(rpr)
        self.assertGreaterEqual(int(rpr.attrib.get("sz", "0")), 1600)

    def test_generation_prompt_receives_template_contract(self) -> None:
        class CapturingAI(AIAdapter):
            def __init__(self) -> None:
                super().__init__(api_key="key", base_url="https://example.test/v1", model="fake")
                self.prompt = {}

            def _chat_json(self, body):  # type: ignore[no-untyped-def]
                self.prompt = json.loads(body["messages"][1]["content"])
                return json.dumps(
                    {
                        "deck_title": "测试主题",
                        "slides": [
                            {"index": 1, "title": "测试主题", "bullets": ["汇报人：张三"], "prototype_hint": "cover", "copy_pattern": "cover_toc"},
                            {"index": 2, "title": "目录", "bullets": ["第一部分", "第二部分"], "prototype_hint": "toc", "copy_pattern": "cover_toc"},
                            {"index": 3, "title": "第一部分", "bullets": ["要点：说明"], "prototype_hint": "section", "copy_pattern": "general"},
                        ],
                    },
                    ensure_ascii=False,
                )

        adapter = CapturingAI()
        adapter.generate_plan(
            topic="测试主题",
            slide_count=3,
            template_spec={
                "ai_standardization": {
                    "deck_flow": ["cover", "toc", "section", "content", "closing"],
                    "slot_bindings": [{"prototype_index": 1, "slot_id": "s1", "semantic": "deck_title"}],
                    "content_rules": {"min_body_font_size_pt": 16, "toc_title_max_chars": 14},
                },
                "prototypes": [{"index": 1, "text_slots": [{"slot_id": "s1", "role_hint": "cover_title", "font_size_pt": 44}]}],
            },
        )

        self.assertIn("template_contract", adapter.prompt)
        self.assertEqual(adapter.prompt["template_contract"]["deck_flow"][0], "cover")
        self.assertEqual(adapter.prompt["template_contract"]["content_rules"]["min_body_font_size_pt"], 16)
        self.assertEqual(adapter.prompt["template_contract"]["slot_bindings"][0]["semantic"], "deck_title")

    def test_generation_prompt_requires_case_driven_complete_outline_not_encyclopedia(self) -> None:
        class CapturingAI(AIAdapter):
            def __init__(self) -> None:
                super().__init__(api_key="key", base_url="https://example.test/v1", model="fake")
                self.prompt = {}
                self.system_prompt = ""

            def _chat_json(self, body):  # type: ignore[no-untyped-def]
                self.system_prompt = body["messages"][0]["content"]
                self.prompt = json.loads(body["messages"][1]["content"])
                return json.dumps(
                    {
                        "deck_title": "肺淋巴管平滑肌瘤病（LAM）",
                        "slides": [
                            {"index": 1, "title": "肺淋巴管平滑肌瘤病（LAM）", "prototype_hint": "cover"},
                            {"index": 2, "title": "目录", "toc_items": ["疾病概述"], "prototype_hint": "toc"},
                            {"index": 3, "title": "疾病概述", "prototype_hint": "section"},
                        ],
                    },
                    ensure_ascii=False,
                )

        adapter = CapturingAI()
        adapter.generate_plan(
            topic="肺淋巴管平滑肌瘤病（LAM）的病因、临床表现与治疗",
            slide_count=15,
            template_spec={},
            audience="PBL 病例汇报",
            tone="临床教学",
        )

        rules = "\n".join(adapter.prompt["rules"])
        self.assertIn("终极大纲", rules)
        self.assertIn("病例线索", rules)
        self.assertIn("疾病概述/病因机制/临床诊断/治疗随访", rules)
        self.assertIn("55-90", rules)
        self.assertIn("every toc_items entry must have one matching section transition", rules)
        self.assertIn("complete outline", adapter.system_prompt.lower())

    def test_copy_patterns_do_not_override_ai_layout_choice(self) -> None:
        plan = {
            "slides": [
                {"index": 1, "title": "封面", "bullets": [], "copy_pattern": "cover_toc"},
                {"index": 2, "title": "目录", "bullets": [], "copy_pattern": "cover_toc"},
                {"index": 3, "title": "三点正文", "bullets": ["A", "B", "C"], "copy_pattern": "label_detail"},
            ]
        }
        copy_patterns = [
            {"index": 3, "copy_pattern": "dense_grid"},
        ]

        out = GenerationService._apply_copy_patterns(plan, copy_patterns)

        self.assertEqual(out["slides"][2]["copy_pattern"], "label_detail")

    def test_template_routes_are_written_into_plan_for_renderer(self) -> None:
        plan = {
            "slides": [
                {"index": 1, "title": "胶质瘤康复", "prototype_hint": "cover", "copy_pattern": "cover_toc"},
                {"index": 2, "title": "目录", "toc_items": ["疾病概览", "功能评估"], "prototype_hint": "toc"},
                {
                    "index": 3,
                    "title": "功能评估",
                    "points": [{"label": "运动", "body": "记录肌力、步态和平衡能力，形成复评基线。"}],
                    "prototype_hint": "content",
                    "copy_pattern": "label_detail",
                },
            ]
        }
        template = {
            "spec": {
                "prototypes": [
                    {
                        "index": 6,
                        "text_slots": [
                            {"slot_id": "l1", "role_hint": "body", "x": 0, "y": 0, "cx": 100, "cy": 100},
                            {"slot_id": "b1", "role_hint": "body", "x": 100, "y": 0, "cx": 100, "cy": 100},
                            {"slot_id": "l2", "role_hint": "body", "x": 0, "y": 100, "cx": 100, "cy": 100},
                            {"slot_id": "b2", "role_hint": "body", "x": 100, "y": 100, "cx": 100, "cy": 100},
                        ],
                    },
                    {
                        "index": 10,
                        "text_slots": [
                            {"slot_id": "l1", "role_hint": "body", "x": 0, "y": 0, "cx": 100, "cy": 100},
                            {"slot_id": "b1", "role_hint": "body", "x": 100, "y": 0, "cx": 100, "cy": 100},
                            {"slot_id": "l2", "role_hint": "body", "x": 0, "y": 100, "cx": 100, "cy": 100},
                            {"slot_id": "b2", "role_hint": "body", "x": 100, "y": 100, "cx": 100, "cy": 100},
                            {"slot_id": "l3", "role_hint": "body", "x": 0, "y": 200, "cx": 100, "cy": 100},
                            {"slot_id": "b3", "role_hint": "body", "x": 100, "y": 200, "cx": 100, "cy": 100},
                            {"slot_id": "l4", "role_hint": "body", "x": 0, "y": 300, "cx": 100, "cy": 100},
                            {"slot_id": "b4", "role_hint": "body", "x": 100, "y": 300, "cx": 100, "cy": 100},
                        ],
                    },
                ],
                "ai_standardization": {
                    "slide_routes": [
                        {"prototype_index": 4, "role": "content", "copy_pattern": "label_detail"},
                        {"prototype_index": 1, "role": "cover", "copy_pattern": "cover_toc"},
                        {"prototype_index": 2, "role": "toc", "copy_pattern": "cover_toc"},
                    ]
                }
            }
        }

        out = GenerationService._apply_template_routes(plan, template, copy_patterns=[])

        self.assertEqual(out["slides"][0]["prototype_index"], 1)
        self.assertEqual(out["slides"][1]["prototype_index"], 2)
        self.assertEqual(out["slides"][2]["prototype_index"], 4)
        self.assertEqual(out["slides"][2]["copy_pattern"], "label_detail")

    def test_content_routes_use_available_layouts_before_reusing_one(self) -> None:
        plan = {
            "slides": [
                {"index": 1, "title": "Cover", "prototype_hint": "cover", "copy_pattern": "cover_toc"},
                {"index": 2, "title": "Toc", "toc_items": [], "prototype_hint": "toc"},
                *[
                    {
                        "index": i,
                        "title": f"Content {i}",
                        "points": [
                            {"label": "A", "body": "detail"},
                            {"label": "B", "body": "detail"},
                            {"label": "C", "body": "detail"},
                        ],
                        "prototype_hint": "content",
                        "copy_pattern": "label_detail",
                    }
                    for i in range(3, 9)
                ],
            ]
        }
        template = {
            "spec": {
                "prototypes": [
                    {
                        "index": 6,
                        "text_slots": [
                            {"slot_id": "l1", "role_hint": "body", "x": 0, "y": 0, "cx": 100, "cy": 100},
                            {"slot_id": "b1", "role_hint": "body", "x": 100, "y": 0, "cx": 100, "cy": 100},
                            {"slot_id": "l2", "role_hint": "body", "x": 0, "y": 100, "cx": 100, "cy": 100},
                            {"slot_id": "b2", "role_hint": "body", "x": 100, "y": 100, "cx": 100, "cy": 100},
                        ],
                    },
                    {
                        "index": 10,
                        "text_slots": [
                            {"slot_id": "l1", "role_hint": "body", "x": 0, "y": 0, "cx": 100, "cy": 100},
                            {"slot_id": "b1", "role_hint": "body", "x": 100, "y": 0, "cx": 100, "cy": 100},
                            {"slot_id": "l2", "role_hint": "body", "x": 0, "y": 100, "cx": 100, "cy": 100},
                            {"slot_id": "b2", "role_hint": "body", "x": 100, "y": 100, "cx": 100, "cy": 100},
                            {"slot_id": "l3", "role_hint": "body", "x": 0, "y": 200, "cx": 100, "cy": 100},
                            {"slot_id": "b3", "role_hint": "body", "x": 100, "y": 200, "cx": 100, "cy": 100},
                            {"slot_id": "l4", "role_hint": "body", "x": 0, "y": 300, "cx": 100, "cy": 100},
                            {"slot_id": "b4", "role_hint": "body", "x": 100, "y": 300, "cx": 100, "cy": 100},
                        ],
                    },
                ],
                "ai_standardization": {
                    "slide_routes": [
                        {"prototype_index": 1, "role": "cover", "copy_pattern": "cover_toc"},
                        {"prototype_index": 2, "role": "toc", "copy_pattern": "cover_toc"},
                        {"prototype_index": 7, "role": "content", "copy_pattern": "label_detail"},
                        {"prototype_index": 8, "role": "dense_grid", "copy_pattern": "dense_grid"},
                        {"prototype_index": 10, "role": "content", "copy_pattern": "label_detail"},
                        {"prototype_index": 11, "role": "dense_grid", "copy_pattern": "dense_grid"},
                        {"prototype_index": 13, "role": "content", "copy_pattern": "label_detail"},
                        {"prototype_index": 14, "role": "content", "copy_pattern": "label_detail"},
                    ]
                }
            }
        }

        out = GenerationService._apply_template_routes(plan, template, copy_patterns=[], force=True)

        content_routes = [slide["prototype_index"] for slide in out["slides"][2:]]
        self.assertGreaterEqual(len(set(content_routes[:4])), 4)
        self.assertNotEqual(content_routes, [7, 7, 7, 7, 7, 7])

    def test_point_heavy_content_can_use_general_routes_for_variety(self) -> None:
        points = [
            {"label": "A", "body": "detail A"},
            {"label": "B", "body": "detail B"},
            {"label": "C", "body": "detail C"},
            {"label": "D", "body": "detail D"},
        ]
        plan = {
            "slides": [
                {"index": 1, "title": "Cover", "prototype_hint": "cover", "copy_pattern": "cover_toc"},
                {"index": 2, "title": "Toc", "toc_items": [], "prototype_hint": "toc"},
                *[
                    {
                        "index": i,
                        "title": f"Point heavy content {i}",
                        "points": [dict(point) for point in points],
                        "prototype_hint": "content",
                        "copy_pattern": "label_detail",
                    }
                    for i in range(3, 10)
                ],
            ]
        }
        large_slots = [
            {"slot_id": "g1", "role_hint": "body", "x": 0, "y": 0, "cx": 9000000, "cy": 4200000},
        ]
        label_detail_slots = []
        bindings = []
        for pair in range(4):
            label_id = f"l{pair}"
            body_id = f"b{pair}"
            label_detail_slots.extend(
                [
                    {"slot_id": label_id, "role_hint": "body", "x": 0, "y": pair * 100, "cx": 1200000, "cy": 500000},
                    {"slot_id": body_id, "role_hint": "body", "x": 1300000, "y": pair * 100, "cx": 5200000, "cy": 500000},
                ]
            )
            bindings.extend(
                [
                    {"prototype_index": 10, "slot_id": label_id, "semantic": "point_label"},
                    {"prototype_index": 10, "slot_id": body_id, "semantic": "point_body"},
                ]
            )
        template = {
            "spec": {
                "prototypes": [
                    {"index": 4, "text_slots": [dict(slot) for slot in large_slots]},
                    {"index": 5, "text_slots": [dict(slot) for slot in large_slots]},
                    {"index": 9, "text_slots": [dict(slot) for slot in large_slots]},
                    {"index": 10, "text_slots": label_detail_slots},
                    {"index": 14, "text_slots": [dict(slot) for slot in large_slots]},
                ],
                "ai_standardization": {
                    "slide_routes": [
                        {"prototype_index": 1, "role": "cover", "copy_pattern": "cover_toc"},
                        {"prototype_index": 2, "role": "toc", "copy_pattern": "cover_toc"},
                        {"prototype_index": 4, "role": "content", "copy_pattern": "general"},
                        {"prototype_index": 5, "role": "content", "copy_pattern": "general"},
                        {"prototype_index": 9, "role": "content", "copy_pattern": "general"},
                        {"prototype_index": 10, "role": "content", "copy_pattern": "label_detail"},
                        {"prototype_index": 14, "role": "content", "copy_pattern": "general"},
                    ],
                    "slot_bindings": bindings,
                },
            }
        }

        out = GenerationService._apply_template_routes(plan, template, copy_patterns=[], force=True)

        content_routes = [slide["prototype_index"] for slide in out["slides"][2:]]
        self.assertGreaterEqual(len(set(content_routes[:5])), 5)
        self.assertIn(10, content_routes[:5])
        self.assertTrue({4, 5, 9, 14}.issubset(set(content_routes[:5])))

    def test_bullet_only_content_converts_to_label_detail_points_for_routed_template(self) -> None:
        label_detail_slots = []
        bindings = []
        for pair in range(4):
            label_id = f"l{pair}"
            body_id = f"b{pair}"
            label_detail_slots.extend(
                [
                    {"slot_id": label_id, "role_hint": "body", "x": 0, "y": pair * 900000, "cx": 1200000, "cy": 500000},
                    {"slot_id": body_id, "role_hint": "body", "x": 1300000, "y": pair * 900000, "cx": 5200000, "cy": 500000},
                ]
            )
            bindings.extend(
                [
                    {"prototype_index": 10, "slot_id": label_id, "semantic": "point_label"},
                    {"prototype_index": 10, "slot_id": body_id, "semantic": "point_body"},
                ]
            )
        plan = {
            "slides": [
                {"index": 1, "title": "Cover", "prototype_hint": "cover"},
                {"index": 2, "title": "Toc", "prototype_hint": "toc"},
                {
                    "index": 3,
                    "title": "Chylothorax signs",
                    "prototype_hint": "content",
                    "copy_pattern": "label_detail",
                    "bullets": [
                        "Pleural effusion: recurrent milky fluid should trigger LAM and lymphatic leakage review.",
                        "Fluid testing: triglyceride elevation and chylomicrons confirm chylothorax rather than simple effusion.",
                        "Management: drainage is only stabilization; recurrence prevention depends on disease-directed therapy.",
                    ],
                },
            ]
        }
        template = {
            "spec": {
                "prototypes": [{"index": 10, "text_slots": label_detail_slots}],
                "ai_standardization": {
                    "slide_routes": [
                        {"prototype_index": 1, "role": "cover", "copy_pattern": "cover_toc"},
                        {"prototype_index": 2, "role": "toc", "copy_pattern": "cover_toc"},
                        {"prototype_index": 10, "role": "content", "copy_pattern": "label_detail"},
                    ],
                    "slot_bindings": bindings,
                },
            }
        }

        out = GenerationService._apply_template_routes(plan, template, copy_patterns=[], force=True)

        routed = out["slides"][2]
        self.assertEqual(routed["prototype_index"], 10)
        self.assertEqual(routed["copy_pattern"], "label_detail")
        self.assertEqual(routed["bullets"], [])
        self.assertGreaterEqual(len(routed["points"]), 3)
        self.assertEqual(routed["points"][0]["label"], "Pleural effusion")
        self.assertIn("recurrent milky fluid", routed["points"][0]["body"])

    def test_label_detail_route_with_footer_body_slot_is_downgraded_for_general_content(self) -> None:
        slides = [
            {"index": 1, "title": "Cover", "prototype_hint": "cover"},
            {"index": 2, "title": "Toc", "prototype_hint": "toc"},
            *[
                {
                    "index": i,
                    "title": f"Content {i}",
                    "prototype_hint": "content",
                    "copy_pattern": "label_detail",
                    "points": [
                        {"label": "A", "body": "detail A"},
                        {"label": "B", "body": "detail B"},
                        {"label": "C", "body": "detail C"},
                        {"label": "D", "body": "detail D"},
                    ],
                }
                for i in range(3, 7)
            ],
        ]
        safe_slots = []
        unsafe_slots = []
        bindings = []
        for prototype_index, target in ((7, unsafe_slots), (10, safe_slots)):
            for pair in range(4):
                label_id = f"l{pair}"
                body_id = f"b{pair}"
                target.extend(
                    [
                        {"slot_id": label_id, "role_hint": "body", "x": 0, "y": pair * 900000, "cx": 1200000, "cy": 500000},
                        {"slot_id": body_id, "role_hint": "body", "x": 1300000, "y": pair * 900000, "cx": 5200000, "cy": 500000},
                    ]
                )
                bindings.extend(
                    [
                        {"prototype_index": prototype_index, "slot_id": label_id, "semantic": "point_label"},
                        {"prototype_index": prototype_index, "slot_id": body_id, "semantic": "point_body"},
                    ]
                )
        unsafe_slots.append({"slot_id": "footer", "role_hint": "body", "x": 600000, "y": 5600000, "cx": 10800000, "cy": 600000})
        bindings.append({"prototype_index": 7, "slot_id": "footer", "semantic": "point_body"})
        template = {
            "spec": {
                "prototypes": [
                    {"index": 7, "text_slots": unsafe_slots},
                    {"index": 10, "text_slots": safe_slots},
                ],
                "ai_standardization": {
                    "slide_routes": [
                        {"prototype_index": 1, "role": "cover", "copy_pattern": "cover_toc"},
                        {"prototype_index": 2, "role": "toc", "copy_pattern": "cover_toc"},
                        {"prototype_index": 7, "role": "content", "copy_pattern": "label_detail"},
                        {"prototype_index": 10, "role": "content", "copy_pattern": "label_detail"},
                    ],
                    "slot_bindings": bindings,
                },
            }
        }

        out = GenerationService._apply_template_routes({"slides": slides}, template, copy_patterns=[], force=True)

        content_routes = [slide["prototype_index"] for slide in out["slides"][2:]]
        self.assertIn(7, content_routes)
        self.assertIn(10, content_routes)
        for slide in out["slides"][2:]:
            if slide["prototype_index"] == 7:
                self.assertEqual(slide["copy_pattern"], "general")

    def test_section_routes_are_reused_for_each_toc_transition(self) -> None:
        plan = {
            "slides": [
                {"index": 1, "title": "Cover", "prototype_hint": "cover", "copy_pattern": "cover_toc"},
                {"index": 2, "title": "Toc", "toc_items": ["A", "B", "C"], "prototype_hint": "toc"},
                {"index": 3, "title": "A", "section_title": "A", "prototype_hint": "section"},
                {"index": 4, "title": "A1", "section_title": "A", "prototype_hint": "content", "points": [{"label": "a", "body": "detail"}]},
                {"index": 5, "title": "B", "section_title": "B", "prototype_hint": "section"},
                {"index": 6, "title": "B1", "section_title": "B", "prototype_hint": "content", "points": [{"label": "b", "body": "detail"}]},
                {"index": 7, "title": "C", "section_title": "C", "prototype_hint": "section"},
                {"index": 8, "title": "C1", "section_title": "C", "prototype_hint": "content", "points": [{"label": "c", "body": "detail"}]},
            ]
        }
        template = {
            "spec": {
                "prototypes": [
                    {
                        "index": 6,
                        "text_slots": [
                            {"slot_id": "l1", "role_hint": "body", "x": 0, "y": 0, "cx": 100, "cy": 100},
                            {"slot_id": "b1", "role_hint": "body", "x": 100, "y": 0, "cx": 100, "cy": 100},
                            {"slot_id": "l2", "role_hint": "body", "x": 0, "y": 100, "cx": 100, "cy": 100},
                            {"slot_id": "b2", "role_hint": "body", "x": 100, "y": 100, "cx": 100, "cy": 100},
                        ],
                    },
                    {
                        "index": 10,
                        "text_slots": [
                            {"slot_id": "l1", "role_hint": "body", "x": 0, "y": 0, "cx": 100, "cy": 100},
                            {"slot_id": "b1", "role_hint": "body", "x": 100, "y": 0, "cx": 100, "cy": 100},
                            {"slot_id": "l2", "role_hint": "body", "x": 0, "y": 100, "cx": 100, "cy": 100},
                            {"slot_id": "b2", "role_hint": "body", "x": 100, "y": 100, "cx": 100, "cy": 100},
                            {"slot_id": "l3", "role_hint": "body", "x": 0, "y": 200, "cx": 100, "cy": 100},
                            {"slot_id": "b3", "role_hint": "body", "x": 100, "y": 200, "cx": 100, "cy": 100},
                            {"slot_id": "l4", "role_hint": "body", "x": 0, "y": 300, "cx": 100, "cy": 100},
                            {"slot_id": "b4", "role_hint": "body", "x": 100, "y": 300, "cx": 100, "cy": 100},
                        ],
                    },
                ],
                "ai_standardization": {
                    "slide_routes": [
                        {"prototype_index": 1, "role": "cover", "copy_pattern": "cover_toc"},
                        {"prototype_index": 2, "role": "toc", "copy_pattern": "cover_toc"},
                        {"prototype_index": 3, "role": "section", "copy_pattern": "general"},
                        {"prototype_index": 7, "role": "content", "copy_pattern": "label_detail"},
                    ]
                }
            }
        }

        out = GenerationService._apply_template_routes(plan, template, copy_patterns=[], force=True)

        section_routes = [
            slide["prototype_index"]
            for slide in out["slides"]
            if slide.get("prototype_hint") == "section"
        ]
        self.assertEqual(section_routes, [3, 3, 3])

    def test_section_route_reuses_visible_transition_before_zero_capacity_route(self) -> None:
        plan = {
            "slides": [
                {"index": 1, "title": "Cover", "prototype_hint": "cover", "copy_pattern": "cover_toc"},
                {"index": 2, "title": "Toc", "toc_items": ["A", "B", "C"], "prototype_hint": "toc"},
                {"index": 3, "title": "A", "section_title": "A", "prototype_hint": "section"},
                {"index": 4, "title": "B", "section_title": "B", "prototype_hint": "section"},
                {"index": 5, "title": "C", "section_title": "C", "prototype_hint": "section"},
            ]
        }
        template = {
            "spec": {
                "prototypes": [
                    {
                        "index": 3,
                        "text_slots": [
                            {"slot_id": "title", "role_hint": "body", "x": 100, "y": 100, "cx": 3000000, "cy": 600000},
                        ],
                    },
                    {
                        "index": 12,
                        "text_slots": [
                            {"slot_id": "title", "role_hint": "page_title", "x": 1000000000, "y": 1000000000, "cx": 0, "cy": 0},
                            {"slot_id": "footer", "role_hint": "body", "x": 1000000000, "y": 1000000000, "cx": 0, "cy": 0},
                        ],
                    },
                ],
                "ai_standardization": {
                    "slide_routes": [
                        {"prototype_index": 1, "role": "cover", "copy_pattern": "cover_toc"},
                        {"prototype_index": 2, "role": "toc", "copy_pattern": "cover_toc"},
                        {"prototype_index": 3, "role": "section", "copy_pattern": "general"},
                        {"prototype_index": 12, "role": "section", "copy_pattern": "general"},
                    ]
                },
            }
        }

        out = GenerationService._apply_template_routes(plan, template, copy_patterns=[], force=True)

        section_routes = [
            slide["prototype_index"]
            for slide in out["slides"]
            if slide.get("prototype_hint") == "section"
        ]
        self.assertEqual(section_routes, [3, 3, 3])

    def test_content_route_never_falls_back_to_section_by_general_pattern(self) -> None:
        plan = {
            "slides": [
                {"index": 1, "title": "Cover", "prototype_hint": "cover", "copy_pattern": "cover_toc"},
                {"index": 2, "title": "Toc", "toc_items": [], "prototype_hint": "toc"},
                {
                    "index": 3,
                    "title": "First content",
                    "prototype_hint": "content",
                    "copy_pattern": "general",
                    "bullets": ["First page uses the only exact content route."],
                },
                {
                    "index": 4,
                    "title": "Second content",
                    "prototype_hint": "content",
                    "copy_pattern": "label_detail",
                    "points": [{"label": "B", "body": "Second page uses the fallback content route."}],
                },
                {
                    "index": 5,
                    "title": "Reference content",
                    "prototype_hint": "content",
                    "copy_pattern": "general",
                    "bullets": ["A full reference or paragraph page must stay content."],
                },
            ]
        }
        template = {
            "spec": {
                "prototypes": [
                    {
                        "index": 6,
                        "text_slots": [
                            {"slot_id": "l1", "role_hint": "body", "x": 0, "y": 0, "cx": 100, "cy": 100},
                            {"slot_id": "b1", "role_hint": "body", "x": 100, "y": 0, "cx": 100, "cy": 100},
                            {"slot_id": "l2", "role_hint": "body", "x": 0, "y": 100, "cx": 100, "cy": 100},
                            {"slot_id": "b2", "role_hint": "body", "x": 100, "y": 100, "cx": 100, "cy": 100},
                        ],
                    },
                    {
                        "index": 10,
                        "text_slots": [
                            {"slot_id": "l1", "role_hint": "body", "x": 0, "y": 0, "cx": 100, "cy": 100},
                            {"slot_id": "b1", "role_hint": "body", "x": 100, "y": 0, "cx": 100, "cy": 100},
                            {"slot_id": "l2", "role_hint": "body", "x": 0, "y": 100, "cx": 100, "cy": 100},
                            {"slot_id": "b2", "role_hint": "body", "x": 100, "y": 100, "cx": 100, "cy": 100},
                            {"slot_id": "l3", "role_hint": "body", "x": 0, "y": 200, "cx": 100, "cy": 100},
                            {"slot_id": "b3", "role_hint": "body", "x": 100, "y": 200, "cx": 100, "cy": 100},
                            {"slot_id": "l4", "role_hint": "body", "x": 0, "y": 300, "cx": 100, "cy": 100},
                            {"slot_id": "b4", "role_hint": "body", "x": 100, "y": 300, "cx": 100, "cy": 100},
                        ],
                    },
                ],
                "ai_standardization": {
                    "slide_routes": [
                        {"prototype_index": 1, "role": "cover", "copy_pattern": "cover_toc"},
                        {"prototype_index": 2, "role": "toc", "copy_pattern": "cover_toc"},
                        {"prototype_index": 3, "role": "section", "copy_pattern": "general"},
                        {"prototype_index": 12, "role": "section", "copy_pattern": "general"},
                        {"prototype_index": 4, "role": "content", "copy_pattern": "general"},
                        {"prototype_index": 7, "role": "content", "copy_pattern": "label_detail"},
                    ]
                }
            }
        }

        out = GenerationService._apply_template_routes(plan, template, copy_patterns=[], force=True)

        self.assertEqual(out["slides"][4]["prototype_hint"], "content")
        self.assertIn(out["slides"][4]["prototype_index"], {4, 7})

    def test_closing_semantic_survives_content_layout_fallback(self) -> None:
        plan = {
            "slides": [
                {"index": 1, "title": "Cover", "prototype_hint": "cover", "copy_pattern": "cover_toc"},
                {"index": 2, "title": "Toc", "toc_items": [], "prototype_hint": "toc"},
                {
                    "index": 3,
                    "title": "总结",
                    "prototype_hint": "closing",
                    "summary_items": ["A", "B", "C"],
                },
            ]
        }
        template = {
            "spec": {
                "prototypes": [
                    {
                        "index": 6,
                        "text_slots": [
                            {"slot_id": "l1", "role_hint": "body", "x": 0, "y": 0, "cx": 100, "cy": 100},
                            {"slot_id": "b1", "role_hint": "body", "x": 100, "y": 0, "cx": 100, "cy": 100},
                            {"slot_id": "l2", "role_hint": "body", "x": 0, "y": 100, "cx": 100, "cy": 100},
                            {"slot_id": "b2", "role_hint": "body", "x": 100, "y": 100, "cx": 100, "cy": 100},
                        ],
                    },
                    {
                        "index": 10,
                        "text_slots": [
                            {"slot_id": "l1", "role_hint": "body", "x": 0, "y": 0, "cx": 100, "cy": 100},
                            {"slot_id": "b1", "role_hint": "body", "x": 100, "y": 0, "cx": 100, "cy": 100},
                            {"slot_id": "l2", "role_hint": "body", "x": 0, "y": 100, "cx": 100, "cy": 100},
                            {"slot_id": "b2", "role_hint": "body", "x": 100, "y": 100, "cx": 100, "cy": 100},
                            {"slot_id": "l3", "role_hint": "body", "x": 0, "y": 200, "cx": 100, "cy": 100},
                            {"slot_id": "b3", "role_hint": "body", "x": 100, "y": 200, "cx": 100, "cy": 100},
                            {"slot_id": "l4", "role_hint": "body", "x": 0, "y": 300, "cx": 100, "cy": 100},
                            {"slot_id": "b4", "role_hint": "body", "x": 100, "y": 300, "cx": 100, "cy": 100},
                        ],
                    },
                ],
                "ai_standardization": {
                    "slide_routes": [
                        {"prototype_index": 1, "role": "cover", "copy_pattern": "cover_toc"},
                        {"prototype_index": 2, "role": "toc", "copy_pattern": "cover_toc"},
                        {"prototype_index": 7, "role": "content", "copy_pattern": "label_detail"},
                    ]
                }
            }
        }

        out = GenerationService._apply_template_routes(plan, template, copy_patterns=[], force=True)

        self.assertEqual(out["slides"][2]["prototype_hint"], "closing")
        self.assertEqual(out["slides"][2]["prototype_index"], 7)

    def test_bullet_content_reuses_general_route_before_dense_grid(self) -> None:
        plan = {
            "slides": [
                {"index": 1, "title": "Cover", "prototype_hint": "cover", "copy_pattern": "cover_toc"},
                {"index": 2, "title": "Toc", "toc_items": [], "prototype_hint": "toc"},
                {"index": 3, "title": "First", "prototype_hint": "content", "copy_pattern": "general", "bullets": ["A"]},
                {"index": 4, "title": "Second", "prototype_hint": "content", "copy_pattern": "general", "bullets": ["B"]},
            ]
        }
        template = {
            "spec": {
                "ai_standardization": {
                    "slide_routes": [
                        {"prototype_index": 1, "role": "cover", "copy_pattern": "cover_toc"},
                        {"prototype_index": 2, "role": "toc", "copy_pattern": "cover_toc"},
                        {"prototype_index": 4, "role": "content", "copy_pattern": "general"},
                        {"prototype_index": 8, "role": "dense_grid", "copy_pattern": "dense_grid"},
                    ]
                }
            }
        }

        out = GenerationService._apply_template_routes(plan, template, copy_patterns=[], force=True)

        self.assertEqual(out["slides"][3]["prototype_index"], 4)
        self.assertEqual(out["slides"][3]["copy_pattern"], "general")

    def test_long_body_content_prefers_high_capacity_route(self) -> None:
        long_bullets = [
            "这一页正文较长，需要保留病例线索、诊断推理、风险提示和处理策略，而不是被塞进窄小文本框后截断。",
            "第二段继续解释临床意义，要求模板路由优先选择大文本框页面，保证主要文本框能被填满。",
            "第三段补充随访和患者教育，模拟真实教学 PPT 中一页会承载的完整说明。",
        ]
        plan = {
            "slides": [
                {"index": 1, "title": "Cover", "prototype_hint": "cover", "copy_pattern": "cover_toc"},
                {"index": 2, "title": "Toc", "toc_items": [], "prototype_hint": "toc"},
                {"index": 3, "title": "Dense body", "prototype_hint": "content", "copy_pattern": "general", "bullets": long_bullets},
            ]
        }
        template = {
            "spec": {
                "prototypes": [
                    {
                        "index": 4,
                        "text_slots": [
                            {"slot_id": "small", "role_hint": "body", "cx": 2000000, "cy": 500000},
                        ],
                    },
                    {
                        "index": 14,
                        "text_slots": [
                            {"slot_id": "large", "role_hint": "body", "cx": 9000000, "cy": 4500000},
                        ],
                    },
                ],
                "ai_standardization": {
                    "slide_routes": [
                        {"prototype_index": 1, "role": "cover", "copy_pattern": "cover_toc"},
                        {"prototype_index": 2, "role": "toc", "copy_pattern": "cover_toc"},
                        {"prototype_index": 4, "role": "content", "copy_pattern": "general"},
                        {"prototype_index": 14, "role": "content", "copy_pattern": "general"},
                    ]
                },
            }
        }

        out = GenerationService._apply_template_routes(plan, template, copy_patterns=[], force=True)

        self.assertEqual(out["slides"][2]["prototype_index"], 14)

    def test_label_detail_content_prefers_enough_point_pairs(self) -> None:
        plan = {
            "slides": [
                {"index": 1, "title": "Cover", "prototype_hint": "cover", "copy_pattern": "cover_toc"},
                {"index": 2, "title": "Toc", "toc_items": [], "prototype_hint": "toc"},
                {
                    "index": 3,
                    "title": "Four points",
                    "prototype_hint": "content",
                    "copy_pattern": "label_detail",
                    "points": [
                        {"label": "A", "body": "detail A"},
                        {"label": "B", "body": "detail B"},
                        {"label": "C", "body": "detail C"},
                        {"label": "D", "body": "detail D"},
                    ],
                },
            ]
        }
        template = {
            "spec": {
                "prototypes": [
                    {
                        "index": 6,
                        "text_slots": [
                            {"slot_id": "l1", "role_hint": "body", "x": 0, "y": 0, "cx": 100, "cy": 100},
                            {"slot_id": "b1", "role_hint": "body", "x": 100, "y": 0, "cx": 100, "cy": 100},
                            {"slot_id": "l2", "role_hint": "body", "x": 0, "y": 100, "cx": 100, "cy": 100},
                            {"slot_id": "b2", "role_hint": "body", "x": 100, "y": 100, "cx": 100, "cy": 100},
                        ],
                    },
                    {
                        "index": 10,
                        "text_slots": [
                            {"slot_id": "l1", "role_hint": "body", "x": 0, "y": 0, "cx": 100, "cy": 100},
                            {"slot_id": "b1", "role_hint": "body", "x": 100, "y": 0, "cx": 100, "cy": 100},
                            {"slot_id": "l2", "role_hint": "body", "x": 0, "y": 100, "cx": 100, "cy": 100},
                            {"slot_id": "b2", "role_hint": "body", "x": 100, "y": 100, "cx": 100, "cy": 100},
                            {"slot_id": "l3", "role_hint": "body", "x": 0, "y": 200, "cx": 100, "cy": 100},
                            {"slot_id": "b3", "role_hint": "body", "x": 100, "y": 200, "cx": 100, "cy": 100},
                            {"slot_id": "l4", "role_hint": "body", "x": 0, "y": 300, "cx": 100, "cy": 100},
                            {"slot_id": "b4", "role_hint": "body", "x": 100, "y": 300, "cx": 100, "cy": 100},
                        ],
                    },
                ],
                "ai_standardization": {
                    "slide_routes": [
                        {"prototype_index": 1, "role": "cover", "copy_pattern": "cover_toc"},
                        {"prototype_index": 2, "role": "toc", "copy_pattern": "cover_toc"},
                        {"prototype_index": 6, "role": "content", "copy_pattern": "label_detail"},
                        {"prototype_index": 10, "role": "content", "copy_pattern": "label_detail"},
                    ],
                    "slot_bindings": [
                        {"prototype_index": 6, "slot_id": "l1", "semantic": "point_label"},
                        {"prototype_index": 6, "slot_id": "b1", "semantic": "point_body"},
                        {"prototype_index": 6, "slot_id": "l2", "semantic": "point_label"},
                        {"prototype_index": 6, "slot_id": "b2", "semantic": "point_body"},
                        {"prototype_index": 10, "slot_id": "l1", "semantic": "point_label"},
                        {"prototype_index": 10, "slot_id": "b1", "semantic": "point_body"},
                        {"prototype_index": 10, "slot_id": "l2", "semantic": "point_label"},
                        {"prototype_index": 10, "slot_id": "b2", "semantic": "point_body"},
                        {"prototype_index": 10, "slot_id": "l3", "semantic": "point_label"},
                        {"prototype_index": 10, "slot_id": "b3", "semantic": "point_body"},
                        {"prototype_index": 10, "slot_id": "l4", "semantic": "point_label"},
                        {"prototype_index": 10, "slot_id": "b4", "semantic": "point_body"},
                    ],
                },
            }
        }

        out = GenerationService._apply_template_routes(plan, template, copy_patterns=[], force=True)

        self.assertEqual(out["slides"][2]["prototype_index"], 10)

    def test_overfull_content_slide_is_split_before_routing(self) -> None:
        long_points = [
            {"label": f"要点{i}", "body": "这是一段较长的临床解释，需要完整保留诊断推理、风险提示、处理策略和随访意义。" * 2}
            for i in range(1, 6)
        ]
        plan = {
            "slides": [
                {"index": 1, "title": "Cover", "prototype_hint": "cover"},
                {"index": 2, "title": "Toc", "toc_items": ["章节"], "prototype_hint": "toc"},
                {"index": 3, "title": "章节", "section_title": "章节", "prototype_hint": "section"},
                {
                    "index": 4,
                    "title": "高密度正文",
                    "section_title": "章节",
                    "prototype_hint": "content",
                    "copy_pattern": "label_detail",
                    "points": long_points,
                },
            ]
        }

        out = GenerationService._split_overfull_content_slides(plan, max_units=260, max_points=3)

        content_slides = [slide for slide in out["slides"] if slide.get("prototype_hint") == "content"]
        self.assertEqual(len(content_slides), 2)
        self.assertEqual(len(content_slides[0]["points"]), 3)
        self.assertEqual(len(content_slides[1]["points"]), 2)
        self.assertEqual(content_slides[1]["bullets"], [])
        self.assertEqual(content_slides[1]["copy_pattern"], "label_detail")
        self.assertEqual(content_slides[1]["section_title"], "章节")
        self.assertIn("续", content_slides[1]["title"])

    def test_label_detail_routes_cycle_when_multiple_templates_fit(self) -> None:
        slides = [
            {"index": 1, "title": "Cover", "prototype_hint": "cover"},
            {"index": 2, "title": "Toc", "prototype_hint": "toc"},
        ]
        for i in range(3):
            slides.append(
                {
                    "index": i + 3,
                    "title": f"Two point page {i}",
                    "prototype_hint": "content",
                    "copy_pattern": "label_detail",
                    "points": [
                        {"label": "A", "body": "detail A"},
                        {"label": "B", "body": "detail B"},
                    ],
                }
            )
        template = {
            "spec": {
                "prototypes": [
                    {
                        "index": idx,
                        "text_slots": [
                            {"slot_id": "l1", "role_hint": "body", "x": 0, "y": 0, "cx": 1500000, "cy": 800000},
                            {"slot_id": "b1", "role_hint": "body", "x": 2000000, "y": 0, "cx": 5000000, "cy": 800000},
                            {"slot_id": "l2", "role_hint": "body", "x": 0, "y": 1000000, "cx": 1500000, "cy": 800000},
                            {"slot_id": "b2", "role_hint": "body", "x": 2000000, "y": 1000000, "cx": 5000000, "cy": 800000},
                        ],
                    }
                    for idx in (6, 7, 10)
                ],
                "ai_standardization": {
                    "slide_routes": [
                        {"prototype_index": 1, "role": "cover", "copy_pattern": "cover_toc"},
                        {"prototype_index": 2, "role": "toc", "copy_pattern": "cover_toc"},
                        {"prototype_index": 6, "role": "content", "copy_pattern": "label_detail"},
                        {"prototype_index": 7, "role": "content", "copy_pattern": "label_detail"},
                        {"prototype_index": 10, "role": "content", "copy_pattern": "label_detail"},
                    ],
                    "slot_bindings": [
                        {"prototype_index": idx, "slot_id": slot, "semantic": semantic}
                        for idx in (6, 7, 10)
                        for slot, semantic in (
                            ("l1", "point_label"),
                            ("b1", "point_body"),
                            ("l2", "point_label"),
                            ("b2", "point_body"),
                        )
                    ],
                },
            }
        }

        out = GenerationService._apply_template_routes({"slides": slides}, template, copy_patterns=[], force=True)

        routed = [slide["prototype_index"] for slide in out["slides"][2:]]
        self.assertEqual(set(routed), {6, 7, 10})

    def test_label_detail_route_reuses_adequate_template_before_inadequate_unused(self) -> None:
        slides = [
            {"index": 1, "title": "Cover", "prototype_hint": "cover"},
            {"index": 2, "title": "Toc", "prototype_hint": "toc"},
            {
                "index": 3,
                "title": "Three point page A",
                "prototype_hint": "content",
                "copy_pattern": "label_detail",
                "points": [
                    {"label": "A", "body": "detail A"},
                    {"label": "B", "body": "detail B"},
                    {"label": "C", "body": "detail C"},
                ],
            },
            {
                "index": 4,
                "title": "Three point page B",
                "prototype_hint": "content",
                "copy_pattern": "label_detail",
                "points": [
                    {"label": "A", "body": "detail A"},
                    {"label": "B", "body": "detail B"},
                    {"label": "C", "body": "detail C"},
                ],
            },
        ]
        template = {
            "spec": {
                "prototypes": [
                    {
                        "index": 6,
                        "text_slots": [
                            {"slot_id": "l1", "role_hint": "body", "x": 0, "y": 0, "cx": 1500000, "cy": 800000},
                            {"slot_id": "b1", "role_hint": "body", "x": 2000000, "y": 0, "cx": 5000000, "cy": 800000},
                            {"slot_id": "l2", "role_hint": "body", "x": 0, "y": 1000000, "cx": 1500000, "cy": 800000},
                            {"slot_id": "b2", "role_hint": "body", "x": 2000000, "y": 1000000, "cx": 5000000, "cy": 800000},
                        ],
                    },
                    {
                        "index": 10,
                        "text_slots": [
                            {"slot_id": "l1", "role_hint": "body", "x": 0, "y": 0, "cx": 1500000, "cy": 800000},
                            {"slot_id": "b1", "role_hint": "body", "x": 2000000, "y": 0, "cx": 5000000, "cy": 800000},
                            {"slot_id": "l2", "role_hint": "body", "x": 0, "y": 1000000, "cx": 1500000, "cy": 800000},
                            {"slot_id": "b2", "role_hint": "body", "x": 2000000, "y": 1000000, "cx": 5000000, "cy": 800000},
                            {"slot_id": "l3", "role_hint": "body", "x": 0, "y": 2000000, "cx": 1500000, "cy": 800000},
                            {"slot_id": "b3", "role_hint": "body", "x": 2000000, "y": 2000000, "cx": 5000000, "cy": 800000},
                        ],
                    },
                ],
                "ai_standardization": {
                    "slide_routes": [
                        {"prototype_index": 1, "role": "cover", "copy_pattern": "cover_toc"},
                        {"prototype_index": 2, "role": "toc", "copy_pattern": "cover_toc"},
                        {"prototype_index": 6, "role": "content", "copy_pattern": "label_detail"},
                        {"prototype_index": 10, "role": "content", "copy_pattern": "label_detail"},
                    ],
                    "slot_bindings": [
                        {"prototype_index": 6, "slot_id": "l1", "semantic": "point_label"},
                        {"prototype_index": 6, "slot_id": "b1", "semantic": "point_body"},
                        {"prototype_index": 6, "slot_id": "l2", "semantic": "point_label"},
                        {"prototype_index": 6, "slot_id": "b2", "semantic": "point_body"},
                        {"prototype_index": 10, "slot_id": "l1", "semantic": "point_label"},
                        {"prototype_index": 10, "slot_id": "b1", "semantic": "point_body"},
                        {"prototype_index": 10, "slot_id": "l2", "semantic": "point_label"},
                        {"prototype_index": 10, "slot_id": "b2", "semantic": "point_body"},
                        {"prototype_index": 10, "slot_id": "l3", "semantic": "point_label"},
                        {"prototype_index": 10, "slot_id": "b3", "semantic": "point_body"},
                    ],
                },
            }
        }

        out = GenerationService._apply_template_routes({"slides": slides}, template, copy_patterns=[], force=True)

        self.assertEqual([slide["prototype_index"] for slide in out["slides"][2:]], [10, 10])

    def test_label_detail_route_pads_underfilled_point_pairs(self) -> None:
        slides = [
            {"index": 1, "title": "Cover", "prototype_hint": "cover"},
            {"index": 2, "title": "Toc", "prototype_hint": "toc"},
            {
                "index": 3,
                "title": "Summary",
                "section_title": "Summary",
                "prototype_hint": "content",
                "copy_pattern": "label_detail",
                "points": [
                    {"label": "A", "body": "First enough detail for a real body slot."},
                    {"label": "B", "body": "Second enough detail for a real body slot."},
                    {"label": "C", "body": "Third enough detail for a real body slot."},
                ],
            },
        ]
        template = {
            "spec": {
                "prototypes": [
                    {
                        "index": 10,
                        "text_slots": [
                            {"slot_id": "l1", "role_hint": "body", "x": 0, "y": 0, "cx": 1500000, "cy": 800000},
                            {"slot_id": "b1", "role_hint": "body", "x": 2000000, "y": 0, "cx": 5000000, "cy": 800000},
                            {"slot_id": "l2", "role_hint": "body", "x": 0, "y": 1000000, "cx": 1500000, "cy": 800000},
                            {"slot_id": "b2", "role_hint": "body", "x": 2000000, "y": 1000000, "cx": 5000000, "cy": 800000},
                            {"slot_id": "l3", "role_hint": "body", "x": 0, "y": 2000000, "cx": 1500000, "cy": 800000},
                            {"slot_id": "b3", "role_hint": "body", "x": 2000000, "y": 2000000, "cx": 5000000, "cy": 800000},
                            {"slot_id": "l4", "role_hint": "body", "x": 0, "y": 3000000, "cx": 1500000, "cy": 800000},
                            {"slot_id": "b4", "role_hint": "body", "x": 2000000, "y": 3000000, "cx": 5000000, "cy": 800000},
                        ],
                    }
                ],
                "ai_standardization": {
                    "slide_routes": [
                        {"prototype_index": 10, "role": "content", "copy_pattern": "label_detail"},
                    ],
                    "slot_bindings": [
                        {"prototype_index": 10, "slot_id": "l1", "semantic": "point_label"},
                        {"prototype_index": 10, "slot_id": "b1", "semantic": "point_body"},
                        {"prototype_index": 10, "slot_id": "l2", "semantic": "point_label"},
                        {"prototype_index": 10, "slot_id": "b2", "semantic": "point_body"},
                        {"prototype_index": 10, "slot_id": "l3", "semantic": "point_label"},
                        {"prototype_index": 10, "slot_id": "b3", "semantic": "point_body"},
                        {"prototype_index": 10, "slot_id": "l4", "semantic": "point_label"},
                        {"prototype_index": 10, "slot_id": "b4", "semantic": "point_body"},
                    ],
                },
            }
        }

        out = GenerationService._apply_template_routes({"slides": slides}, template, copy_patterns=[], force=True)

        points = out["slides"][2]["points"]
        self.assertEqual(len(points), 4)
        self.assertEqual(points[-1]["label"], "补充提示")
        self.assertGreaterEqual(len(points[-1]["body"]), 20)

    def test_high_demand_general_page_prefers_capacity_over_unused_template(self) -> None:
        dense_bullets = ["clinical detail " * 18, "follow up detail " * 16]
        plan = {
            "slides": [
                {"index": 1, "title": "Cover", "prototype_hint": "cover"},
                {"index": 2, "title": "Toc", "prototype_hint": "toc"},
                {"index": 3, "title": "Warmup", "prototype_hint": "content", "copy_pattern": "general", "bullets": ["short"]},
                {"index": 4, "title": "Dense", "prototype_hint": "content", "copy_pattern": "general", "bullets": dense_bullets},
            ]
        }
        template = {
            "spec": {
                "prototypes": [
                    {"index": 4, "text_slots": [{"slot_id": "small", "role_hint": "body", "cx": 3000000, "cy": 900000}]},
                    {"index": 14, "text_slots": [{"slot_id": "large", "role_hint": "body", "cx": 9000000, "cy": 4500000}]},
                ],
                "ai_standardization": {
                    "slide_routes": [
                        {"prototype_index": 1, "role": "cover", "copy_pattern": "cover_toc"},
                        {"prototype_index": 2, "role": "toc", "copy_pattern": "cover_toc"},
                        {"prototype_index": 4, "role": "content", "copy_pattern": "general"},
                        {"prototype_index": 14, "role": "content", "copy_pattern": "general"},
                    ]
                },
            }
        }

        out = GenerationService._apply_template_routes(plan, template, copy_patterns=[], force=True)

        self.assertEqual(out["slides"][3]["prototype_index"], 14)

    def test_overfull_four_point_slide_balances_into_two_label_detail_pages(self) -> None:
        long_points = [
            {"label": f"P{i}", "body": "clinical reasoning and treatment detail " * 2}
            for i in range(1, 5)
        ]
        plan = {
            "slides": [
                {"index": 1, "title": "Cover", "prototype_hint": "cover"},
                {
                    "index": 2,
                    "title": "Dense label detail",
                    "prototype_hint": "content",
                    "copy_pattern": "label_detail",
                    "points": long_points,
                },
            ]
        }

        out = GenerationService._split_overfull_content_slides(plan, max_units=260, max_points=3)

        content_slides = [slide for slide in out["slides"] if slide.get("prototype_hint") == "content"]
        self.assertEqual([len(slide["points"]) for slide in content_slides], [2, 2])
        self.assertTrue(all(slide["copy_pattern"] == "label_detail" for slide in content_slides))

    def test_generate_requires_confirmed_outline_before_rendering(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service = GenerationService.__new__(GenerationService)
            from app.config import Settings
            from app.core.linter import SlideLinter
            from app.core.slide_planner import SlidePlanner
            from app.core.template_normalizer import TemplateNormalizer
            from app.storage import Storage

            service.settings = Settings(
                data_dir=Path(tmp),
                host="127.0.0.1",
                port=0,
                openai_api_key="",
                openai_base_url="",
                openai_model="",
            )
            service.storage = Storage(Path(tmp))
            service.normalizer = TemplateNormalizer()
            service.planner = SlidePlanner()
            service.renderer = TemplateRenderer()
            service.linter = SlideLinter()
            service.runtime_defaults = {"openai_api_key": "", "openai_base_url": "", "openai_model": ""}

            pptx = Path(tmp) / "template.pptx"
            _minimal_pptx(pptx)
            template = service.storage.create_template("template.pptx", pptx.read_bytes())
            service.storage.save_template_spec(template["template_id"], {"slide_count": 1, "ai_standardization": {"slide_routes": []}})
            project = service.create_project("Test topic", template["template_id"], 4)

            with self.assertRaisesRegex(ValueError, "确认"):
                service.generate_project(project["project_id"])

    def test_generate_records_real_stage_messages_for_polling_ui(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service = GenerationService.__new__(GenerationService)
            from app.config import Settings
            from app.core.slide_planner import SlidePlanner
            from app.core.template_normalizer import TemplateNormalizer
            from app.storage import Storage

            class FakeRenderer:
                def copy_pattern_summary(self, template_path, slide_count):  # type: ignore[no-untyped-def]
                    return []

                def render(self, template_path, plan, output_path, template_spec):  # type: ignore[no-untyped-def]
                    output_path.write_bytes(b"pptx")
                    return {"ok": True}

            class FakeLinter:
                def lint(self, output_path):  # type: ignore[no-untyped-def]
                    return {"issues": []}

            service.settings = Settings(
                data_dir=Path(tmp),
                host="127.0.0.1",
                port=0,
                openai_api_key="",
                openai_base_url="",
                openai_model="",
            )
            service.storage = Storage(Path(tmp))
            service.normalizer = TemplateNormalizer()
            service.planner = SlidePlanner()
            service.renderer = FakeRenderer()
            service.linter = FakeLinter()
            service.runtime_defaults = {"openai_api_key": "", "openai_base_url": "", "openai_model": ""}

            pptx = Path(tmp) / "template.pptx"
            _minimal_pptx(pptx)
            template = service.storage.create_template("template.pptx", pptx.read_bytes())
            service.storage.save_template_spec(
                template["template_id"],
                {
                    "slide_count": 1,
                    "ai_standardization": {"slide_routes": []},
                },
            )
            project = service.create_project("Test topic", template["template_id"], 4)
            plan = {
                "slides": [
                    {"title": "Cover", "prototype_hint": "cover"},
                    {"title": "Toc", "prototype_hint": "toc"},
                    {"title": "Content", "prototype_hint": "content", "bullets": ["detail"]},
                    {"title": "End", "prototype_hint": "closing", "summary_items": ["done"]},
                ]
            }
            service.storage.update_project(
                project["project_id"],
                {
                    "draft_plan": plan,
                    "outline_confirmed": True,
                    "conversation": [],
                },
            )

            out = service.generate_project(project["project_id"])

            messages = "\n".join(msg["content"] for msg in out["conversation"])
            self.assertIn("正在匹配模板版式", messages)
            self.assertIn("正在写入 PPTX", messages)
            self.assertIn("正在运行版式检查", messages)
            self.assertIn("PPT 已生成，可以下载", messages)

    def test_plan_records_real_stage_messages_for_polling_ui(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service = GenerationService.__new__(GenerationService)
            from app.config import Settings
            from app.core.slide_planner import SlidePlanner
            from app.core.template_normalizer import TemplateNormalizer
            from app.storage import Storage

            class FakeRenderer:
                def copy_pattern_summary(self, template_path, slide_count):  # type: ignore[no-untyped-def]
                    return []

            service.settings = Settings(
                data_dir=Path(tmp),
                host="127.0.0.1",
                port=0,
                openai_api_key="",
                openai_base_url="",
                openai_model="",
            )
            service.storage = Storage(Path(tmp))
            service.normalizer = TemplateNormalizer()
            service.planner = SlidePlanner()
            service.renderer = FakeRenderer()
            service.runtime_defaults = {"openai_api_key": "", "openai_base_url": "", "openai_model": ""}

            pptx = Path(tmp) / "template.pptx"
            _minimal_pptx(pptx)
            template = service.storage.create_template("template.pptx", pptx.read_bytes())
            service.storage.save_template_spec(
                template["template_id"],
                {
                    "slide_count": 1,
                    "ai_standardization": {"slide_routes": []},
                },
            )
            project = service.create_project("Test topic", template["template_id"], 4)

            out = service.plan_project(project["project_id"], "", allow_without_ai=True)

            messages = "\n".join(msg["content"] for msg in out["project"]["conversation"])
            self.assertIn("正在生成完整 PPT 大纲", messages)
            self.assertIn("正在依据模板合同检查大纲", messages)
            self.assertIn("完整大纲已生成", messages)

    def test_local_standardization_builds_slot_bindings_without_ai(self) -> None:
        local = GenerationService._local_template_standardization(
            {
                "prototypes": [
                    {
                        "index": 1,
                        "text_slots": [
                            {"slot_id": "s1", "role_hint": "cover_title", "font_size_pt": 44},
                            {"slot_id": "s2", "role_hint": "meta", "font_size_pt": 18, "text": "汇报人：张三"},
                        ],
                    },
                    {"index": 2, "text_slots": [{"slot_id": "s1", "role_hint": "toc_title", "font_size_pt": 32}]},
                ]
            }
        )

        self.assertFalse(local["ai_used"])
        self.assertIn("已生成本地标准化合同", local["summary"])
        self.assertNotIn("未配置或无法调用 AI", local["summary"])
        self.assertIn("deck_flow", local)
        self.assertEqual(local["content_rules"]["min_body_font_size_pt"], 16)
        semantics = {item["semantic"] for item in local["slot_bindings"]}
        self.assertIn("deck_title", semantics)
        self.assertIn("presenter", semantics)

    def test_local_standardization_detects_label_detail_body_slots(self) -> None:
        local = GenerationService._local_template_standardization(
            {
                "prototypes": [
                    {
                        "index": 3,
                        "text_slots": [
                            {"slot_id": "s1_1", "role_hint": "page_title", "font_size_pt": 28, "cx": 7600000, "cy": 600000},
                            {"slot_id": "s2_1", "role_hint": "body", "font_size_pt": 18, "cx": 1500000, "cy": 620000, "alignment": "ctr"},
                            {"slot_id": "s3_1", "role_hint": "body", "font_size_pt": 18, "cx": 6200000, "cy": 900000, "alignment": "l"},
                            {"slot_id": "s4_1", "role_hint": "body", "font_size_pt": 18, "cx": 1500000, "cy": 620000, "alignment": "ctr"},
                            {"slot_id": "s5_1", "role_hint": "body", "font_size_pt": 18, "cx": 6200000, "cy": 900000, "alignment": "l"},
                        ],
                    }
                ]
            }
        )

        route = local["slide_routes"][0]
        self.assertEqual(route["copy_pattern"], "label_detail")
        by_slot = {item["slot_id"]: item["semantic"] for item in local["slot_bindings"]}
        self.assertEqual(by_slot["s1_1"], "page_title")
        self.assertEqual(by_slot["s2_1"], "point_label")
        self.assertEqual(by_slot["s3_1"], "point_body")

    def test_local_standardization_marks_transition_title_slot(self) -> None:
        local = GenerationService._local_template_standardization(
            {
                "prototypes": [
                    {
                        "index": 3,
                        "text_slots": [
                            {"slot_id": "s1_1", "role_hint": "page_title", "font_size_pt": 34, "cx": 5000000, "cy": 900000},
                        ],
                    },
                    {
                        "index": 4,
                        "text_slots": [
                            {"slot_id": "s1_1", "role_hint": "page_title", "font_size_pt": 28, "cx": 7600000, "cy": 600000},
                            {"slot_id": "s2_1", "role_hint": "body", "font_size_pt": 18, "cx": 6000000, "cy": 1200000},
                        ],
                    },
                ]
            }
        )

        first_route = local["slide_routes"][0]
        self.assertEqual(first_route["role"], "section")
        by_slot = {
            (item["prototype_index"], item["slot_id"]): item["semantic"]
            for item in local["slot_bindings"]
        }
        self.assertEqual(by_slot[(3, "s1_1")], "section_title")

    def test_local_standardization_detects_multiple_transition_templates(self) -> None:
        local = GenerationService._local_template_standardization(
            {
                "prototypes": [
                    {"index": 1, "text_slots": [{"slot_id": "s1", "role_hint": "cover_title", "font_size_pt": 44}]},
                    {"index": 2, "text_slots": [{"slot_id": "s1", "role_hint": "toc_title", "font_size_pt": 32}]},
                    {
                        "index": 3,
                        "text_slots": [
                            {"slot_id": "s1_1", "role_hint": "page_title", "font_size_pt": 34, "cx": 5000000, "cy": 900000},
                        ],
                    },
                    {
                        "index": 5,
                        "text_slots": [
                            {"slot_id": "s1_1", "role_hint": "page_title", "font_size_pt": 36, "cx": 5200000, "cy": 880000},
                        ],
                    },
                    {
                        "index": 6,
                        "text_slots": [
                            {"slot_id": "s1_1", "role_hint": "page_title", "font_size_pt": 28, "cx": 7600000, "cy": 600000},
                            {"slot_id": "s2_1", "role_hint": "body", "font_size_pt": 18, "cx": 6000000, "cy": 1200000},
                        ],
                    },
                ]
            }
        )

        routes = {
            item["prototype_index"]: item["role"]
            for item in local["slide_routes"]
        }
        self.assertEqual(routes[3], "section")
        self.assertEqual(routes[5], "section")
        self.assertEqual(routes[6], "content")

    def test_local_standardization_keeps_multi_slot_visual_content_templates(self) -> None:
        local = GenerationService._local_template_standardization(
            {
                "prototypes": [
                    {
                        "index": 8,
                        "text_slots": [
                            {"slot_id": "t", "role_hint": "page_title", "font_size_pt": 28, "cx": 7600000, "cy": 600000},
                            {"slot_id": "n1", "role_hint": "body", "font_size_pt": 24, "text": "01", "x": 500000, "y": 1400000, "cx": 900000, "cy": 600000},
                            {"slot_id": "b1", "role_hint": "body", "font_size_pt": 16, "text": "第一栏说明", "x": 1450000, "y": 1400000, "cx": 2200000, "cy": 900000},
                            {"slot_id": "n2", "role_hint": "body", "font_size_pt": 24, "text": "02", "x": 4200000, "y": 1400000, "cx": 900000, "cy": 600000},
                            {"slot_id": "b2", "role_hint": "body", "font_size_pt": 16, "text": "第二栏说明", "x": 5150000, "y": 1400000, "cx": 2200000, "cy": 900000},
                            {"slot_id": "n3", "role_hint": "body", "font_size_pt": 24, "text": "03", "x": 7950000, "y": 1400000, "cx": 900000, "cy": 600000},
                            {"slot_id": "b3", "role_hint": "body", "font_size_pt": 16, "text": "第三栏说明", "x": 8900000, "y": 1400000, "cx": 2200000, "cy": 900000},
                        ],
                    }
                ]
            }
        )

        self.assertEqual(local["slide_routes"][0]["role"], "dense_grid")
        self.assertEqual(local["slide_routes"][0]["copy_pattern"], "dense_grid")
        semantics = {
            item["slot_id"]: item["semantic"]
            for item in local["slot_bindings"]
            if item["prototype_index"] == 8
        }
        self.assertEqual(semantics["t"], "page_title")
        self.assertEqual(semantics["n1"], "point_label")
        self.assertEqual(semantics["b1"], "point_body")

    def test_old_local_standardization_summary_is_upgraded_for_display(self) -> None:
        template = {
            "spec": {
                "ai_standardization": {
                    "ai_used": False,
                    "summary": "未配置或无法调用 AI，已基于本地文本框、字号、字体和位置生成保底模板合同。",
                }
            }
        }

        GenerationService._refresh_local_standardization_summary(template)

        summary = template["spec"]["ai_standardization"]["summary"]
        self.assertIn("已生成本地标准化合同", summary)
        self.assertNotIn("未配置或无法调用 AI", summary)


if __name__ == "__main__":
    unittest.main()
