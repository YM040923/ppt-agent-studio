import re
import tempfile
import unittest
from pathlib import Path

from app.core.ai_adapter import AIAdapter
from app.core.slide_planner import SlidePlanner
from app.service import GenerationService
from tests.test_template_contract import _minimal_pptx


def _slide_text_units(slide: dict) -> int:
    texts = [
        str(slide.get("title") or ""),
        str(slide.get("subtitle") or ""),
        *[str(item or "") for item in slide.get("bullets", []) if isinstance(slide.get("bullets"), list)],
        *[str(item or "") for item in slide.get("summary_items", []) if isinstance(slide.get("summary_items"), list)],
    ]
    if isinstance(slide.get("points"), list):
        for point in slide["points"]:
            if isinstance(point, dict):
                texts.append(str(point.get("label") or ""))
                texts.append(str(point.get("body") or ""))
    return sum(len(re.sub(r"\s+", "", text)) for text in texts)


class ReferenceQualityPlanTests(unittest.TestCase):
    def test_plan_project_requires_explicit_consent_before_local_fallback_without_ai(self) -> None:
        import app.service as service_module
        from app.core.linter import SlideLinter
        from app.core.renderer import TemplateRenderer
        from app.core.template_normalizer import TemplateNormalizer
        from app.storage import Storage

        original_ai = service_module.AIAdapter

        class OfflineAI(AIAdapter):
            def __init__(self, *args, **kwargs):  # type: ignore[no-untyped-def]
                pass

            def check_connection(self) -> dict:  # type: ignore[override]
                return {"ok": False, "reason": "no_api_key", "message": "未配置 API Key"}

            def generate_plan(self, *args, **kwargs):  # type: ignore[no-untyped-def]
                raise AssertionError("AI plan generation must not be called when connection check fails")

        service_module.AIAdapter = OfflineAI  # type: ignore[assignment]
        try:
            with tempfile.TemporaryDirectory() as tmp:
                service = GenerationService.__new__(GenerationService)
                service.settings = type(
                    "SettingsLike",
                    (),
                    {
                        "data_dir": Path(tmp),
                        "host": "127.0.0.1",
                        "port": 0,
                        "openai_api_key": "",
                        "openai_base_url": "https://example.test/v1",
                        "openai_model": "fake",
                    },
                )()
                service.storage = Storage(Path(tmp))
                service.normalizer = TemplateNormalizer()
                service.planner = SlidePlanner()
                service.renderer = TemplateRenderer()
                service.linter = SlideLinter()
                service.runtime_defaults = {
                    "openai_api_key": "",
                    "openai_base_url": "https://example.test/v1",
                    "openai_model": "fake",
                }

                pptx = Path(tmp) / "template.pptx"
                _minimal_pptx(pptx)
                template = service.storage.create_template("template.pptx", pptx.read_bytes())
                service.storage.save_template_spec(template["template_id"], {"slide_count": 1, "ai_standardization": {"slide_routes": []}})
                project = service.create_project("肺淋巴管平滑肌瘤病（LAM）的病因、临床表现与治疗", template["template_id"], 15)

                out = service.plan_project(project["project_id"], "")

                self.assertEqual(out["ai_status"], "unavailable")
                self.assertIn("继续不用 AI", out["assistant_message"])
                self.assertIsNone(out["project"].get("draft_plan"))
                self.assertEqual(out["project"].get("status"), "needs_ai_choice")
        finally:
            service_module.AIAdapter = original_ai  # type: ignore[assignment]

    def test_plan_project_uses_local_fallback_only_after_user_consent(self) -> None:
        import app.service as service_module
        from app.core.linter import SlideLinter
        from app.core.renderer import TemplateRenderer
        from app.core.template_normalizer import TemplateNormalizer
        from app.storage import Storage

        original_ai = service_module.AIAdapter

        class OfflineAI(AIAdapter):
            def __init__(self, *args, **kwargs):  # type: ignore[no-untyped-def]
                pass

            def check_connection(self) -> dict:  # type: ignore[override]
                return {"ok": False, "reason": "network_error", "message": "AI 连接测试失败"}

            def generate_plan(self, *args, **kwargs):  # type: ignore[no-untyped-def]
                raise AssertionError("AI should not be called after user chose local generation")

        service_module.AIAdapter = OfflineAI  # type: ignore[assignment]
        try:
            with tempfile.TemporaryDirectory() as tmp:
                service = GenerationService.__new__(GenerationService)
                service.settings = type(
                    "SettingsLike",
                    (),
                    {
                        "data_dir": Path(tmp),
                        "host": "127.0.0.1",
                        "port": 0,
                        "openai_api_key": "",
                        "openai_base_url": "https://example.test/v1",
                        "openai_model": "fake",
                    },
                )()
                service.storage = Storage(Path(tmp))
                service.normalizer = TemplateNormalizer()
                service.planner = SlidePlanner()
                service.renderer = TemplateRenderer()
                service.linter = SlideLinter()
                service.runtime_defaults = {
                    "openai_api_key": "",
                    "openai_base_url": "https://example.test/v1",
                    "openai_model": "fake",
                }

                pptx = Path(tmp) / "template.pptx"
                _minimal_pptx(pptx)
                template = service.storage.create_template("template.pptx", pptx.read_bytes())
                service.storage.save_template_spec(template["template_id"], {"slide_count": 1, "ai_standardization": {"slide_routes": []}})
                project = service.create_project("肺淋巴管平滑肌瘤病（LAM）的病因、临床表现与治疗", template["template_id"], 15)

                out = service.plan_project(project["project_id"], "", allow_without_ai=True)

                self.assertEqual(out["plan"]["source"], "reference_quality_lam")
                self.assertEqual(out["project"]["status"], "planned")
                self.assertIsInstance(out["project"].get("draft_plan"), dict)
        finally:
            service_module.AIAdapter = original_ai  # type: ignore[assignment]

    def test_plan_project_does_not_fallback_when_chat_generation_fails_after_ai_check(self) -> None:
        import app.service as service_module
        from app.core.linter import SlideLinter
        from app.core.renderer import TemplateRenderer
        from app.core.template_normalizer import TemplateNormalizer
        from app.storage import Storage

        original_ai = service_module.AIAdapter

        class BrokenChatAI(AIAdapter):
            def __init__(self, *args, **kwargs):  # type: ignore[no-untyped-def]
                pass

            def check_connection(self) -> dict:  # type: ignore[override]
                return {"ok": True, "reason": "ok", "message": "AI 连接测试通过"}

            def generate_plan(self, *args, **kwargs):  # type: ignore[no-untyped-def]
                return None

            def polish_plan(self, *args, **kwargs):  # type: ignore[no-untyped-def]
                raise AssertionError("Polish must not run when plan generation failed")

        service_module.AIAdapter = BrokenChatAI  # type: ignore[assignment]
        try:
            with tempfile.TemporaryDirectory() as tmp:
                service = GenerationService.__new__(GenerationService)
                service.settings = type(
                    "SettingsLike",
                    (),
                    {
                        "data_dir": Path(tmp),
                        "host": "127.0.0.1",
                        "port": 0,
                        "openai_api_key": "key",
                        "openai_base_url": "https://example.test/v1",
                        "openai_model": "fake",
                    },
                )()
                service.storage = Storage(Path(tmp))
                service.normalizer = TemplateNormalizer()
                service.planner = SlidePlanner()
                service.renderer = TemplateRenderer()
                service.linter = SlideLinter()
                service.runtime_defaults = {
                    "openai_api_key": "key",
                    "openai_base_url": "https://example.test/v1",
                    "openai_model": "fake",
                }

                pptx = Path(tmp) / "template.pptx"
                _minimal_pptx(pptx)
                template = service.storage.create_template("template.pptx", pptx.read_bytes())
                service.storage.save_template_spec(template["template_id"], {"slide_count": 1, "ai_standardization": {"slide_routes": []}})
                project = service.create_project("肺淋巴管平滑肌瘤病（LAM）的病因、临床表现与治疗", template["template_id"], 15)

                out = service.plan_project(project["project_id"], "")

                self.assertTrue(out["requires_user_choice"])
                self.assertEqual(out["ai_status"], "unavailable")
                self.assertEqual(out["ai_check"]["reason"], "generation_unavailable")
                self.assertIn("继续不用 AI", out["assistant_message"])
                self.assertIsNone(out["project"].get("draft_plan"))
                self.assertEqual(out["project"].get("status"), "needs_ai_choice")
        finally:
            service_module.AIAdapter = original_ai  # type: ignore[assignment]

    def test_lam_reference_plan_matches_handmade_density_floor(self) -> None:
        plan = SlidePlanner().build_reference_quality_plan(
            "肺淋巴管平滑肌瘤病（LAM）的病因、临床表现与治疗",
            audience="PBL 病例汇报",
            tone="临床教学",
        )

        slides = plan["slides"]
        content_units = [
            _slide_text_units(slide)
            for slide in slides
            if slide.get("prototype_hint") == "content"
        ]

        self.assertGreaterEqual(len(slides), 23)
        self.assertGreaterEqual(sum(_slide_text_units(slide) for slide in slides), 3600)
        self.assertGreaterEqual(sum(1 for units in content_units if units >= 170), 13)
        self.assertLessEqual(sum(1 for units in content_units if units < 120), 1)

    def test_lam_reference_plan_fills_main_body_slots_with_teachable_detail(self) -> None:
        plan = SlidePlanner().build_reference_quality_plan(
            "肺淋巴管平滑肌瘤病（LAM）的病因、临床表现与治疗",
            audience="PBL 病例汇报",
            tone="临床教学",
        )

        body_lengths = []
        for slide in plan["slides"]:
            if slide.get("prototype_hint") != "content":
                continue
            if "参考" in str(slide.get("title") or ""):
                continue
            points = slide.get("points") if isinstance(slide.get("points"), list) else []
            bullets = slide.get("bullets") if isinstance(slide.get("bullets"), list) else []
            for point in points:
                if isinstance(point, dict):
                    body_lengths.append(len(re.sub(r"\s+", "", str(point.get("body") or ""))))
            for bullet in bullets:
                body = str(bullet or "").split("：", 1)[-1]
                body_lengths.append(len(re.sub(r"\s+", "", body)))

        self.assertGreaterEqual(len(body_lengths), 55)
        self.assertLessEqual(sum(length < 34 for length in body_lengths), 8)
        self.assertGreaterEqual(sum(length >= 50 for length in body_lengths), 28)
        self.assertGreaterEqual(sum(body_lengths) / len(body_lengths), 50)

    def test_lam_reference_plan_uses_case_driven_non_mechanical_rhythm(self) -> None:
        plan = SlidePlanner().build_reference_quality_plan(
            "肺淋巴管平滑肌瘤病（LAM）的病因、临床表现与治疗",
            audience="PBL 病例汇报",
            tone="临床教学",
        )
        slides = plan["slides"]
        titles = [str(slide.get("title") or "") for slide in slides]
        toc_items = slides[1].get("toc_items")
        generic_toc = ["疾病概述", "病因机制", "临床诊断", "治疗随访"]
        narrative_text = "".join(
            str(slide.get("title") or "")
            + str(slide.get("subtitle") or "")
            + "".join(str(item or "") for item in slide.get("bullets", []))
            + "".join(str(item or "") for item in slide.get("toc_items", []))
            + "".join(
                str(point.get("label") or "") + str(point.get("body") or "")
                for point in slide.get("points", [])
                if isinstance(point, dict)
            )
            for slide in slides
        )
        section_counts = []
        current = 0
        for slide in slides[2:]:
            if slide.get("prototype_hint") == "section":
                if current:
                    section_counts.append(current)
                current = 0
            elif slide.get("prototype_hint") == "content" and "参考" not in str(slide.get("title") or ""):
                current += 1
        if current:
            section_counts.append(current)

        self.assertNotEqual(toc_items, generic_toc)
        self.assertGreaterEqual(len(set(section_counts)), 2)
        self.assertGreaterEqual(sum(token in narrative_text for token in ("小杨", "第一幕", "第二幕", "证据链", "普通气胸")), 4)
        self.assertTrue(any("总结：LAM" in title for title in titles[-3:]))

    def test_lam_reference_plan_keeps_closing_and_references_out_of_section_content_counts(self) -> None:
        plan = SlidePlanner().build_reference_quality_plan(
            "\u80ba\u6dcb\u5df4\u7ba1\u5e73\u6ed1\u808c\u7624\u75c5\uff08LAM\uff09\u7684\u75c5\u56e0\u3001\u4e34\u5e8a\u8868\u73b0\u4e0e\u6cbb\u7597",
            audience="PBL \u75c5\u4f8b\u6c47\u62a5",
            tone="\u4e34\u5e8a\u6559\u5b66",
        )
        slides = plan["slides"]
        titles = [str(slide.get("title") or "") for slide in slides]
        section_counts = []
        current = 0
        for slide in slides[2:]:
            role = slide.get("prototype_hint")
            if role == "section":
                if current:
                    section_counts.append(current)
                current = 0
            elif role == "content":
                current += 1
        if current:
            section_counts.append(current)

        self.assertLessEqual(max(section_counts), 6)
        self.assertGreaterEqual(len(section_counts), 4)
        self.assertNotEqual(slides[-2].get("prototype_hint"), "content")
        self.assertNotEqual(slides[-1].get("prototype_hint"), "content")
        self.assertIn("\u603b\u7ed3", titles[-2])
        self.assertIn("\u53c2\u8003\u6587\u732e", titles[-1])

    def test_lam_reference_plan_keeps_content_titles_concise(self) -> None:
        plan = SlidePlanner().build_reference_quality_plan(
            "\u80ba\u6dcb\u5df4\u7ba1\u5e73\u6ed1\u808c\u7624\u75c5\uff08LAM\uff09\u7684\u75c5\u56e0\u3001\u4e34\u5e8a\u8868\u73b0\u4e0e\u6cbb\u7597",
            audience="PBL \u75c5\u4f8b\u6c47\u62a5",
            tone="\u4e34\u5e8a\u6559\u5b66",
        )
        content_title_lengths = [
            len(re.sub(r"\s+", "", str(slide.get("title") or "")))
            for slide in plan["slides"]
            if slide.get("prototype_hint") == "content"
        ]

        self.assertLessEqual(max(content_title_lengths), 20)
        self.assertLessEqual(sum(length > 18 for length in content_title_lengths), 2)

    def test_template_routing_preserves_closing_then_reference_tail_order(self) -> None:
        plan = SlidePlanner().build_reference_quality_plan(
            "\u80ba\u6dcb\u5df4\u7ba1\u5e73\u6ed1\u808c\u7624\u75c5\uff08LAM\uff09\u7684\u75c5\u56e0\u3001\u4e34\u5e8a\u8868\u73b0\u4e0e\u6cbb\u7597",
            audience="PBL \u75c5\u4f8b\u6c47\u62a5",
            tone="\u4e34\u5e8a\u6559\u5b66",
        )
        template = {"spec": {"ai_standardization": {"slide_routes": []}, "prototypes": []}}

        routed = GenerationService._apply_template_routes(plan, template, copy_patterns=[], force=True)
        slides = routed["slides"]

        self.assertEqual(slides[-2].get("prototype_hint"), "closing")
        self.assertEqual(slides[-1].get("prototype_hint"), "reference")
        self.assertIn("\u603b\u7ed3", str(slides[-2].get("title") or ""))
        self.assertIn("\u53c2\u8003\u6587\u732e", str(slides[-1].get("title") or ""))

    def test_lam_reference_plan_avoids_repeated_filler_tails(self) -> None:
        plan = SlidePlanner().build_reference_quality_plan(
            "肺淋巴管平滑肌瘤病（LAM）的病因、临床表现与治疗",
            audience="PBL 病例汇报",
            tone="临床教学",
        )
        filler_phrases = [
            "应说明这一线索如何改变鉴别诊断、检查选择和后续管理重点。",
            "同时交代与普通气胸不同的复发风险、检查顺序和后续预防策略。",
            "需要把分子机制和囊性肺破坏、肺外受累及靶向治疗选择连起来。",
            "讲解时要同时说明适应证、疗效观察、安全监测和随访调整依据。",
            "补充判断依据、临床意义和下一步处理，使听众能直接用于病例讨论。",
        ]
        deck_text = ""
        repeated_inside_slide = []
        for slide in plan["slides"]:
            chunks = [
                str(slide.get("title") or ""),
                *[str(item or "") for item in slide.get("bullets", []) if isinstance(slide.get("bullets"), list)],
                *[str(item or "") for item in slide.get("summary_items", []) if isinstance(slide.get("summary_items"), list)],
            ]
            if isinstance(slide.get("points"), list):
                for point in slide["points"]:
                    if isinstance(point, dict):
                        chunks.append(str(point.get("label") or ""))
                        chunks.append(str(point.get("body") or ""))
            slide_text = "\n".join(chunks)
            deck_text += slide_text + "\n"
            for phrase in filler_phrases:
                if slide_text.count(phrase) > 1:
                    repeated_inside_slide.append((slide.get("title"), phrase))

        self.assertEqual(repeated_inside_slide, [])
        for phrase in filler_phrases:
            self.assertLessEqual(deck_text.count(phrase), 2, phrase)

    def test_lam_reference_plan_has_no_repeated_long_sentence_inside_one_slide(self) -> None:
        plan = SlidePlanner().build_reference_quality_plan(
            "肺淋巴管平滑肌瘤病（LAM）的病因、临床表现与治疗",
            audience="PBL 病例汇报",
            tone="临床教学",
        )
        repeated = []
        for slide in plan["slides"]:
            if slide.get("prototype_hint") != "content":
                continue
            chunks = []
            if isinstance(slide.get("bullets"), list):
                chunks.extend(str(item or "") for item in slide["bullets"])
            if isinstance(slide.get("points"), list):
                for point in slide["points"]:
                    if isinstance(point, dict):
                        chunks.append(str(point.get("body") or ""))
            sentences = [
                item.strip()
                for chunk in chunks
                for item in re.split(r"[。！？!?]", chunk)
                if len(item.strip()) >= 18
            ]
            for sentence in set(sentences):
                if sentences.count(sentence) > 1:
                    repeated.append((slide.get("title"), sentence))

        self.assertEqual(repeated, [])

    def test_thin_ai_plan_with_enough_pages_still_triggers_reference_upgrade(self) -> None:
        slides = [
            {"title": "Cover", "prototype_hint": "cover"},
            {"title": "目录", "prototype_hint": "toc", "toc_items": ["一", "二", "三", "四"]},
        ]
        for section in range(4):
            slides.append({"title": f"章节{section}", "prototype_hint": "section"})
            for page in range(5):
                slides.append(
                    {
                        "title": f"正文{section}-{page}",
                        "prototype_hint": "content",
                        "points": [
                            {"label": "要点", "body": "说明不足"},
                            {"label": "处理", "body": "缺少细节"},
                        ],
                    }
                )
        slides.append({"title": "总结", "prototype_hint": "closing"})

        self.assertTrue(GenerationService._plan_needs_reference_quality_upgrade({"slides": slides}))


    def test_generic_encyclopedia_lam_outline_triggers_reference_upgrade_even_when_dense(self) -> None:
        lam = "\u80ba\u6dcb\u5df4\u7ba1\u5e73\u6ed1\u808c\u7624\u75c5\uff08LAM\uff09"
        generic_sections = [
            "\u75be\u75c5\u6982\u8ff0",
            "\u75c5\u56e0\u673a\u5236",
            "\u4e34\u5e8a\u8bca\u65ad",
            "\u6cbb\u7597\u968f\u8bbf",
        ]
        content_titles = [
            "LAM\u57fa\u672c\u8ba4\u8bc6",
            "\u6d41\u884c\u75c5\u4e0e\u5206\u578b",
            "\u9057\u4f20\u4e0e\u4fe1\u53f7\u901a\u8def",
            "\u7ec4\u7ec7\u635f\u4f24\u673a\u5236",
            "\u4e34\u5e8a\u8868\u73b0",
            "\u68c0\u67e5\u4e0e\u786e\u8bca",
            "\u6cbb\u7597\u7b56\u7565",
            "\u968f\u8bbf\u4e0e\u5b66\u4e60\u8981\u70b9",
        ]
        dense_body = (
            "\u8fd9\u91cc\u8865\u5145\u75be\u75c5\u7684\u5b9a\u4e49\u3001\u5e38\u89c1\u8868\u73b0\u3001"
            "\u68c0\u67e5\u65b9\u5f0f\u548c\u5904\u7406\u539f\u5219\uff0c\u6587\u5b57\u5bc6\u5ea6"
            "\u8db3\u591f\uff0c\u4f46\u7ed3\u6784\u4ecd\u7136\u662f\u6cdb\u5316\u767e\u79d1\u5f0f\u9648\u8ff0\u3002"
        )
        slides = [
            {"title": lam, "prototype_hint": "cover", "subtitle": "\u75c5\u56e0\u3001\u4e34\u5e8a\u8868\u73b0\u4e0e\u6cbb\u7597"},
            {"title": "\u76ee\u5f55", "prototype_hint": "toc", "toc_items": generic_sections},
        ]
        title_index = 0
        for section in generic_sections:
            slides.append({"title": section, "prototype_hint": "section"})
            for _ in range(5):
                title = content_titles[title_index % len(content_titles)]
                title_index += 1
                slides.append(
                    {
                        "title": title,
                        "prototype_hint": "content",
                        "points": [
                            {"label": "\u6982\u5ff5", "body": dense_body},
                            {"label": "\u673a\u5236", "body": dense_body},
                            {"label": "\u8bc4\u4f30", "body": dense_body},
                            {"label": "\u7ba1\u7406", "body": dense_body},
                        ],
                    }
                )
        slides.append({"title": "\u603b\u7ed3\uff1aLAM\u7684\u8ba4\u8bc6\u4e0e\u7ba1\u7406", "prototype_hint": "closing"})

        self.assertGreaterEqual(sum(_slide_text_units(slide) for slide in slides), 3400)
        self.assertFalse(any(token in str(slides) for token in ("\u5c0f\u6768", "\u7b2c\u4e00\u5e55", "\u8bc1\u636e\u94fe")))
        self.assertTrue(GenerationService._plan_needs_reference_quality_upgrade({"slides": slides}))

    def test_service_upgrades_bad_ai_15_page_lam_outline_before_confirmation(self) -> None:
        bad_ai_plan = {
            "deck_title": "肺淋巴管平滑肌瘤病（LAM）的病因、临床表现与治疗",
            "slides": [
                {"index": 1, "title": "肺淋巴管平滑肌瘤病（LAM）的病因、临床表现与治", "prototype_hint": "cover", "bullets": ["肺淋巴管平滑肌瘤病（LAM）的病因、临床表现与治疗"]},
                {"index": 2, "title": "目录", "prototype_hint": "toc", "toc_items": ["疾病概述", "病因机制", "临床诊断", "治疗随访"]},
                {"index": 3, "title": "疾病概述", "prototype_hint": "section"},
                {"index": 4, "title": "LAM基本认识", "prototype_hint": "content", "points": [{"label": "疾病定义", "body": "LAM是罕见低度恶性肿瘤样疾病，异常平滑肌样细胞可累及肺、淋巴系统和肾脏。"}]},
                {"index": 5, "title": "流行病与分型", "prototype_hint": "content", "points": [{"label": "散发型", "body": "散发性LAM多无明确家族史，常以气胸、活动后气促或体检影像异常起病。"}]},
                {"index": 6, "title": "病因机制", "prototype_hint": "content"},
                {"index": 7, "title": "遗传与信号通路", "prototype_hint": "content", "points": [{"label": "TSC基因", "body": "LAM与TSC1或TSC2基因失活相关，可导致错构瘤蛋白复合体功能下降。"}]},
                {"index": 8, "title": "组织损伤机制", "prototype_hint": "content", "points": [{"label": "囊腔形成", "body": "LAM细胞可分泌蛋白酶并破坏肺间质，导致薄壁囊腔逐渐形成和扩大。"}]},
                {"index": 9, "title": "临床诊断", "prototype_hint": "content"},
                {"index": 10, "title": "临床表现", "prototype_hint": "content", "points": [{"label": "气促", "body": "LAM最常见表现为活动后呼吸困难，常随肺功能下降而逐渐加重。"}]},
                {"index": 11, "title": "检查与确诊", "prototype_hint": "content", "points": [{"label": "HRCT", "body": "HRCT典型表现为双肺弥漫、均匀分布的薄壁圆形囊腔，是识别LAM的关键检查。"}]},
                {"index": 12, "title": "治疗随访", "prototype_hint": "closing"},
                {"index": 13, "title": "治疗策略", "prototype_hint": "content", "points": [{"label": "mTOR抑制", "body": "西罗莫司适用于肺功能下降、乳糜并发症或肾血管平滑肌脂肪瘤进展的LAM患者。"}]},
                {"index": 14, "title": "随访与学习要点", "prototype_hint": "content", "points": [{"label": "功能监测", "body": "LAM随访需定期检查肺功能，重点观察FEV1和DLCO的变化趋势。"}]},
                {"index": 15, "title": "总结", "prototype_hint": "closing", "summary_items": ["LAM是以育龄期女性多见的罕见囊性肺病。"]},
            ],
            "source": "ai",
        }

        with tempfile.TemporaryDirectory() as tmp:
            import app.service as service_module
            from app.config import Settings
            from app.core.renderer import TemplateRenderer
            from app.core.template_normalizer import TemplateNormalizer
            from app.storage import Storage

            original_ai = service_module.AIAdapter

            class FakeAI(original_ai):
                def __init__(self, *args, **kwargs):  # type: ignore[no-untyped-def]
                    pass

                def check_connection(self) -> dict:  # type: ignore[override]
                    return {"ok": True, "reason": "ok", "message": "AI 连接测试通过"}

                def generate_plan(self, *args, **kwargs):  # type: ignore[no-untyped-def]
                    return bad_ai_plan

                def polish_plan(self, *args, **kwargs):  # type: ignore[no-untyped-def]
                    return bad_ai_plan

            service_module.AIAdapter = FakeAI  # type: ignore[assignment]
            try:
                service = GenerationService.__new__(GenerationService)
                service.settings = Settings(
                    data_dir=Path(tmp),
                    host="127.0.0.1",
                    port=0,
                    openai_api_key="key",
                    openai_base_url="https://example.test/v1",
                    openai_model="fake",
                )
                service.storage = Storage(Path(tmp))
                service.normalizer = TemplateNormalizer()
                service.planner = SlidePlanner()
                service.renderer = TemplateRenderer()
                service.runtime_defaults = {"openai_api_key": "key", "openai_base_url": "https://example.test/v1", "openai_model": "fake"}

                pptx = Path(tmp) / "template.pptx"
                _minimal_pptx(pptx)
                template = service.storage.create_template("template.pptx", pptx.read_bytes())
                service.storage.save_template_spec(template["template_id"], {"slide_count": 1, "ai_standardization": {"slide_routes": []}})
                project = service.create_project("肺淋巴管平滑肌瘤病（LAM）的病因、临床表现与治疗", template["template_id"], 15)

                out = service.plan_project(project["project_id"], "")
            finally:
                service_module.AIAdapter = original_ai  # type: ignore[assignment]

        final_plan = out["project"]["draft_plan"]
        slides = final_plan["slides"]
        titles = [str(slide.get("title") or "") for slide in slides]
        toc_items = slides[1].get("toc_items")
        content_units = [_slide_text_units(slide) for slide in slides if slide.get("prototype_hint") == "content"]

        self.assertEqual(final_plan.get("source"), "reference_quality_lam")
        self.assertGreaterEqual(len(slides), 23)
        self.assertNotEqual(toc_items, ["疾病概述", "病因机制", "临床诊断", "治疗随访"])
        self.assertTrue(any("小杨" in title for title in titles))
        self.assertGreaterEqual(sum(1 for slide in slides if slide.get("prototype_hint") == "section"), 4)
        self.assertGreaterEqual(min(content_units), 150)

    def test_case_driven_but_short_lam_outline_still_upgrades_to_reference_depth(self) -> None:
        ai_plan = {
            "deck_title": "肺淋巴管平滑肌瘤病（LAM）的病因、临床表现与治疗",
            "source": "ai",
            "slides": [
                {"index": 1, "title": "肺淋巴管平滑肌瘤病（LAM）的病因、临床表现与治", "prototype_hint": "cover"},
                {"index": 2, "title": "汇报路径", "prototype_hint": "toc", "toc_items": ["从病例入手", "线索到诊断", "机制看风险", "治疗与随访"]},
                {"index": 3, "title": "从病例入手", "prototype_hint": "section"},
                {"index": 4, "title": "首诊线索", "prototype_hint": "content", "points": [{"label": "年轻女性", "body": "20岁女性出现大量气胸和乳白色胸水时，应把普通气胸、乳糜胸和LAM线索放在一起判断。"}]},
                {"index": 5, "title": "病因图谱", "prototype_hint": "content", "points": [{"label": "TSC异常", "body": "TSC1或TSC2失活可推动mTOR通路激活，解释LAM细胞增殖、迁移和组织破坏。"}]},
                {"index": 6, "title": "线索到诊断", "prototype_hint": "section"},
                {"index": 7, "title": "初步检查", "prototype_hint": "content", "points": [{"label": "HRCT", "body": "HRCT若见双肺弥漫薄壁圆形囊腔，再结合VEGF-D和肺外受累，可形成诊断证据链。"}]},
                {"index": 8, "title": "表现与并发症", "prototype_hint": "content", "points": [{"label": "反复气胸", "body": "LAM相关气胸复发风险较高，急性处理后还要提前讨论胸膜固定和复发预防策略。"}]},
                {"index": 9, "title": "机制看风险", "prototype_hint": "section"},
                {"index": 10, "title": "机制与治疗靶点", "prototype_hint": "content", "points": [{"label": "mTOR靶点", "body": "mTOR异常激活使西罗莫司成为进展性LAM的重要治疗选择，需要结合肺功能和并发症判断。"}]},
                {"index": 11, "title": "肺外受累", "prototype_hint": "content", "points": [{"label": "肾AML", "body": "肾血管平滑肌脂肪瘤、淋巴管肌瘤和乳糜胸提示LAM是系统性疾病，随访不能只盯肺部。"}]},
                {"index": 12, "title": "治疗与随访", "prototype_hint": "section"},
                {"index": 13, "title": "治疗路径", "prototype_hint": "content", "points": [{"label": "综合处理", "body": "治疗需同时处理气胸、乳糜胸、肺功能下降和药物安全监测，不能只列一个药物名称。"}]},
                {"index": 14, "title": "患者教育", "prototype_hint": "content", "points": [{"label": "长期管理", "body": "患者需避免吸烟和雌激素暴露，妊娠前进行风险评估，并按计划复查肺功能和肾脏影像。"}]},
                {"index": 15, "title": "总结", "prototype_hint": "closing", "summary_items": ["LAM需要从病例线索进入诊断和全程管理。"]},
            ],
        }

        self.assertTrue(GenerationService._plan_needs_reference_quality_upgrade(ai_plan))

    def test_plan_summary_shows_complete_body_text_for_user_confirmation(self) -> None:
        long_body = (
            "右侧肺压缩约80%，起病急且程度重，提示囊性肺病导致胸膜下囊腔破裂的可能，"
            "需要同步解释复发风险和后续胸膜固定策略。"
        )
        summary = GenerationService._plan_summary(
            {
                "slides": [
                    {"title": "封面", "prototype_hint": "cover"},
                    {"title": "目录", "prototype_hint": "toc", "toc_items": ["病例线索"]},
                    {
                        "title": "病例线索",
                        "prototype_hint": "content",
                        "points": [{"label": "大量气胸", "body": long_body}],
                    },
                ]
            }
        )

        self.assertIn(long_body, summary)
        self.assertNotIn(f"大量气胸: {long_body[:44]}\n", summary)


if __name__ == "__main__":
    unittest.main()
