import unittest
from xml.etree import ElementTree as ET

from app.core.pptx_utils import NS
from app.core.renderer import TemplateRenderer, _ParagraphRef


def _build_pref(
    shape_cx: int,
    shape_cy: int,
    placeholder_type: str = "",
    font_size: int = 2400,
    order: int = 0,
    shape_id: int = 0,
    shape_x: int = 0,
    shape_y: int = 0,
    text_align: str = "",
    slot_id: str = "",
) -> _ParagraphRef:
    ppr = f'<a:pPr algn="{text_align}" />' if text_align else ""
    para = ET.fromstring(
        f"""
        <a:p xmlns:a="{NS["a"]}">
          {ppr}
          <a:r>
            <a:rPr sz="{font_size}" />
            <a:t></a:t>
          </a:r>
        </a:p>
        """
    )
    text_nodes = para.findall(".//a:t", NS)
    return _ParagraphRef(
        para=para,
        text_nodes=text_nodes,
        text="",
        order=order,
        shape_id=shape_id,
        shape_y=shape_y,
        shape_x=shape_x,
        shape_cx=shape_cx,
        shape_cy=shape_cy,
        placeholder_type=placeholder_type,
        is_placeholder=bool(placeholder_type),
        is_mirrored=False,
        text_align=text_align,
        slot_id=slot_id,
    )


