import unittest

from app.core.ai_adapter import AIAdapter


class AIAdapterCompactTests(unittest.TestCase):
    def test_compact_line_prefers_prefix_before_separator(self) -> None:
        text = "康复评估：功能目标与家庭执行协同路径"
        compact = AIAdapter._compact_line(text, max_chars=12)
        self.assertEqual(compact, "康复评估")

    def test_compact_line_truncates_when_no_separator(self) -> None:
        text = "出院后连续康复管理评估与闭环追踪机制"
        compact = AIAdapter._compact_line(text, max_chars=10)
        self.assertNotIn("...", compact)
        self.assertNotIn("…", compact)
        self.assertLessEqual(len(compact), 10)


    def test_polish_bullet_for_layout_expands_short_detail(self) -> None:
        bullet = "\u541e\u54bd\u98ce\u9669\uff1a\u7b5b\u67e5"
        polished = AIAdapter._polish_bullet_for_layout(bullet, anchor="\u80f6\u8d28\u7624")
        self.assertIn("\uff1a", polished)
        self.assertGreaterEqual(len(polished), 14)
        label = polished.split("\uff1a", 1)[0]
        self.assertLessEqual(len(label), 12)

    def test_polish_slide_bullets_uses_content_target_density(self) -> None:
        bullets = ["\u541e\u54bd\u98ce\u9669\uff1a\u7b5b\u67e5", "\u8fd0\u52a8\u80fd\u529b\uff1a\u8bc4\u4f30"]
        polished = AIAdapter._polish_slide_bullets(bullets, hint="content", anchor="\u80f6\u8d28\u7624")
        self.assertEqual(len(polished), 2)
        for line in polished:
            self.assertIn("\uff1a", line)
            self.assertGreaterEqual(len(line.split("\uff1a", 1)[1]), 20)

    def test_label_detail_pattern_uses_short_label_and_rich_detail(self) -> None:
        polished = AIAdapter._polish_slide_bullets_for_pattern(
            ["\u541e\u54bd\u98ce\u9669\uff1a\u7b5b\u67e5", "\u8fd0\u52a8\u80fd\u529b\uff1a\u8bc4\u4f30"],
            pattern="label_detail",
            anchor="\u80f6\u8d28\u7624",
        )
        self.assertEqual(len(polished), 2)
        for line in polished:
            head, detail = AIAdapter._split_heading_detail(line)
            self.assertGreaterEqual(len(head), 2)
            self.assertLessEqual(len(head), 12)
            self.assertGreaterEqual(len(detail), 20)

    def test_normalize_points_expands_short_ai_body_text(self) -> None:
        points = AIAdapter._normalize_points(
            [
                {"label": "\u541e\u54bd\u98ce\u9669", "body": "\u7b5b\u67e5"},
                {"label": "\u8fd0\u52a8\u80fd\u529b", "body": "\u8bc4\u4f30"},
            ],
            max_count=4,
        )

        self.assertEqual(len(points), 2)
        for point in points:
            self.assertGreaterEqual(len(point["body"]), 40)
            self.assertLessEqual(len(point["body"]), 118)

    def test_dense_grid_pattern_keeps_entries_compact(self) -> None:
        polished = AIAdapter._polish_slide_bullets_for_pattern(
            [
                "\u98ce\u9669\u8bc6\u522b\uff1a\u56f4\u7ed5\u80f6\u8d28\u7624\u672f\u540e\u541e\u54bd\u969c\u788d\u5efa\u7acb\u7b5b\u67e5\u3001\u590d\u8bc4\u3001\u8f6c\u8bca\u548c\u5bb6\u5c5e\u544a\u77e5\u95ed\u73af"
            ],
            pattern="dense_grid",
            anchor="\u80f6\u8d28\u7624",
        )
        self.assertLessEqual(len(polished[0]), 42)

    def test_process_pattern_adds_stage_like_detail(self) -> None:
        polished = AIAdapter._polish_slide_bullets_for_pattern(
            ["\u672f\u540e\u65e9\u671f\uff1a\u542f\u52a8\u5e8a\u65c1\u8bad\u7ec3"],
            pattern="process",
            anchor="\u80f6\u8d28\u7624",
        )
        head, detail = AIAdapter._split_heading_detail(polished[0])
        self.assertTrue(head)
        self.assertGreaterEqual(len(detail), 16)


if __name__ == "__main__":
    unittest.main()
