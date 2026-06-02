from pathlib import Path
import unittest


class UiCopyTests(unittest.TestCase):
    def test_local_template_standardization_copy_reads_as_success(self):
        app_js = Path(__file__).resolve().parents[1] / "app" / "static" / "app.js"
        script = app_js.read_text(encoding="utf-8")

        self.assertIn("已生成本地标准化合同", script)
        self.assertNotIn("未完成 AI 标准化", script)
