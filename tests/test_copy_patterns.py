import unittest
from xml.etree import ElementTree as ET

from app.core.renderer import TemplateRenderer, _ParagraphRef, _SlideProfile


def pref(order, x, y, cx, cy, align="", placeholder_type="", text=""):
    para = ET.Element("p")
    return _ParagraphRef(
        para=para,
        text_nodes=[],
        text=text,
        order=order,
        shape_id=order,
        shape_y=y,
        shape_x=x,
        shape_cx=cx,
        shape_cy=cy,
        placeholder_type=placeholder_type,
        is_placeholder=bool(placeholder_type),
        is_mirrored=False,
        text_align=align,
    )


class CopyPatternTests(unittest.TestCase):
    def test_label_detail_pattern_for_paired_narrow_and_wide_slots(self):
        renderer = TemplateRenderer()
        slots = [
            pref(0, 0, 0, 6000000, 500000, placeholder_type="title"),
            pref(1, 200000, 1000000, 2200000, 400000, align="ctr"),
            pref(2, 2600000, 1000000, 5600000, 500000, align="l"),
            pref(3, 200000, 1700000, 2200000, 400000, align="ctr"),
            pref(4, 2600000, 1700000, 5600000, 500000, align="l"),
        ]

        self.assertEqual(renderer._classify_copy_pattern(slots), "label_detail")

    def test_dense_grid_pattern_for_many_similar_content_slots(self):
        renderer = TemplateRenderer()
        slots = [pref(0, 0, 0, 6000000, 500000, placeholder_type="title")]
        for i in range(10):
            slots.append(pref(i + 1, (i % 5) * 1600000, 900000 + (i // 5) * 700000, 1400000, 420000))

        self.assertEqual(renderer._classify_copy_pattern(slots), "dense_grid")

    def test_general_pattern_for_ambiguous_layout(self):
        renderer = TemplateRenderer()
        slots = [
            pref(0, 0, 0, 6000000, 500000, placeholder_type="title"),
            pref(1, 0, 900000, 4200000, 800000, align="l"),
            pref(2, 0, 1800000, 4200000, 800000, align="l"),
        ]

        self.assertEqual(renderer._classify_copy_pattern(slots), "general")

    def test_route_penalty_prefers_matching_content_pattern(self):
        label_detail = _SlideProfile(
            path="ppt/slides/slide3.xml",
            index=3,
            slot_count=7,
            title_slot_count=1,
            max_capacity=80,
            min_capacity=12,
            avg_capacity=36,
            label_slot_count=3,
            detail_slot_count=3,
            copy_pattern="label_detail",
        )
        dense_grid = _SlideProfile(
            path="ppt/slides/slide4.xml",
            index=4,
            slot_count=7,
            title_slot_count=1,
            max_capacity=42,
            min_capacity=12,
            avg_capacity=24,
            label_slot_count=0,
            detail_slot_count=0,
            copy_pattern="dense_grid",
        )

        self.assertLess(
            TemplateRenderer._route_penalty(label_detail, needed_slots=4, hint="content", slide_number=5, copy_pattern="label_detail"),
            TemplateRenderer._route_penalty(dense_grid, needed_slots=4, hint="content", slide_number=5, copy_pattern="label_detail"),
        )

    def test_route_penalty_prefers_sparse_section_page(self):
        section = _SlideProfile(
            path="ppt/slides/slide5.xml",
            index=5,
            slot_count=1,
            title_slot_count=1,
            max_capacity=24,
            min_capacity=24,
            avg_capacity=24,
            copy_pattern="cover_toc",
        )
        content = _SlideProfile(
            path="ppt/slides/slide6.xml",
            index=6,
            slot_count=6,
            title_slot_count=1,
            max_capacity=80,
            min_capacity=16,
            avg_capacity=42,
            copy_pattern="label_detail",
        )

        self.assertLess(
            TemplateRenderer._route_penalty(section, needed_slots=2, hint="section", slide_number=3, copy_pattern="general"),
            TemplateRenderer._route_penalty(content, needed_slots=2, hint="section", slide_number=3, copy_pattern="general"),
        )


if __name__ == "__main__":
    unittest.main()
