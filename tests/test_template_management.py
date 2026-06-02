import tempfile
import unittest
from pathlib import Path

from app.core.ai_adapter import AIAdapter
from app.storage import Storage


class TemplateManagementTests(unittest.TestCase):
    def test_delete_template_removes_template_folder(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            storage = Storage(Path(tmp))
            template = storage.create_template("demo.pptx", b"pptx bytes")

            removed = storage.delete_template(str(template["template_id"]))

            self.assertTrue(removed)
            self.assertIsNone(storage.get_template(str(template["template_id"])))
            self.assertFalse((Path(tmp) / "templates" / str(template["template_id"])).exists())

    def test_ai_adapter_standardizes_template_metadata(self) -> None:
        class FakeAI(AIAdapter):
            def _chat_json(self, body):  # type: ignore[no-untyped-def]
                return """
                {
                  "summary": "医疗汇报模板，封面和正文页清晰",
                  "layout_roles": [
                    {"layout": "Title Slide", "role": "cover", "confidence": 0.91}
                  ],
                  "slide_routes": [
                    {"prototype_index": 1, "role": "cover", "copy_pattern": "cover_toc"}
                  ],
                  "normalization_notes": ["优先使用标题占位符", "正文页保持短标题加说明"]
                }
                """

        adapter = FakeAI(api_key="key", base_url="https://example.test/v1", model="fake-model")

        result = adapter.standardize_template(
            {
                "layouts": [{"name": "Title Slide", "layout_type": "title", "placeholder_count": 2}],
                "prototypes": [{"index": 1, "layout_path": "ppt/slideLayouts/slideLayout1.xml", "text_preview": "标题"}],
            }
        )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result["agent"], "template_standardization_agent")
        self.assertTrue(result["ai_used"])
        self.assertEqual(result["layout_roles"][0]["role"], "cover")
        self.assertEqual(result["slide_routes"][0]["copy_pattern"], "cover_toc")


if __name__ == "__main__":
    unittest.main()