class RendererTypographyTests(unittest.TestCase):
    def test_normalize_slot_text_keeps_medical_leading_numbers(self) -> None:
        renderer = TemplateRenderer()

        self.assertEqual(renderer._normalize_slot_text("20岁女性，育龄期人群"), "20岁女性，育龄期人群")
        self.assertEqual(renderer._normalize_slot_text("80%肺压缩提示大量气胸"), "80%肺压缩提示大量气胸")
        self.assertEqual(renderer._normalize_slot_text("1. 先救急，再查因"), "先救急，再查因")

    def test_single_line_slot_shrinks_font(self) -> None:
        renderer = TemplateRenderer()
        pref = _build_pref(shape_cx=2300000, shape_cy=520000, font_size=2600)

        renderer._set_paragraph_text(pref, "出院后康复管理评估与家庭执行协同路径")

        rpr = pref.para.find(".//a:rPr", NS)
        self.assertIsNotNone(rpr)
        final_size = int((rpr.attrib.get("sz") or "0"))
        self.assertLess(final_size, 2600)
        self.assertGreaterEqual(final_size, 1400)

    def test_single_line_slot_shortens_without_visible_ellipsis(self) -> None:
        renderer = TemplateRenderer()
        pref = _build_pref(shape_cx=1200000, shape_cy=420000, font_size=2200)

        text = renderer._fit_text_to_slot(pref, "康复训练路径与多学科协作机制及居家执行闭环追踪评估")

        self.assertFalse(text.endswith("..."))
        self.assertNotIn("\n", text)

    def test_short_heading_in_tall_box_still_shrinks(self) -> None:
        renderer = TemplateRenderer()
        pref = _build_pref(shape_cx=1900000, shape_cy=1200000, font_size=2800)

        renderer._set_paragraph_text(pref, "步行耐力分级推进")

        rpr = pref.para.find(".//a:rPr", NS)
        self.assertIsNotNone(rpr)
        final_size = int((rpr.attrib.get("sz") or "0"))
        self.assertLess(final_size, 2800)
        self.assertGreaterEqual(final_size, 1200)

    def test_set_text_removes_soft_line_break_elements(self) -> None:
        renderer = TemplateRenderer()
        pref = _build_pref(shape_cx=1900000, shape_cy=1200000, font_size=2800)
        ET.SubElement(pref.para, f"{{{NS['a']}}}br")
        self.assertEqual(len(pref.para.findall(".//a:br", NS)), 1)

        renderer._set_paragraph_text(pref, "步行耐力分级推进")

        self.assertEqual(len(pref.para.findall(".//a:br", NS)), 0)

    def test_wide_content_box_allows_longer_main_text(self) -> None:
        renderer = TemplateRenderer()
        pref = _build_pref(shape_cx=8500000, shape_cy=820000, font_size=1800)

        text = renderer._fit_text_to_slot(pref, "识别癫痫发作风险并完成家属告知与转诊预案")

        self.assertFalse(text.endswith("..."))
        self.assertGreaterEqual(len(text), 18)

    def test_center_label_and_left_detail_should_be_assigned_differently(self) -> None:
        renderer = TemplateRenderer()
        slots = [
            _build_pref(
                shape_cx=2200000,
                shape_cy=820000,
                font_size=2400,
                order=0,
                shape_id=1,
                shape_x=600000,
                shape_y=1800000,
                text_align="ctr",
            ),
            _build_pref(
                shape_cx=8500000,
                shape_cy=820000,
                font_size=1800,
                order=1,
                shape_id=2,
                shape_x=3000000,
                shape_y=1800000,
                text_align="l",
            ),
            _build_pref(
                shape_cx=2200000,
                shape_cy=820000,
                font_size=2400,
                order=2,
                shape_id=3,
                shape_x=600000,
                shape_y=3000000,
                text_align="ctr",
            ),
            _build_pref(
                shape_cx=8500000,
                shape_cy=820000,
                font_size=1800,
                order=3,
                shape_id=4,
                shape_x=3000000,
                shape_y=3000000,
                text_align="l",
            ),
        ]

        assignment = renderer._build_assignment(
            slots,
            [
                "癫痫风险：诱因、发作史、用药依从",
                "误吸风险：咳嗽弱、湿嗓、进食呛咳",
            ],
        )

        self.assertIn(0, assignment)
        self.assertIn(1, assignment)
        self.assertIn(2, assignment)
        self.assertIn(3, assignment)
        self.assertNotIn("：", assignment[0])
        self.assertNotIn("：", assignment[2])
        self.assertIn("：", assignment[1])
        self.assertIn("：", assignment[3])

    def test_regular_content_keeps_minimum_readable_font(self) -> None:
        renderer = TemplateRenderer()
        pref = _build_pref(shape_cx=3200000, shape_cy=1400000, font_size=1200)

        renderer._set_paragraph_text(pref, "这是一个普通正文段落")

        rpr = pref.para.find(".//a:rPr", NS)
        self.assertIsNotNone(rpr)
        final_size = int((rpr.attrib.get("sz") or "0"))
        self.assertGreaterEqual(final_size, 1800)


    def test_wide_detail_slot_expands_short_detail(self) -> None:
        renderer = TemplateRenderer()
        pref = _build_pref(shape_cx=8500000, shape_cy=820000, font_size=1800, text_align="l")
        raw = "\u541e\u54bd\u98ce\u9669\uff1a\u7b5b\u67e5"

        text = renderer._fit_text_to_slot(pref, raw)

        self.assertIn("\uff1a", text)
        self.assertGreater(len(text), len(raw))

    def test_compact_card_template_uses_footer_for_combined_bullet_details(self) -> None:
        renderer = TemplateRenderer()
        slots = [
            _build_pref(shape_cx=2563812, shape_cy=2563812, shape_x=1100000, shape_y=1789360, order=0, shape_id=1, slot_id="card1"),
            _build_pref(shape_cx=2563812, shape_cy=2563812, shape_x=4800000, shape_y=1789360, order=1, shape_id=2, slot_id="card2"),
            _build_pref(shape_cx=2563812, shape_cy=2563812, shape_x=8400000, shape_y=1789360, order=2, shape_id=3, slot_id="card3"),
            _build_pref(shape_cx=10852150, shape_cy=1595257, shape_x=660000, shape_y=4690772, order=3, shape_id=4, slot_id="footer"),
        ]
        slide = {
            "title": "LAM\u4e0e\u96cc\u6fc0\u7d20",
            "bullets": [
                "\u5973\u6027\u9ad8\u53d1\uff1aLAM\u51e0\u4e4e\u5168\u90e8\u53d1\u751f\u4e8e\u5973\u6027\uff0c\u63d0\u793a\u96cc\u6fc0\u7d20\u53ef\u80fd\u53c2\u4e0e\u75be\u75c5\u53d1\u751f\u548c\u8fdb\u5c55\u3002",
                "\u8fc1\u79fb\u4fb5\u88ad\uff1a\u96cc\u6fc0\u7d20\u53ef\u80fd\u4fc3\u8fdbLAM\u7ec6\u80de\u8fc1\u79fb\u3001\u4fb5\u88ad\u548c\u6dcb\u5df4\u7ba1\u76f8\u5173\u64ad\u6563\u3002",
                "\u4e34\u5e8a\u8bc4\u4f30\uff1a\u59ca\u5a20\u548c\u5916\u6e90\u6027\u96cc\u6fc0\u7d20\u66b4\u9732\u9700\u8981\u8c28\u614e\u8bc4\u4f30\uff0c\u4e0d\u80fd\u53ea\u628aLAM\u7406\u89e3\u4e3a\u6fc0\u7d20\u75c5\u3002",
            ],
        }
        bindings = [
            {"slot_id": "card1", "semantic": "body"},
            {"slot_id": "card2", "semantic": "body"},
            {"slot_id": "card3", "semantic": "body"},
            {"slot_id": "footer", "semantic": "body"},
        ]

        assignment = renderer._build_contract_assignment(slots, slide, bindings)

        self.assertIn("女性高发", assignment[0])
        self.assertNotIn("疾病发生和进展", assignment[0])
        self.assertIn("疾病发生和进展", assignment[3])
        self.assertIn("迁移、侵袭", assignment[3])
        self.assertIn("谨慎评估", assignment[3])


if __name__ == "__main__":
    unittest.main()
