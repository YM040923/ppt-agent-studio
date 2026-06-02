from pathlib import Path
import unittest


class GenerationProgressUiTests(unittest.TestCase):
    def test_generation_uses_project_polling_for_real_stage_feedback(self):
        app_js = Path(__file__).resolve().parents[1] / "app" / "static" / "app.js"
        script = app_js.read_text(encoding="utf-8")

        self.assertIn("function startProjectPolling", script)
        self.assertIn("await startProjectPolling(id)", script)
        self.assertIn("stopProjectPolling()", script)

    def test_outline_generation_also_uses_project_polling(self):
        app_js = Path(__file__).resolve().parents[1] / "app" / "static" / "app.js"
        script = app_js.read_text(encoding="utf-8")

        self.assertGreaterEqual(script.count("await startProjectPolling(id)"), 2)
