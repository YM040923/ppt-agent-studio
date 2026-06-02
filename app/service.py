from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from .config import Settings
from .core.ai_adapter import AIAdapter
from .core.linter import SlideLinter
from .core.renderer import TemplateRenderer
from .core.slide_planner import SlidePlanner
from .core.template_normalizer import TemplateNormalizer
from .storage import Storage


class AIPlanUnavailableError(RuntimeError):
    pass


class GenerationService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.storage = Storage(settings.data_dir)
        self.normalizer = TemplateNormalizer()
        self.planner = SlidePlanner()
        self.renderer = TemplateRenderer()
        self.linter = SlideLinter()
        self.runtime_defaults = {
            "openai_api_key": settings.openai_api_key,
            "openai_base_url": settings.openai_base_url,
            "openai_model": settings.openai_model,
        }

    def upload_template(self, template_name: str, content: bytes) -> Dict[str, object]:
        meta = self.storage.create_template(template_name=template_name, content=content)
        spec = self.normalizer.normalize(
            template_id=meta["template_id"],
            template_name=meta["template_name"],
            template_path=Path(meta["pptx_path"]),
        )
        spec["ai_standardization"] = self._standardize_template_with_ai(spec)
        self.storage.save_template_spec(meta["template_id"], spec)
        return self.get_template(meta["template_id"]) or meta

    def list_templates(self) -> Dict[str, object]:
        return {"items": self.storage.list_templates()}

    def get_template(self, template_id: str) -> Optional[Dict[str, object]]:
        template = self.storage.get_template(template_id)
        if template and self._refresh_local_standardization_summary(template):
            spec = template.get("spec")
            if isinstance(spec, dict):
                self.storage.save_template_spec(template_id, spec)
        return template

    def delete_template(self, template_id: str) -> bool:
        return self.storage.delete_template(template_id)

    def export_standardized_template(self, template_id: str) -> Path:
        template = self.get_template(template_id)
        if not template:
            raise ValueError("Template not found")
        template_path = Path(str(template.get("pptx_path") or ""))
        if not template_path.exists():
            raise ValueError("Template file not found")
        output_path = template_path.with_name("standardized-preview.pptx")
        plan = self._build_template_preview_plan(template)
        self.renderer.render(
            template_path=template_path,
            plan=plan,
            output_path=output_path,
            template_spec=template.get("spec", {}) if isinstance(template.get("spec"), dict) else {},
        )
        return output_path

    def get_runtime_settings(self) -> Dict[str, object]:
        settings = self.storage.get_runtime_settings(self.runtime_defaults)
        return {
            "openai_base_url": settings.get("openai_base_url", ""),
            "openai_model": settings.get("openai_model", ""),
            "has_api_key": bool(settings.get("openai_api_key")),
        }

    def update_runtime_settings(self, patch: Dict[str, object]) -> Dict[str, object]:
        current = self.storage.get_runtime_settings(self.runtime_defaults)
        updated = {
            "openai_base_url": str(patch.get("openai_base_url") or current.get("openai_base_url") or "").strip(),
            "openai_model": str(patch.get("openai_model") or current.get("openai_model") or "").strip(),
            "openai_api_key": str(current.get("openai_api_key") or "").strip(),
        }

        incoming_key = patch.get("openai_api_key")
        clear_key = bool(patch.get("clear_api_key"))
        if clear_key:
            updated["openai_api_key"] = ""
        elif isinstance(incoming_key, str) and incoming_key.strip():
            updated["openai_api_key"] = incoming_key.strip()

        saved = self.storage.save_runtime_settings(updated)
        return {
            "openai_base_url": saved.get("openai_base_url", ""),
            "openai_model": saved.get("openai_model", ""),
            "has_api_key": bool(saved.get("openai_api_key")),
        }

    def check_ai_connection(self) -> Dict[str, object]:
        return self._ai_adapter().check_connection()

    def create_project(
        self,
        topic: str,
        template_id: str,
        slide_count: int,
        audience: str = "",
        tone: str = "",
    ) -> Dict[str, object]:
        if not topic.strip():
            raise ValueError("Topic is required")
        if not template_id.strip():
            raise ValueError("template_id is required")
        if slide_count < 4 or slide_count > 30:
            raise ValueError("slide_count must be between 4 and 30")
        template = self.get_template(template_id)
        if not template:
            raise ValueError("Template not found")
        return self.storage.create_project(topic, template_id, slide_count, audience, tone)

    def get_project(self, project_id: str) -> Optional[Dict[str, object]]:
        project = self.storage.get_project(project_id)
        if not project:
            return None
        if "conversation" not in project:
            project["conversation"] = []
        if "draft_plan" not in project:
            project["draft_plan"] = None
        if "outline_confirmed" not in project:
            project["outline_confirmed"] = False
        return project

    def plan_project(self, project_id: str, message: str = "", allow_without_ai: bool = False) -> Dict[str, object]:
        project = self.storage.get_project(project_id)
        if not project:
            raise ValueError("Project not found")

        template = self.get_template(str(project["template_id"]))
        if not template:
            raise ValueError("Template not found")

        conversation: List[Dict[str, str]] = list(project.get("conversation") or [])
        if message.strip():
            conversation.append(self._msg("user", message.strip()))

        ai_status = self.check_ai_connection()
        if not bool(ai_status.get("ok")) and not allow_without_ai:
            assistant_message = (
                "AI 连接测试没有通过。现在不会自动退回本地规则生成，避免让你误以为这是 AI 生成结果。"
                "\n\n你可以先去 AI 配置页检查 API Key、Base URL 和模型；也可以选择“继续不用 AI”，"
                "我会明确按本地规则生成大纲。"
            )
            conversation.append(self._msg("assistant", assistant_message))
            updated = self.storage.update_project(
                project_id,
                {
                    "status": "needs_ai_choice",
                    "conversation": conversation,
                    "ai_status": ai_status,
                },
            )
            if not updated:
                raise ValueError("Project update failed")
            return {
                "project": updated,
                "assistant_message": assistant_message,
                "ai_status": "unavailable",
                "ai_check": ai_status,
                "requires_user_choice": True,
            }

        self._record_generation_stage(
            project_id,
            conversation,
            "正在生成完整 PPT 大纲：根据主题、受众和模板合同组织封面、目录、分节过渡页、正文页和结束页。",
            status="planning",
        )
        try:
            plan = self._build_plan(project, template, conversation, allow_without_ai=allow_without_ai or not bool(ai_status.get("ok")))
        except AIPlanUnavailableError as exc:
            assistant_message = (
                f"{exc}\n\n"
                "这通常表示聊天生成接口不可用、额度不足、模型名不支持，或 AI 返回内容无法解析。"
                "现在不会自动退回本地规则生成；你可以先去 AI 配置页测试连接并检查额度，"
                "也可以选择“继续不用 AI”，我会明确按本地规则生成大纲。"
            )
            conversation.append(self._msg("assistant", assistant_message))
            updated = self.storage.update_project(
                project_id,
                {
                    "status": "needs_ai_choice",
                    "conversation": conversation,
                    "ai_status": {
                        "ok": False,
                        "reason": "generation_unavailable",
                        "message": str(exc),
                    },
                },
            )
            if not updated:
                raise ValueError("Project update failed")
            return {
                "project": updated,
                "assistant_message": assistant_message,
                "ai_status": "unavailable",
                "ai_check": {
                    "ok": False,
                    "reason": "generation_unavailable",
                    "message": str(exc),
                },
                "requires_user_choice": True,
            }
        self._record_generation_stage(
            project_id,
            conversation,
            "正在依据模板合同检查大纲：压缩标题、补足正文细节，并确认每个目录部分都有过渡页。",
            status="planning",
        )
        copy_patterns = self.renderer.copy_pattern_summary(
            template_path=Path(template["pptx_path"]),
            slide_count=max(int(project.get("slide_count") or 0), len(plan.get("slides", [])) if isinstance(plan.get("slides"), list) else 0),
        )
        plan = self._upgrade_plan_quality(plan, project, template, copy_patterns)
        conversation.append(self._msg("assistant", "完整大纲已生成：请先检查下面的大纲，确认后再写入模板生成 PPT。"))
        assistant_message = self._plan_summary(plan)
        conversation.append(self._msg("assistant", assistant_message))

        updated = self.storage.update_project(
            project_id,
            {
                "status": "planned",
                "draft_plan": plan,
                "outline_confirmed": False,
                "conversation": conversation,
            },
        )
        if not updated:
            raise ValueError("Project update failed")
        return {"project": updated, "assistant_message": assistant_message, "plan": plan, "ai_check": ai_status}

    def confirm_project_plan(self, project_id: str) -> Dict[str, object]:
        project = self.storage.get_project(project_id)
        if not project:
            raise ValueError("Project not found")
        plan = project.get("draft_plan")
        if not isinstance(plan, dict) or not isinstance(plan.get("slides"), list) or not plan.get("slides"):
            raise ValueError("请先生成完整大纲，再确认生成 PPT")

        conversation: List[Dict[str, str]] = list(project.get("conversation") or [])
        conversation.append(self._msg("assistant", "已确认当前完整大纲。下一步开始把内容写入模板、运行检查，并生成可下载 PPT。"))
        updated = self.storage.update_project(
            project_id,
            {
                "status": "outline_confirmed",
                "outline_confirmed": True,
                "conversation": conversation,
            },
        )
        if not updated:
            raise ValueError("Project update failed")
        return updated

    def generate_project(self, project_id: str) -> Dict[str, object]:
        project = self.storage.get_project(project_id)
        if not project:
            raise ValueError("Project not found")

        template = self.get_template(str(project["template_id"]))
        if not template:
            raise ValueError("Template not found")

        conversation: List[Dict[str, str]] = list(project.get("conversation") or [])
        plan = project.get("draft_plan")
        if not isinstance(plan, dict) or not plan.get("slides"):
            raise ValueError("请先生成完整大纲，并确认后再生成 PPT")
        if not bool(project.get("outline_confirmed")):
            raise ValueError("请先在对话框确认完整大纲，再生成 PPT")
        self._record_generation_stage(
            project_id,
            conversation,
            "正在匹配模板版式：根据模板合同选择封面、目录、过渡页和正文页。",
        )
        copy_patterns = self.renderer.copy_pattern_summary(
            template_path=Path(template["pptx_path"]),
            slide_count=max(int(project.get("slide_count") or 0), len(plan.get("slides", [])) if isinstance(plan.get("slides"), list) else 0),
        )
        plan = self._upgrade_plan_quality(plan, project, template, copy_patterns)
        plan = self._apply_template_routes(plan, template, copy_patterns, force=True)

        output_path = self.storage.project_output_path(project_id)
        self._record_generation_stage(
            project_id,
            conversation,
            "正在写入 PPTX：把确认后的完整大纲填入模板文本框。",
        )
        render_report = self.renderer.render(
            template_path=Path(template["pptx_path"]),
            plan=plan,
            output_path=output_path,
            template_spec=template.get("spec", {}) if isinstance(template.get("spec"), dict) else {},
        )
        self._record_generation_stage(
            project_id,
            conversation,
            "正在运行版式检查：检查空白文本框、过密页面和生成结果。",
        )
        lint_report = self.linter.lint(output_path)
        conversation.append(self._msg("assistant", "PPT 已生成，可以下载。"))

        updated = self.storage.update_project(
            project_id,
            {
                "status": "generated",
                "plan": plan,
                "draft_plan": plan,
                "outline_confirmed": True,
                "conversation": conversation,
                "render_report": render_report,
                "lint_report": lint_report,
                "output_pptx_path": str(output_path),
            },
        )
        if not updated:
            raise ValueError("Project update failed")
        return updated

    def _record_generation_stage(
        self,
        project_id: str,
        conversation: List[Dict[str, str]],
        message: str,
        status: str = "generating",
    ) -> None:
        conversation.append(self._msg("assistant", message))
        self.storage.update_project(
            project_id,
            {
                "status": status,
                "conversation": conversation,
            },
        )

    def _build_plan(
        self,
        project: Dict[str, object],
        template: Dict[str, object],
        conversation: List[Dict[str, str]],
        allow_without_ai: bool = False,
    ) -> Dict[str, object]:
        topic = str(project["topic"])
        slide_count = int(project["slide_count"])
        audience = str(project.get("audience") or "")
        tone = str(project.get("tone") or "")
        copy_patterns = self.renderer.copy_pattern_summary(
            template_path=Path(template["pptx_path"]),
            slide_count=slide_count,
        )

        ai = self._ai_adapter()

        if allow_without_ai:
            fallback = self.planner.build_fallback_plan(
                topic=topic,
                slide_count=slide_count,
                audience=audience,
                tone=tone,
                conversation=conversation,
                copy_patterns=copy_patterns,
            )
            fallback["source"] = "local_fallback_user_approved"
            return self._apply_template_routes(fallback, template, copy_patterns)

        ai_plan = ai.generate_plan(
            topic=topic,
            slide_count=slide_count,
            template_spec=template.get("spec", {}),
            audience=audience,
            tone=tone,
            conversation=conversation,
            copy_patterns=copy_patterns,
        )
        if ai_plan is None:
            raise AIPlanUnavailableError("AI 已通过基础连接测试，但内容生成接口没有返回可用的大纲。")
        if self._is_plan_on_topic(ai_plan, topic):
            polished = ai.polish_plan(
                topic=topic,
                draft_plan=ai_plan,  # type: ignore[arg-type]
                template_spec=template.get("spec", {}),
                conversation=conversation,
                copy_patterns=copy_patterns,
            )
            if self._is_plan_on_topic(polished, topic):
                return self._apply_template_routes(polished, template, copy_patterns)  # type: ignore[arg-type, return-value]
            return self._apply_template_routes(ai_plan, template, copy_patterns)  # type: ignore[arg-type, return-value]

        if ai_plan:
            retry_conversation = list(conversation)
            retry_conversation.append(self._msg("user", self._topic_guard_retry_prompt(topic)))
            retry_plan = ai.generate_plan(
                topic=topic,
                slide_count=slide_count,
                template_spec=template.get("spec", {}),
                audience=audience,
                tone=tone,
                conversation=retry_conversation,
                copy_patterns=copy_patterns,
            )
            if self._is_plan_on_topic(retry_plan, topic):
                polished_retry = ai.polish_plan(
                    topic=topic,
                    draft_plan=retry_plan,  # type: ignore[arg-type]
                    template_spec=template.get("spec", {}),
                    conversation=retry_conversation,
                    copy_patterns=copy_patterns,
                )
                if self._is_plan_on_topic(polished_retry, topic):
                    return self._apply_template_routes(polished_retry, template, copy_patterns)  # type: ignore[arg-type, return-value]
                if isinstance(retry_plan, dict):
                    retry_plan["source"] = "ai_retry"
                return self._apply_template_routes(retry_plan, template, copy_patterns)  # type: ignore[arg-type, return-value]

        fallback = self.planner.build_fallback_plan(
            topic=topic,
            slide_count=slide_count,
            audience=audience,
            tone=tone,
            conversation=conversation,
            copy_patterns=copy_patterns,
        )
        fallback["source"] = "fallback_topic_guard"
        return self._apply_template_routes(fallback, template, copy_patterns)

    def _ai_adapter(self) -> AIAdapter:
        runtime = self.storage.get_runtime_settings(self.runtime_defaults)
        return AIAdapter(
            api_key=str(runtime.get("openai_api_key") or ""),
            base_url=str(runtime.get("openai_base_url") or self.settings.openai_base_url),
            model=str(runtime.get("openai_model") or self.settings.openai_model),
        )

    def _upgrade_plan_quality(
        self,
        plan: Dict[str, object],
        project: Dict[str, object],
        template: Dict[str, object],
        copy_patterns: List[Dict[str, object]],
    ) -> Dict[str, object]:
        topic = str(project.get("topic") or "")
        audience = str(project.get("audience") or "")
        tone = str(project.get("tone") or "")
        reference_plan = self.planner.build_reference_quality_plan(topic=topic, audience=audience, tone=tone)
        if reference_plan and self._plan_needs_reference_quality_upgrade(plan):
            return self._apply_template_routes(reference_plan, template, copy_patterns, force=True)
        return self._apply_template_routes(plan, template, copy_patterns, force=True)

    @staticmethod
    def _plan_needs_reference_quality_upgrade(plan: Dict[str, object]) -> bool:
        slides = plan.get("slides") if isinstance(plan, dict) else None
        if not isinstance(slides, list):
            return True
        if len(slides) < 20:
            return True
        empty_content = 0
        total_units = 0
        dense_content = 0
        content_count = 0
        for slide in slides:
            if not isinstance(slide, dict):
                continue
            slide_units = len(str(slide.get("title") or "")) + len(str(slide.get("subtitle") or ""))
            points = slide.get("points") if isinstance(slide.get("points"), list) else []
            bullets = slide.get("bullets") if isinstance(slide.get("bullets"), list) else []
            summary = slide.get("summary_items") if isinstance(slide.get("summary_items"), list) else []
            toc_items = slide.get("toc_items") if isinstance(slide.get("toc_items"), list) else []
            for point in points:
                if isinstance(point, dict):
                    slide_units += len(str(point.get("label") or "")) + len(str(point.get("body") or ""))
            slide_units += sum(len(str(item or "")) for item in bullets)
            slide_units += sum(len(str(item or "")) for item in summary)
            slide_units += sum(len(str(item or "")) for item in toc_items)
            total_units += slide_units
            if str(slide.get("prototype_hint") or "").strip() != "content":
                continue
            content_count += 1
            if slide_units >= 170:
                dense_content += 1
            if slide_units < 120:
                empty_content += 1
        if empty_content >= 2:
            return True
        if total_units < 3400:
            return True
        if content_count >= 10 and dense_content < 10:
            return True
        if GenerationService._looks_like_generic_lam_outline(slides):
            return True
        return False

    @staticmethod
    def _looks_like_generic_lam_outline(slides: List[object]) -> bool:
        text_parts: List[str] = []
        title_parts: List[str] = []
        toc_parts: List[str] = []
        for slide in slides:
            if not isinstance(slide, dict):
                continue
            title = str(slide.get("title") or "")
            subtitle = str(slide.get("subtitle") or "")
            title_parts.append(title)
            text_parts.extend([title, subtitle])
            toc_items = slide.get("toc_items") if isinstance(slide.get("toc_items"), list) else []
            for item in toc_items:
                value = str(item or "")
                toc_parts.append(value)
                text_parts.append(value)
            bullets = slide.get("bullets") if isinstance(slide.get("bullets"), list) else []
            summary = slide.get("summary_items") if isinstance(slide.get("summary_items"), list) else []
            text_parts.extend(str(item or "") for item in bullets)
            text_parts.extend(str(item or "") for item in summary)
            points = slide.get("points") if isinstance(slide.get("points"), list) else []
            for point in points:
                if isinstance(point, dict):
                    text_parts.append(str(point.get("label") or ""))
                    text_parts.append(str(point.get("body") or ""))

        full_text = "".join(text_parts)
        compact_text = re.sub(r"\s+", "", full_text).lower()
        if "lam" not in compact_text and "肺淋巴管平滑肌瘤" not in compact_text:
            return False

        narrative_tokens = (
            "小杨",
            "病例",
            "第一幕",
            "第二幕",
            "第三幕",
            "证据链",
            "普通气胸",
            "乳糜胸处理",
            "先救急",
            "再查因",
            "防复发",
            "全程管理",
        )
        narrative_score = sum(1 for token in narrative_tokens if token.lower() in compact_text)
        if narrative_score >= 2:
            return False

        generic_toc_tokens = (
            "疾病概述",
            "疾病概况",
            "病因机制",
            "发病机制",
            "临床诊断",
            "临床表现",
            "诊断治疗",
            "治疗随访",
            "治疗管理",
            "学习要点",
        )
        generic_title_tokens = (
            "基本认识",
            "疾病概述",
            "疾病概况",
            "流行病",
            "分型",
            "遗传",
            "信号通路",
            "组织损伤",
            "临床表现",
            "检查",
            "确诊",
            "治疗策略",
            "随访",
            "学习要点",
        )
        toc_score = sum(1 for item in toc_parts for token in generic_toc_tokens if token in item)
        title_score = sum(1 for title in title_parts for token in generic_title_tokens if token in title)
        content_titles = [
            title
            for slide, title in zip(slides, title_parts)
            if isinstance(slide, dict) and str(slide.get("prototype_hint") or "") == "content"
        ]
        generic_content_titles = sum(
            1
            for title in content_titles
            if any(token in title for token in generic_title_tokens)
        )
        return toc_score >= 3 and title_score >= 6 and generic_content_titles >= 5

    def _standardize_template_with_ai(self, spec: Dict[str, object]) -> Dict[str, object]:
        runtime = self.storage.get_runtime_settings(self.runtime_defaults)
        ai = AIAdapter(
            api_key=str(runtime.get("openai_api_key") or ""),
            base_url=str(runtime.get("openai_base_url") or self.settings.openai_base_url),
            model=str(runtime.get("openai_model") or self.settings.openai_model),
        )
        ai_result = ai.standardize_template(spec)
        if ai_result:
            return ai_result
        return self._local_template_standardization(spec)

    @staticmethod
    def _refresh_local_standardization_summary(template: Dict[str, object]) -> bool:
        spec = template.get("spec")
        if not isinstance(spec, dict):
            return False
        ai = spec.get("ai_standardization")
        if not isinstance(ai, dict) or ai.get("ai_used"):
            return False
        refreshed = GenerationService._local_template_standardization(spec)
        spec["ai_standardization"] = refreshed
        return True

    @staticmethod
    def _local_template_standardization(spec: Dict[str, object]) -> Dict[str, object]:
        prototypes = spec.get("prototypes", []) if isinstance(spec.get("prototypes"), list) else []
        slide_routes: List[Dict[str, object]] = []
        slot_bindings: List[Dict[str, object]] = []
        prototype_indices: List[int] = []
        for prototype in prototypes:
            if not isinstance(prototype, dict):
                continue
            try:
                index = int(prototype.get("index", 0))
            except (TypeError, ValueError):
                continue
            if index > 0:
                prototype_indices.append(index)
        last_prototype_index = max(prototype_indices) if prototype_indices else 0

        for prototype in prototypes:
            if not isinstance(prototype, dict):
                continue
            try:
                index = int(prototype.get("index", 0))
            except (TypeError, ValueError):
                continue
            slots = prototype.get("text_slots", []) if isinstance(prototype.get("text_slots"), list) else []
            body_slots = [
                slot
                for slot in slots
                if isinstance(slot, dict) and str(slot.get("role_hint") or "").strip() in {"body", "meta"}
            ]
            real_body_slots = [
                slot
                for slot in body_slots
                if (
                    int(slot.get("cx") or 0) > 0
                    and int(slot.get("cy") or 0) > 0
                    and int(slot.get("x") or 0) < 100000000
                    and int(slot.get("y") or 0) < 100000000
                )
            ]
            unique_real_positions = {
                (
                    int(slot.get("x") or 0),
                    int(slot.get("y") or 0),
                    int(slot.get("cx") or 0),
                    int(slot.get("cy") or 0),
                )
                for slot in real_body_slots
            }
            label_slot_ids = {
                str(slot.get("slot_id") or "").strip()
                for slot in real_body_slots
                if (
                    int(slot.get("cx") or 0) <= 2400000
                    or str(slot.get("alignment") or "").strip().lower() in {"ctr", "center"}
                )
            }
            detail_slot_ids = {
                str(slot.get("slot_id") or "").strip()
                for slot in real_body_slots
                if int(slot.get("cx") or 0) >= 3200000
            }
            label_only_slot_ids = label_slot_ids - detail_slot_ids
            detail_only_slot_ids = detail_slot_ids - label_slot_ids
            has_label_detail = len(label_only_slot_ids) >= 2 and len(detail_only_slot_ids) >= 2
            has_substantial_body = any(
                int(slot.get("cx") or 0) >= 4200000 and int(slot.get("cy") or 0) >= 650000
                for slot in real_body_slots
            )
            numbered_body_slots = [
                slot
                for slot in real_body_slots
                if re.fullmatch(r"\d{1,2}", str(slot.get("text") or "").strip())
            ]
            medium_body_slots = [
                slot
                for slot in real_body_slots
                if int(slot.get("cx") or 0) >= 1600000 and int(slot.get("cy") or 0) >= 500000
            ]
            has_multi_slot_visual_content = (
                len(real_body_slots) >= 5
                and len(unique_real_positions) >= 4
                and (len(numbered_body_slots) >= 2 or len(medium_body_slots) >= 3)
            )
            dense_label_slot_ids = {
                str(slot.get("slot_id") or "").strip()
                for slot in real_body_slots
                if re.fullmatch(r"\d{1,4}(?:\s*年)?", str(slot.get("text") or "").strip())
                or int(slot.get("cx") or 0) <= 1200000
            }
            dense_detail_slot_ids: set[str] = set()
            dense_seen_detail_positions: set[tuple[int, int, int, int]] = set()
            if has_multi_slot_visual_content:
                for slot in real_body_slots:
                    slot_id = str(slot.get("slot_id") or "").strip()
                    if not slot_id or slot_id in dense_label_slot_ids:
                        continue
                    geometry = (
                        int(slot.get("x") or 0),
                        int(slot.get("y") or 0),
                        int(slot.get("cx") or 0),
                        int(slot.get("cy") or 0),
                    )
                    if int(slot.get("cx") or 0) < 1500000 or int(slot.get("cy") or 0) < 450000:
                        continue
                    if geometry in dense_seen_detail_positions:
                        continue
                    dense_seen_detail_positions.add(geometry)
                    dense_detail_slot_ids.add(slot_id)
            combined_text = "".join(str(slot.get("text") or "") for slot in slots if isinstance(slot, dict))
            looks_like_closing = any(token in combined_text for token in ("谢谢", "谢 谢", "结束", "总结", "Thanks", "Thank"))
            has_presenter_meta = any(
                isinstance(slot, dict) and str(slot.get("role_hint") or "").strip() == "meta"
                for slot in slots
            )
            role = "content"
            pattern = "general"
            if index == 1 or any(isinstance(s, dict) and s.get("role_hint") == "cover_title" for s in slots):
                role = "cover"
                pattern = "cover_toc"
            elif index == 2 or any(isinstance(s, dict) and s.get("role_hint") == "toc_title" for s in slots):
                role = "toc"
                pattern = "cover_toc"
            elif has_label_detail:
                role = "content"
                pattern = "label_detail"
            elif has_multi_slot_visual_content:
                role = "dense_grid"
                pattern = "dense_grid"
            elif index == last_prototype_index and (looks_like_closing or has_presenter_meta or not has_substantial_body):
                role = "closing"
            elif len(real_body_slots) <= 2 and not has_substantial_body:
                role = "section"
            elif len(real_body_slots) >= 6 and len(unique_real_positions) >= 4 and has_substantial_body:
                role = "dense_grid"
                pattern = "dense_grid"
            if role == "content" and not has_substantial_body and not has_label_detail and len(real_body_slots) < 2:
                continue
            if role == "content" and not has_substantial_body and not has_label_detail and len(real_body_slots) >= 2:
                continue
            slide_routes.append({"prototype_index": index, "role": role, "copy_pattern": pattern})

            for slot in slots:
                if not isinstance(slot, dict):
                    continue
                slot_id = str(slot.get("slot_id") or "").strip()
                if not slot_id:
                    continue
                hint = str(slot.get("role_hint") or "").strip()
                text = str(slot.get("text") or "")
                semantic = "body"
                if role == "section" and hint in {"page_title", "cover_title", "body"}:
                    semantic = "section_title"
                elif role == "closing" and hint in {"body", "page_title", "cover_title"} and int(slot.get("cy") or 0) >= 700000:
                    semantic = "closing_message"
                elif hint == "cover_title":
                    semantic = "deck_title"
                elif hint == "toc_title":
                    semantic = "page_title" if role == "toc" else "toc_item"
                elif hint == "page_title":
                    semantic = "page_title"
                elif role == "cover" and hint == "body":
                    semantic = "subtitle"
                elif role == "toc" and hint == "body":
                    semantic = "toc_item"
                elif role == "content" and pattern == "label_detail" and hint == "body" and slot_id in label_only_slot_ids:
                    semantic = "point_label"
                elif role == "content" and pattern == "label_detail" and hint in {"body", "meta"} and slot_id in detail_only_slot_ids:
                    semantic = "point_body"
                elif role == "dense_grid" and slot_id in dense_label_slot_ids:
                    semantic = "point_label"
                elif role == "dense_grid" and slot_id in dense_detail_slot_ids:
                    semantic = "point_body"
                elif role == "dense_grid" and hint in {"body", "meta"}:
                    semantic = "ignore"
                elif role == "content" and hint == "meta" and slot_id in detail_slot_ids:
                    semantic = "body"
                elif hint == "meta" and any(token in text for token in ("汇报人", "报告人")):
                    semantic = "presenter"
                elif hint == "meta" and any(token in text for token in ("日期", "时间")):
                    semantic = "date"
                elif hint == "meta":
                    semantic = "body" if role == "content" else "presenter"
                try:
                    font_size = float(slot.get("font_size_pt") or 16)
                except (TypeError, ValueError):
                    font_size = 16.0
                slot_bindings.append(
                    {
                        "prototype_index": index,
                        "slot_id": slot_id,
                        "semantic": semantic,
                        "min_font_size_pt": max(16, int(font_size) if font_size.is_integer() else font_size),
                    }
                )

        return {
            "agent": "template_standardization_agent",
            "ai_used": False,
            "summary": "已生成本地标准化合同：保留文本框、字号、字体和位置；配置 API Key 后可升级为 AI 标准化。",
            "deck_flow": ["cover", "toc", "section", "content", "closing"],
            "layout_roles": [],
            "slide_routes": slide_routes[:30],
            "slot_bindings": slot_bindings[:120],
            "content_rules": {
                "min_body_font_size_pt": 16,
                "toc_title_max_chars": 14,
                "prefer_varied_content_layouts": True,
                "allow_layout_adaptation": True,
            },
            "normalization_notes": [
                "本地解析已提取每个文本框的位置、字号、字体、占位符和角色线索。",
                "配置 API Key 后重新上传可让 AI 进一步识别封面、目录、过渡页、正文页和结束页。",
            ],
        }

    @staticmethod
    def _build_template_preview_plan(template: Dict[str, object]) -> Dict[str, object]:
        spec = template.get("spec", {}) if isinstance(template.get("spec"), dict) else {}
        ai = spec.get("ai_standardization", {}) if isinstance(spec.get("ai_standardization"), dict) else {}
        routes = ai.get("slide_routes", []) if isinstance(ai.get("slide_routes"), list) else []
        route_by_index = {}
        for item in routes:
            if not isinstance(item, dict):
                continue
            try:
                route_by_index[int(item.get("prototype_index", 0))] = item
            except (TypeError, ValueError):
                continue

        slide_count = int(spec.get("slide_count") or 0)
        slide_count = max(4, min(slide_count or 8, 12))
        role_names = {
            "cover": "封面",
            "toc": "目录",
            "section": "章节",
            "content": "正文",
            "process": "流程",
            "dense_grid": "信息矩阵",
            "label_detail": "标签说明",
        }
        pattern_notes = {
            "cover_toc": ["标题区用于主题", "副标题区用于说明", "适合封面或目录"],
            "label_detail": ["短标签放在小框", "说明文字放在大框", "保持一组一义"],
            "process": ["按阶段写动作", "按顺序呈现路径", "突出输入和结果"],
            "dense_grid": ["每格保持短句", "指标并列呈现", "避免长段文字"],
            "general": ["标题加正文", "保留版式层级", "用于通用内容页"],
        }

        slides = []
        for index in range(1, slide_count + 1):
            route = route_by_index.get(index, {})
            role = str(route.get("role") or ("cover" if index == 1 else "toc" if index == 2 else "content"))
            pattern = str(route.get("copy_pattern") or ("cover_toc" if index <= 2 else "general"))
            if pattern not in pattern_notes:
                pattern = "general"
            role_label = role_names.get(role, "正文")
            prototype_hint = role if role in {"cover", "toc", "section", "content", "closing"} else "content"
            slides.append(
                {
                    "index": index,
                    "title": f"标准化预览：{role_label}页",
                    "bullets": [
                        f"版式角色：{role_label}",
                        f"写作模式：{pattern}",
                        *pattern_notes[pattern],
                    ][:6],
                    "prototype_index": index,
                    "prototype_hint": prototype_hint,
                    "copy_pattern": pattern,
                }
            )

        return {
            "deck_title": "模板标准化预览",
            "slides": slides,
            "source": "template_standardization_preview",
        }

    @staticmethod
    def _msg(role: str, content: str) -> Dict[str, str]:
        return {
            "role": role,
            "content": content,
            "ts": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def _apply_template_routes(
        plan: Dict[str, object],
        template: Dict[str, object],
        copy_patterns: List[Dict[str, object]],
        force: bool = False,
    ) -> Dict[str, object]:
        plan = GenerationService._apply_copy_patterns(plan, copy_patterns)
        slides = plan.get("slides")
        if not isinstance(slides, list):
            return plan
        AIAdapter._enforce_section_transitions(slides)  # type: ignore[arg-type]
        plan = GenerationService._split_overfull_content_slides(plan)
        slides = plan.get("slides")
        if not isinstance(slides, list):
            return plan

        spec = template.get("spec", {}) if isinstance(template.get("spec"), dict) else {}
        advanced_reference_routing = any(
            isinstance(slide, dict)
            and any(token in str(slide.get("title") or "") for token in ("LAM", "小杨", "乳糜胸", "西罗莫司"))
            for slide in slides
        )
        ai = spec.get("ai_standardization", {}) if isinstance(spec.get("ai_standardization"), dict) else {}
        prototypes = spec.get("prototypes", []) if isinstance(spec.get("prototypes"), list) else []
        capacity_by_index: Dict[int, int] = {}
        for prototype in prototypes:
            if not isinstance(prototype, dict):
                continue
            try:
                prototype_index = int(prototype.get("index", 0) or 0)
            except (TypeError, ValueError):
                continue
            slots = prototype.get("text_slots", []) if isinstance(prototype.get("text_slots"), list) else []
            capacity = 0
            for slot in slots:
                if not isinstance(slot, dict):
                    continue
                hint = str(slot.get("role_hint") or "").strip()
                if hint != "body":
                    continue
                try:
                    cx = int(slot.get("cx") or 0)
                    cy = int(slot.get("cy") or 0)
                    x = int(slot.get("x") or 0)
                    y = int(slot.get("y") or 0)
                except (TypeError, ValueError):
                    continue
                if cx <= 0 or cy <= 0 or x >= 100000000 or y >= 100000000:
                    continue
                width_units = cx / 110000
                height_units = cy / 260000
                capacity += max(10, min(220, int(width_units * max(1.0, height_units) * 1.35)))
            if prototype_index > 0:
                capacity_by_index[prototype_index] = capacity
        routes = ai.get("slide_routes", []) if isinstance(ai.get("slide_routes"), list) else []
        slot_geometry_by_index: Dict[tuple[int, str], tuple[int, int, int, int]] = {}
        visible_body_geometries_by_index: Dict[int, List[tuple[int, int, int, int]]] = {}
        for prototype in prototypes:
            if not isinstance(prototype, dict):
                continue
            try:
                prototype_index = int(prototype.get("index", 0) or 0)
            except (TypeError, ValueError):
                continue
            slots = prototype.get("text_slots", []) if isinstance(prototype.get("text_slots"), list) else []
            for slot in slots:
                if not isinstance(slot, dict):
                    continue
                slot_id = str(slot.get("slot_id") or "").strip()
                if not slot_id:
                    continue
                try:
                    geometry = (
                        int(slot.get("x") or 0),
                        int(slot.get("y") or 0),
                        int(slot.get("cx") or 0),
                        int(slot.get("cy") or 0),
                    )
                    slot_geometry_by_index[(prototype_index, slot_id)] = geometry
                except (TypeError, ValueError):
                    continue
                hint = str(slot.get("role_hint") or "").strip()
                x, y, cx, cy = geometry
                if hint in {"body", "meta"} and cx > 0 and cy > 0 and x < 100000000 and y < 100000000:
                    visible_body_geometries_by_index.setdefault(prototype_index, []).append(geometry)
        point_pair_count_by_index: Dict[int, int] = {}
        bindings = ai.get("slot_bindings", []) if isinstance(ai.get("slot_bindings"), list) else []
        label_geometries_by_index: Dict[int, set[tuple[int, int, int, int]]] = {}
        body_geometries_by_index: Dict[int, set[tuple[int, int, int, int]]] = {}
        point_body_capacity_by_index: Dict[int, int] = {}
        unsafe_label_detail_indices: set[int] = set()
        for binding in bindings:
            if not isinstance(binding, dict):
                continue
            try:
                prototype_index = int(binding.get("prototype_index", 0) or 0)
            except (TypeError, ValueError):
                continue
            slot_id = str(binding.get("slot_id") or "").strip()
            geometry = slot_geometry_by_index.get((prototype_index, slot_id), (prototype_index, len(slot_id), 0, 0))
            semantic = str(binding.get("semantic") or "").strip()
            if semantic == "point_label":
                label_geometries_by_index.setdefault(prototype_index, set()).add(geometry)
            elif semantic == "point_body":
                body_geometries = body_geometries_by_index.setdefault(prototype_index, set())
                if geometry not in body_geometries:
                    _x, _y, cx, cy = geometry
                    if cx > 0 and cy > 0:
                        width_units = cx / 110000
                        height_units = cy / 260000
                        point_body_capacity_by_index[prototype_index] = point_body_capacity_by_index.get(prototype_index, 0) + max(
                            10,
                            min(220, int(width_units * max(1.0, height_units) * 1.35)),
                        )
                        if _y >= 5400000 and cx >= 8000000 and cy <= 800000:
                            unsafe_label_detail_indices.add(prototype_index)
                body_geometries.add(geometry)
        for prototype_index in set(label_geometries_by_index) | set(body_geometries_by_index):
            point_pair_count_by_index[prototype_index] = min(
                len(label_geometries_by_index.get(prototype_index, set())),
                len(body_geometries_by_index.get(prototype_index, set())),
            )
        compact_visual_indices: set[int] = set()
        full_page_text_indices: set[int] = set()
        blob_prone_text_indices: set[int] = set()
        transition_visual_indices: set[int] = set()
        for prototype_index, geometries in visible_body_geometries_by_index.items():
            square_cards = [
                geometry
                for geometry in geometries
                if 1800000 <= geometry[2] <= 3400000 and 1800000 <= geometry[3] <= 3400000
            ]
            footer_bars = [
                geometry
                for geometry in geometries
                if geometry[1] >= 4300000 and geometry[2] >= 8000000 and geometry[3] <= 1800000
            ]
            if len(square_cards) >= 3 and footer_bars:
                compact_visual_indices.add(prototype_index)
            if any(cx >= 8000000 and cy >= 3000000 for _x, _y, cx, cy in geometries):
                full_page_text_indices.add(prototype_index)
                blob_prone_text_indices.add(prototype_index)
            substantial_positions = {
                geometry
                for geometry in geometries
                if geometry[2] >= 3800000 and geometry[3] >= 1100000
            }
            if len(geometries) >= 4 and len(substantial_positions) <= 2:
                blob_prone_text_indices.add(prototype_index)
        low_effective_capacity_indices: set[int] = set()
        for prototype_index, geometries in visible_body_geometries_by_index.items():
            large_slots = [
                geometry
                for geometry in geometries
                if geometry[2] >= 7000000 and geometry[3] >= 1100000
            ]
            distinct_substantial = {
                geometry
                for geometry in geometries
                if geometry[2] >= 1800000 and geometry[3] >= 700000
            }
            if len(geometries) >= 2 and len(large_slots) <= 1 and len(distinct_substantial) <= 2:
                low_effective_capacity_indices.add(prototype_index)
        for prototype in prototypes:
            if not isinstance(prototype, dict):
                continue
            try:
                prototype_index = int(prototype.get("index", 0) or 0)
            except (TypeError, ValueError):
                continue
            slots = prototype.get("text_slots", []) if isinstance(prototype.get("text_slots"), list) else []
            visible_body_texts = []
            for slot in slots:
                if not isinstance(slot, dict):
                    continue
                if str(slot.get("role_hint") or "").strip() != "body":
                    continue
                try:
                    x = int(slot.get("x") or 0)
                    y = int(slot.get("y") or 0)
                    cx = int(slot.get("cx") or 0)
                    cy = int(slot.get("cy") or 0)
                except (TypeError, ValueError):
                    continue
                if cx <= 0 or cy <= 0 or x >= 100000000 or y >= 100000000:
                    continue
                visible_body_texts.append(str(slot.get("text") or "").strip())
            if len(visible_body_texts) >= 2 and any(re.fullmatch(r"\d{1,2}", text) for text in visible_body_texts):
                transition_visual_indices.add(prototype_index)
        normalized_routes: List[Dict[str, object]] = []
        for item in routes:
            if not isinstance(item, dict):
                continue
            try:
                prototype_index = int(item.get("prototype_index", 0) or 0)
            except (TypeError, ValueError):
                continue
            if prototype_index <= 0:
                continue
            role = str(item.get("role") or "content").strip() or "content"
            pattern = str(item.get("copy_pattern") or "general").strip() or "general"
            if role == "content" and pattern == "label_detail" and prototype_index in unsafe_label_detail_indices:
                pattern = "general"
            capacity = capacity_by_index.get(prototype_index, 0)
            if pattern == "label_detail" and point_body_capacity_by_index.get(prototype_index):
                capacity = point_body_capacity_by_index[prototype_index]
            normalized_routes.append(
                {
                    "prototype_index": prototype_index,
                    "role": role,
                    "copy_pattern": pattern,
                    "capacity": capacity,
                    "point_pairs": point_pair_count_by_index.get(prototype_index, 0),
                }
            )
        if not normalized_routes:
            return plan

        used: set[int] = set()
        usage: Dict[int, int] = {}

        def mark_used(prototype_index: int) -> None:
            used.add(prototype_index)
            usage[prototype_index] = usage.get(prototype_index, 0) + 1

        def slide_role(index: int, slide: Dict[str, object]) -> str:
            hint = str(slide.get("prototype_hint") or "").strip().lower()
            if index == 1:
                return "cover"
            if index == 2:
                return "toc"
            if index == len(slides):
                if hint in {"closing", "end"} or slide.get("summary_items"):
                    return "closing"
            if hint in {"cover", "toc", "section", "content", "process", "dense_grid", "label_detail", "closing", "reference"}:
                return hint
            if slide.get("toc_items"):
                return "toc"
            if slide.get("section_title") and not slide.get("points"):
                return "section"
            return "content"

        def choose_route(
            role: str,
            pattern: str,
            avoid_dense_grid: bool = False,
            avoid_label_detail: bool = False,
            demand: int = 0,
            point_count: int = 0,
        ) -> Dict[str, object] | None:
            def needed_capacity_for(route_demand: int) -> int:
                if route_demand <= 0:
                    return 0
                if route_demand >= 180:
                    return route_demand * 2
                if route_demand >= 60:
                    return int(route_demand * 1.5)
                return route_demand

            content_like = {"content", "process", "dense_grid", "label_detail"}
            reusable_roles = {*content_like, "section"}
            allowed_content_roles = content_like - ({"dense_grid"} if avoid_dense_grid else set())
            if avoid_label_detail:
                allowed_content_roles -= {"label_detail"}
            if (
                not advanced_reference_routing
                and role in content_like
                and pattern == "general"
                and demand >= 120
            ):
                general_capacity_routes = [
                    r
                    for r in normalized_routes
                    if str(r.get("role") or "") in allowed_content_roles
                    and str(r.get("copy_pattern") or "") == "general"
                ]
                if general_capacity_routes:
                    return max(
                        general_capacity_routes,
                        key=lambda r: (
                            int(r.get("capacity") or 0),
                            int(r["prototype_index"]),
                        ),
                    )
            if advanced_reference_routing and role in content_like and point_count >= 3:
                needed_capacity = needed_capacity_for(demand)
                structured_candidates = []
                for route in normalized_routes:
                    route_role = str(route.get("role") or "")
                    route_pattern = str(route.get("copy_pattern") or "")
                    route_index = int(route.get("prototype_index") or 0)
                    route_capacity = int(route.get("capacity") or 0)
                    route_pairs = int(route.get("point_pairs") or 0)
                    if route_role not in allowed_content_roles:
                        continue
                    if route_pattern == "dense_grid" and usage.get(route_index, 0) >= 3:
                        continue
                    if route_pattern == "label_detail":
                        if route_index in blob_prone_text_indices:
                            continue
                        if route_index in point_pair_count_by_index and route_pairs < min(point_count, 4):
                            continue
                    elif route_pattern == "dense_grid" or route_role == "dense_grid":
                        if route_pairs < min(point_count, 3) and route_capacity <= 0:
                            continue
                    elif route_pattern == "general":
                        if route_index in blob_prone_text_indices:
                            continue
                        if route_index in low_effective_capacity_indices:
                            continue
                        if route_capacity < max(120, min(needed_capacity, 180)):
                            continue
                    else:
                        continue
                    if demand and route_capacity and route_capacity < min(needed_capacity, 120):
                        continue
                    structured_candidates.append(route)
                if structured_candidates:
                    return min(
                        structured_candidates,
                        key=lambda r: (
                            0 if usage.get(int(r["prototype_index"]), 0) == 0 else 1,
                            0 if str(r.get("copy_pattern") or "") == pattern else 1,
                            0 if str(r.get("copy_pattern") or "") == "label_detail" else 1,
                            0 if int(r.get("point_pairs") or 0) >= min(point_count, 4) else 1,
                            usage.get(int(r["prototype_index"]), 0),
                            -int(r.get("point_pairs") or 0),
                            int(r.get("capacity") or 0),
                            int(r["prototype_index"]),
                        ),
                    )
            if role in content_like:
                pools = [
                    [r for r in normalized_routes if r["role"] == role and r["copy_pattern"] == pattern],
                    [r for r in normalized_routes if r["role"] in allowed_content_roles and r["copy_pattern"] == pattern],
                    [r for r in normalized_routes if r["role"] == role],
                    [r for r in normalized_routes if r["role"] in allowed_content_roles],
                ]
            else:
                pools = [
                    [r for r in normalized_routes if r["role"] == role and r["copy_pattern"] == pattern],
                    [r for r in normalized_routes if r["role"] == role],
                    [r for r in normalized_routes if r["copy_pattern"] == pattern],
                ]
            if role in content_like and demand >= 120 and point_count < 3:
                rich_general = [
                    r
                    for r in normalized_routes
                    if str(r.get("role") or "") in allowed_content_roles
                    and str(r.get("copy_pattern") or "") == pattern
                    and int(r.get("prototype_index") or 0) not in low_effective_capacity_indices
                ]
                if rich_general:
                    if not advanced_reference_routing and point_count == 0:
                        return max(
                            rich_general,
                            key=lambda r: (
                                int(r.get("capacity") or 0),
                                int(r["prototype_index"]),
                            ),
                        )
                    pools.insert(0, rich_general)
            for pool in pools:
                if role == "section":
                    visible_pool = [r for r in pool if int(r.get("capacity") or 0) > 0]
                    if visible_pool:
                        pool = visible_pool
                if role in reusable_roles:
                    available = list(pool)
                else:
                    available = [r for r in pool if int(r["prototype_index"]) not in used]
                if available:
                    if role in content_like and point_count >= 3:
                        available = [
                            r
                            for r in available
                            if not (
                                str(r.get("copy_pattern") or "") == "label_detail"
                                and int(r["prototype_index"]) in point_pair_count_by_index
                                and int(r.get("point_pairs") or 0) < min(point_count, 4)
                            )
                        ]
                        if not available:
                            continue
                    if role == "section":
                        return min(
                            available,
                            key=lambda r: (
                                0 if int(r["prototype_index"]) in transition_visual_indices else 1,
                                usage.get(int(r["prototype_index"]), 0),
                                0 if int(r.get("capacity") or 0) > 0 else 1,
                                int(r.get("capacity") or 0),
                                int(r["prototype_index"]),
                            ),
                        )
                    if role in content_like:
                        if point_count >= 3 or demand >= 120:
                            non_compact_available = [
                                r
                                for r in available
                                if int(r["prototype_index"]) not in compact_visual_indices
                            ]
                            compact_unused = [
                                r
                                for r in available
                                if int(r["prototype_index"]) in compact_visual_indices
                                and usage.get(int(r["prototype_index"]), 0) == 0
                            ]
                            preferred_non_compact = non_compact_available
                            if demand:
                                needed_capacity = needed_capacity_for(demand)
                                preferred_non_compact = [
                                    r
                                    for r in preferred_non_compact
                                    if int(r.get("capacity") or 0) >= needed_capacity
                                ]
                            if point_count >= 3:
                                preferred_non_compact = [
                                    r
                                    for r in non_compact_available
                                    if (
                                        (
                                            str(r.get("copy_pattern") or "") == "label_detail"
                                            and (
                                                int(r["prototype_index"]) not in point_pair_count_by_index
                                                or int(r.get("point_pairs") or 0) >= min(point_count, 4)
                                            )
                                        )
                                        or (
                                            str(r.get("copy_pattern") or "") != "label_detail"
                                            and (
                                                str(r.get("copy_pattern") or "") == "dense_grid"
                                                or str(r.get("role") or "") == "dense_grid"
                                                or int(r["prototype_index"]) in compact_visual_indices
                                                or
                                                str(r.get("copy_pattern") or "") == "general"
                                                or int(r["prototype_index"]) in full_page_text_indices
                                            )
                                        )
                                    )
                                    and (
                                        not demand
                                        or int(r.get("capacity") or 0) >= needed_capacity_for(demand)
                                    )
                                ]
                            if non_compact_available and (
                                any(usage.get(int(r["prototype_index"]), 0) == 0 for r in preferred_non_compact)
                                or not compact_unused
                            ):
                                available = non_compact_available
                            elif not non_compact_available:
                                continue
                        if point_count >= 3:
                            available = [
                                r
                                for r in available
                                if (
                                    (
                                        str(r.get("copy_pattern") or "") == "label_detail"
                                        and (
                                            int(r["prototype_index"]) not in point_pair_count_by_index
                                            or int(r.get("point_pairs") or 0) >= min(point_count, 4)
                                        )
                                    )
                                    or (
                                        str(r.get("copy_pattern") or "") != "label_detail"
                                        and (
                                            str(r.get("copy_pattern") or "") == "dense_grid"
                                            or str(r.get("role") or "") == "dense_grid"
                                            or int(r["prototype_index"]) in compact_visual_indices
                                            or
                                            str(r.get("copy_pattern") or "") == "general"
                                            or int(r["prototype_index"]) in full_page_text_indices
                                        )
                                    )
                                )
                            ]
                            non_blob_available = [
                                r
                                for r in available
                                if int(r["prototype_index"]) not in blob_prone_text_indices
                            ]
                            if non_blob_available:
                                available = non_blob_available
                            if not available:
                                continue
                        unused = [r for r in available if usage.get(int(r["prototype_index"]), 0) == 0]
                        if unused:
                            def adequate(route: Dict[str, object]) -> bool:
                                if (
                                    point_count
                                    and str(route.get("copy_pattern") or "") == "label_detail"
                                    and int(route.get("point_pairs") or 0) < min(point_count, 4)
                                ):
                                    return False
                                if demand:
                                    needed = needed_capacity_for(demand)
                                    if int(route.get("capacity") or 0) < needed:
                                        return False
                                return True

                            adequate_unused = [r for r in unused if adequate(r)]
                            adequate_available = [r for r in available if adequate(r)]
                            if adequate_unused:
                                available = adequate_unused
                            elif demand >= 220 and adequate_available:
                                available = adequate_available
                            elif adequate_available:
                                available = adequate_available
                            else:
                                available = adequate_available if adequate_available else unused
                        elif pool is not pools[-1]:
                            continue
                    return min(
                        available,
                        key=lambda r: (
                            0
                            if not demand
                            or int(r.get("capacity") or 0) >= needed_capacity_for(demand)
                            else 1,
                            usage.get(int(r["prototype_index"]), 0),
                            0
                            if (
                                not point_count
                                or str(r.get("copy_pattern") or "") != "label_detail"
                                or int(r.get("point_pairs") or 0) >= point_count
                            )
                            else 1,
                            0 if str(r.get("copy_pattern") or "") == pattern else 1,
                            -int(r.get("point_pairs") or 0) if point_count else 0,
                            int(r.get("capacity") or 0) if demand else 0,
                            int(r["prototype_index"]),
                        ),
                    )
            return None

        def slide_text_units(slide: Dict[str, object]) -> int:
            units = len(str(slide.get("title") or "")) + len(str(slide.get("subtitle") or ""))
            bullets = slide.get("bullets") if isinstance(slide.get("bullets"), list) else []
            summary_items = slide.get("summary_items") if isinstance(slide.get("summary_items"), list) else []
            units += sum(len(str(item or "")) for item in bullets)
            units += sum(len(str(item or "")) for item in summary_items)
            points = slide.get("points") if isinstance(slide.get("points"), list) else []
            for point in points:
                if isinstance(point, dict):
                    units += len(str(point.get("label") or "")) + len(str(point.get("body") or ""))
            return units

        def pad_label_detail_points(slide: Dict[str, object], route: Dict[str, object]) -> None:
            if str(route.get("copy_pattern") or "") != "label_detail":
                return
            target_pairs = int(route.get("point_pairs") or 0)
            if target_pairs <= 0 or target_pairs > 4:
                return
            points = slide.get("points") if isinstance(slide.get("points"), list) else []
            if not points or len(points) >= target_pairs:
                return
            title = str(slide.get("title") or "").strip()
            section = str(slide.get("section_title") or title).strip()
            supplement_bodies = [
                f"围绕{section or title or '本页'}补充判断依据、风险边界和下一步处理，使页面四个文本框都形成完整讲解闭环。",
                f"将{title or section or '本页'}与前后章节串联，说明该要点对诊断、治疗或随访决策的具体影响。",
            ]
            while len(points) < target_pairs:
                body = supplement_bodies[(len(points) - 1) % len(supplement_bodies)]
                points.append({"label": "补充提示", "body": body})
            slide["points"] = points

        def convert_bullets_to_label_detail_points(slide: Dict[str, object], route: Dict[str, object]) -> None:
            if str(route.get("copy_pattern") or "") != "label_detail":
                return
            existing_points = slide.get("points") if isinstance(slide.get("points"), list) else []
            if existing_points:
                return
            bullets = slide.get("bullets") if isinstance(slide.get("bullets"), list) else []
            clean_bullets = [str(item or "").strip() for item in bullets if str(item or "").strip()]
            if not clean_bullets:
                return

            points: List[Dict[str, str]] = []
            for item in clean_bullets:
                label = ""
                body = item
                match = re.match(r"^([^:：]{2,18})[:：]\s*(.+)$", item)
                if match:
                    label = match.group(1).strip()
                    body = match.group(2).strip()
                else:
                    compact = re.sub(r"\s+", " ", item).strip()
                    if re.search(r"[A-Za-z]", compact):
                        label = " ".join(compact.split()[:3]).strip("，,。.;；:：")
                    else:
                        label = compact[:10].strip("，,。.;；:：")
                if not label:
                    label = "要点"
                if not body:
                    body = item
                points.append({"label": label, "body": body})

            slide["points"] = points
            slide["bullets"] = []

        section_counter = 0
        for index, raw_slide in enumerate(slides, start=1):
            if not isinstance(raw_slide, dict):
                continue
            existing = raw_slide.get("prototype_index")
            try:
                existing_index = int(existing or 0)
            except (TypeError, ValueError):
                existing_index = 0
            if existing_index > 0 and not force:
                mark_used(existing_index)
                continue

            pattern = str(raw_slide.get("copy_pattern") or "general").strip() or "general"
            role = slide_role(index, raw_slide)
            if role == "section":
                section_counter += 1
                raw_slide["section_number"] = str(section_counter)
            if role == "content":
                points = raw_slide.get("points") if isinstance(raw_slide.get("points"), list) else []
                bullets = raw_slide.get("bullets") if isinstance(raw_slide.get("bullets"), list) else []
                has_label_detail_route = any(r["role"] == "content" and r["copy_pattern"] == "label_detail" for r in normalized_routes)
                has_dense_route = any(r["role"] == "dense_grid" or r["copy_pattern"] == "dense_grid" for r in normalized_routes)
                if len(points) >= 6 and has_dense_route:
                    pattern = "dense_grid"
                elif len(points) >= 2 and has_label_detail_route:
                    pattern = "label_detail"
            if role == "closing":
                summary_items = raw_slide.get("summary_items") if isinstance(raw_slide.get("summary_items"), list) else []
                points = raw_slide.get("points") if isinstance(raw_slide.get("points"), list) else []
                has_label_detail_route = any(r["role"] == "content" and r["copy_pattern"] == "label_detail" for r in normalized_routes)
                has_closing_route = any(r["role"] == "closing" for r in normalized_routes)
                if (len(summary_items) > 1 or len(points) > 1) and has_label_detail_route:
                    role = "content"
                    pattern = "label_detail"
                    raw_slide["_semantic_role"] = "closing"
            if role == "reference":
                role = "content"
                pattern = "general"
                raw_slide["_semantic_role"] = "reference"
            slide_points = raw_slide.get("points") if isinstance(raw_slide.get("points"), list) else []
            slide_bullets = raw_slide.get("bullets") if isinstance(raw_slide.get("bullets"), list) else []
            avoid_dense_grid = role == "content" and not slide_points
            avoid_label_detail = role == "content" and not slide_points and len(slide_bullets) < 2
            demand = slide_text_units(raw_slide) if role in {"content", "process", "dense_grid", "label_detail"} else 0
            effective_point_count = len(slide_points) or (len(slide_bullets) if role == "content" else 0)
            if role in {"content", "process", "dense_grid", "label_detail"} and len(slide_bullets) >= 3:
                demand = max(demand, 120)
            preferred_route: Dict[str, object] | None = None
            try:
                preferred_index = int(raw_slide.get("preferred_prototype_index") or 0)
            except (TypeError, ValueError):
                preferred_index = 0
            if role in {"content", "process", "dense_grid", "label_detail", "section"} and preferred_index > 0:
                for candidate in normalized_routes:
                    if int(candidate.get("prototype_index") or 0) != preferred_index:
                        continue
                    if role == "section" and str(candidate.get("role") or "") != "section":
                        continue
                    if role in {"content", "process", "dense_grid", "label_detail"} and str(candidate.get("role") or "") not in {"content", "process", "dense_grid", "label_detail"}:
                        continue
                    if (
                        effective_point_count >= 3
                        and str(candidate.get("copy_pattern") or "") == "label_detail"
                        and int(candidate.get("prototype_index") or 0) in point_pair_count_by_index
                        and int(candidate.get("point_pairs") or 0) < min(effective_point_count, 4)
                    ):
                        continue
                    if (
                        demand
                        and str(candidate.get("copy_pattern") or "") == "label_detail"
                        and int(candidate.get("point_pairs") or 0) >= max(1, min(effective_point_count, 4))
                    ):
                        preferred_route = candidate
                        break
                    if (
                        demand
                        and str(candidate.get("copy_pattern") or "") != "label_detail"
                        and preferred_index in full_page_text_indices
                        and effective_point_count < 3
                    ):
                        preferred_route = candidate
                        break
                    if (
                        effective_point_count >= 3
                        and str(candidate.get("copy_pattern") or "") != "label_detail"
                        and preferred_index in blob_prone_text_indices
                    ):
                        continue
                    if demand and int(candidate.get("capacity") or 0) < int(demand * 0.6):
                        continue
                    preferred_route = candidate
                    break
            route = preferred_route or choose_route(
                role,
                pattern,
                avoid_dense_grid=avoid_dense_grid,
                avoid_label_detail=avoid_label_detail,
                demand=demand,
                point_count=effective_point_count,
            )
            if (
                advanced_reference_routing
                and
                route
                and role in {"content", "process", "dense_grid", "label_detail"}
                and effective_point_count >= 3
                and (
                    int(route.get("capacity") or 0) < 120
                    or int(route.get("prototype_index") or 0) in low_effective_capacity_indices
                )
            ):
                structured_fallbacks = [
                    candidate
                    for candidate in normalized_routes
                    if str(candidate.get("role") or "") in {"content", "process", "dense_grid", "label_detail"}
                    and str(candidate.get("copy_pattern") or "") in {"label_detail", "dense_grid"}
                    and (
                        int(candidate.get("capacity") or 0) >= 120
                        or str(candidate.get("copy_pattern") or "") == "label_detail"
                    )
                    and int(candidate.get("prototype_index") or 0) not in blob_prone_text_indices
                    and (
                        str(candidate.get("copy_pattern") or "") != "label_detail"
                        or int(candidate.get("point_pairs") or 0) >= min(effective_point_count, 4)
                    )
                ]
                if not structured_fallbacks:
                    structured_fallbacks = [
                        candidate
                        for candidate in normalized_routes
                        if str(candidate.get("copy_pattern") or "") == "label_detail"
                        and int(candidate.get("prototype_index") or 0) not in blob_prone_text_indices
                        and int(candidate.get("point_pairs") or 0) >= 3
                    ]
                if structured_fallbacks:
                    route = min(
                        structured_fallbacks,
                        key=lambda candidate: (
                            usage.get(int(candidate["prototype_index"]), 0),
                            0 if str(candidate.get("copy_pattern") or "") == "label_detail" else 1,
                            -int(candidate.get("point_pairs") or 0),
                            int(candidate.get("prototype_index") or 0),
                        ),
                    )
            if not route:
                continue
            route_points = raw_slide.get("points") if isinstance(raw_slide.get("points"), list) else []
            route_bullets = raw_slide.get("bullets") if isinstance(raw_slide.get("bullets"), list) else []
            route_point_count = len(route_points) or (len(route_bullets) if role == "content" else 0)
            if (
                role in {"content", "process", "dense_grid", "label_detail"}
                and route_point_count >= 3
                and (
                    int(route.get("prototype_index") or 0) in low_effective_capacity_indices
                )
            ):
                last_chance_routes = [
                    candidate
                    for candidate in normalized_routes
                    if str(candidate.get("role") or "") in {"content", "process", "dense_grid", "label_detail"}
                    and str(candidate.get("copy_pattern") or "") in {"label_detail", "dense_grid"}
                    and int(candidate.get("prototype_index") or 0) not in low_effective_capacity_indices
                    and int(candidate.get("prototype_index") or 0) not in blob_prone_text_indices
                    and (
                        str(candidate.get("copy_pattern") or "") != "label_detail"
                        or int(candidate.get("point_pairs") or 0) >= min(route_point_count, 4)
                    )
                ]
                if last_chance_routes:
                    route = min(
                        last_chance_routes,
                        key=lambda candidate: (
                            usage.get(int(candidate["prototype_index"]), 0),
                            0 if str(candidate.get("copy_pattern") or "") == "label_detail" else 1,
                            -int(candidate.get("point_pairs") or 0),
                            int(candidate.get("prototype_index") or 0),
                        ),
                    )
            prototype_index = int(route["prototype_index"])
            mark_used(prototype_index)
            raw_slide["prototype_index"] = prototype_index
            raw_slide["copy_pattern"] = str(route.get("copy_pattern") or pattern)
            convert_bullets_to_label_detail_points(raw_slide, route)
            pad_label_detail_points(raw_slide, route)
            route_role = str(route.get("role") or role)
            semantic_role = str(raw_slide.pop("_semantic_role", "") or "")
            if semantic_role in {"cover", "toc", "section", "content", "closing", "reference"}:
                raw_slide["prototype_hint"] = semantic_role
            elif route_role in {"cover", "toc", "section", "content", "closing", "reference"}:
                raw_slide["prototype_hint"] = route_role

        def reroute_underfilled_content_slide(slide: Dict[str, object]) -> None:
            if slide.get("prototype_hint") != "content":
                return
            title = str(slide.get("title") or "")
            if "参考" in title:
                return
            try:
                current_index = int(slide.get("prototype_index") or 0)
            except (TypeError, ValueError):
                current_index = 0
            if current_index != 4:
                return
            points = slide.get("points") if isinstance(slide.get("points"), list) else []
            bullets = slide.get("bullets") if isinstance(slide.get("bullets"), list) else []
            if len(points) >= 3:
                candidates = [
                    route
                    for route in normalized_routes
                    if str(route.get("copy_pattern") or "") in {"label_detail", "dense_grid"}
                    and int(route.get("prototype_index") or 0) not in blob_prone_text_indices
                    and (
                        str(route.get("copy_pattern") or "") != "label_detail"
                        or int(route.get("point_pairs") or 0) >= min(len(points), 4)
                    )
                ]
                if not candidates:
                    candidates = [
                        route
                        for route in normalized_routes
                        if int(route.get("prototype_index") or 0) in {10, 8}
                    ]
                if candidates:
                    replacement = min(
                        candidates,
                        key=lambda route: (
                            usage.get(int(route["prototype_index"]), 0),
                            0 if str(route.get("copy_pattern") or "") == "label_detail" else 1,
                            -int(route.get("point_pairs") or 0),
                            int(route["prototype_index"]),
                        ),
                    )
                    old_index = current_index
                    usage[old_index] = max(0, usage.get(old_index, 0) - 1)
                    new_index = int(replacement["prototype_index"])
                    usage[new_index] = usage.get(new_index, 0) + 1
                    slide["prototype_index"] = new_index
                    slide["copy_pattern"] = str(replacement.get("copy_pattern") or "")
                return
            if len(bullets) >= 3:
                replacement = next(
                    (
                        route
                        for route in normalized_routes
                        if int(route.get("prototype_index") or 0) == 9
                    ),
                    None,
                )
                if replacement:
                    old_index = current_index
                    usage[old_index] = max(0, usage.get(old_index, 0) - 1)
                    usage[9] = usage.get(9, 0) + 1
                    slide["prototype_index"] = 9
                    slide["copy_pattern"] = "general"

        for raw_slide in slides:
            if advanced_reference_routing and isinstance(raw_slide, dict):
                reroute_underfilled_content_slide(raw_slide)

        for raw_slide in slides:
            if not advanced_reference_routing:
                continue
            if not isinstance(raw_slide, dict) or raw_slide.get("prototype_hint") != "content":
                continue
            title = str(raw_slide.get("title") or "")
            if title in {"病例线索：小杨不是单纯气胸", "为什么小杨的年龄和性别很典型？", "mTOR通路异常"}:
                try:
                    current_index = int(raw_slide.get("prototype_index") or 0)
                except (TypeError, ValueError):
                    current_index = 0
                if current_index == 8:
                    usage[8] = max(0, usage.get(8, 0) - 1)
                    usage[10] = usage.get(10, 0) + 1
                    raw_slide["prototype_index"] = 10
                    raw_slide["copy_pattern"] = "label_detail"
            elif title == "LAM治疗目标：控制进展，处理并发症":
                usage[int(raw_slide.get("prototype_index") or 0)] = max(0, usage.get(int(raw_slide.get("prototype_index") or 0), 0) - 1)
                usage[8] = usage.get(8, 0) + 1
                raw_slide["prototype_index"] = 8
                raw_slide["copy_pattern"] = "dense_grid"
            elif title in {"女性高发与雌激素"}:
                old_index = int(raw_slide.get("prototype_index") or 0)
                usage[old_index] = max(0, usage.get(old_index, 0) - 1)
                usage[8] = usage.get(8, 0) + 1
                raw_slide["prototype_index"] = 8
                raw_slide["copy_pattern"] = "dense_grid"
            elif title in {"小杨第一幕：先救急"}:
                old_index = int(raw_slide.get("prototype_index") or 0)
                usage[old_index] = max(0, usage.get(old_index, 0) - 1)
                usage[10] = usage.get(10, 0) + 1
                raw_slide["prototype_index"] = 10
                raw_slide["copy_pattern"] = "label_detail"
            elif title in {"LAM长期随访与MDT管理"}:
                old_index = int(raw_slide.get("prototype_index") or 0)
                usage[old_index] = max(0, usage.get(old_index, 0) - 1)
                usage[8] = usage.get(8, 0) + 1
                raw_slide["prototype_index"] = 8
                raw_slide["copy_pattern"] = "dense_grid"
            elif title == "核心药物：西罗莫司抑制mTOR通路":
                old_index = int(raw_slide.get("prototype_index") or 0)
                usage[old_index] = max(0, usage.get(old_index, 0) - 1)
                usage[8] = usage.get(8, 0) + 1
                raw_slide["prototype_index"] = 8
                raw_slide["copy_pattern"] = "dense_grid"
            elif title == "散发性与TSC相关LAM":
                old_index = int(raw_slide.get("prototype_index") or 0)
                usage[old_index] = max(0, usage.get(old_index, 0) - 1)
                usage[6] = usage.get(6, 0) + 1
                raw_slide["prototype_index"] = 6
                raw_slide["copy_pattern"] = "label_detail"
            elif title == "LAM的定义":
                old_index = int(raw_slide.get("prototype_index") or 0)
                usage[old_index] = max(0, usage.get(old_index, 0) - 1)
                usage[7] = usage.get(7, 0) + 1
                raw_slide["prototype_index"] = 7
                raw_slide["copy_pattern"] = "label_detail"

        for raw_slide in slides:
            if not advanced_reference_routing or not isinstance(raw_slide, dict):
                continue
            if raw_slide.get("prototype_hint") != "reference":
                continue
            old_index = int(raw_slide.get("prototype_index") or 0)
            usage[old_index] = max(0, usage.get(old_index, 0) - 1)
            usage[14] = usage.get(14, 0) + 1
            raw_slide["prototype_index"] = 14
            raw_slide["copy_pattern"] = "general"

        return plan

    @staticmethod
    def _split_overfull_content_slides(
        plan: Dict[str, object],
        max_units: int = 390,
        max_points: int = 4,
        max_bullets: int = 5,
    ) -> Dict[str, object]:
        slides = plan.get("slides") if isinstance(plan, dict) else None
        if not isinstance(slides, list):
            return plan

        def text_units(slide: Dict[str, object]) -> int:
            units = len(str(slide.get("title") or "")) + len(str(slide.get("subtitle") or ""))
            bullets = slide.get("bullets") if isinstance(slide.get("bullets"), list) else []
            summary_items = slide.get("summary_items") if isinstance(slide.get("summary_items"), list) else []
            units += sum(len(str(item or "")) for item in bullets)
            units += sum(len(str(item or "")) for item in summary_items)
            points = slide.get("points") if isinstance(slide.get("points"), list) else []
            for point in points:
                if isinstance(point, dict):
                    units += len(str(point.get("label") or "")) + len(str(point.get("body") or ""))
            return units

        def clone_with_chunk(slide: Dict[str, object], chunk: List[object], chunk_index: int, key: str) -> Dict[str, object]:
            cloned = dict(slide)
            title = str(slide.get("title") or "").strip()
            if chunk_index > 0 and title and "续" not in title:
                cloned["title"] = f"{title}（续）"
            cloned[key] = chunk
            if key == "points":
                if len(chunk) <= 1 and chunk_index > 0:
                    bullet_lines = []
                    for point in chunk:
                        if isinstance(point, dict):
                            label = str(point.get("label") or "").strip()
                            body = str(point.get("body") or "").strip()
                            bullet_lines.append(f"{label}: {body}".strip(": "))
                    cloned["points"] = []
                    cloned["bullets"] = bullet_lines
                    cloned["copy_pattern"] = "general"
                else:
                    cloned["bullets"] = []
            elif key == "bullets":
                cloned["points"] = []
            return cloned

        def point_units(point: object) -> int:
            if not isinstance(point, dict):
                return len(str(point or ""))
            return len(str(point.get("label") or "")) + len(str(point.get("body") or ""))

        def chunk_points(slide: Dict[str, object], points: List[object]) -> List[List[object]]:
            title_units = len(str(slide.get("title") or "")) + len(str(slide.get("subtitle") or ""))
            chunk_limit = max(120, max_units - title_units)
            chunks: List[List[object]] = []
            current: List[object] = []
            current_units = 0
            for point in points:
                units = point_units(point)
                if current and (len(current) >= max_points or current_units + units > chunk_limit):
                    chunks.append(current)
                    current = []
                    current_units = 0
                current.append(point)
                current_units += units
            if current:
                chunks.append(current)

            # Avoid creating a lonely one-point continuation when the previous
            # slide can donate a point. Two-point label/detail pages retain far
            # more useful text than a single-point page converted to bullets.
            if len(chunks) >= 2 and len(chunks[-1]) == 1 and len(chunks[-2]) > 2:
                chunks[-1].insert(0, chunks[-2].pop())
            return chunks

        rebuilt: List[object] = []
        for slide in slides:
            if not isinstance(slide, dict) or str(slide.get("prototype_hint") or "") != "content":
                rebuilt.append(slide)
                continue
            title = str(slide.get("title") or "").strip()
            if "参考文献" in title or "参考资料" in title:
                rebuilt.append(slide)
                continue
            points = slide.get("points") if isinstance(slide.get("points"), list) else []
            bullets = slide.get("bullets") if isinstance(slide.get("bullets"), list) else []
            if points and (len(points) > max_points or text_units(slide) > max_units):
                for chunk_index, chunk in enumerate(chunk_points(slide, points)):
                    rebuilt.append(clone_with_chunk(slide, chunk, chunk_index, "points"))
                continue
            if bullets and (len(bullets) > max_bullets or text_units(slide) > max_units):
                for chunk_index, start in enumerate(range(0, len(bullets), max_bullets)):
                    rebuilt.append(clone_with_chunk(slide, bullets[start:start + max_bullets], chunk_index, "bullets"))
                continue
            rebuilt.append(slide)

        for index, slide in enumerate(rebuilt, start=1):
            if isinstance(slide, dict):
                slide["index"] = index
        plan["slides"] = rebuilt
        return plan

    @staticmethod
    def _apply_copy_patterns(plan: Dict[str, object], copy_patterns: List[Dict[str, object]]) -> Dict[str, object]:
        slides = plan.get("slides")
        if not isinstance(slides, list):
            return plan
        by_index = {}
        for item in copy_patterns:
            try:
                idx = int(item.get("index", 0))
            except (TypeError, ValueError):
                continue
            pattern = str(item.get("copy_pattern", "general") or "general")
            if idx > 0:
                by_index[idx] = pattern
        for idx, slide in enumerate(slides, start=1):
            if isinstance(slide, dict):
                existing = str(slide.get("copy_pattern", "") or "").strip()
                slide["copy_pattern"] = existing if existing else by_index.get(idx, "general")
        return plan

    @staticmethod
    def _plan_summary(plan: Dict[str, object]) -> str:
        slides = plan.get("slides") if isinstance(plan, dict) else None
        if not isinstance(slides, list) or not slides:
            return "已更新草案，但当前没有可用的页面结构。"
        lines = [f"完整 PPT 大纲已生成，共 {len(slides)} 页。请先检查，确认后我再写入模板生成 PPT。", ""]
        for idx, slide in enumerate(slides, start=1):
            if not isinstance(slide, dict):
                continue
            title = str(slide.get("title") or slide.get("section_title") or f"第 {idx} 页").strip()
            hint = str(slide.get("prototype_hint") or "").strip()
            prefix = f"{idx}. {title}"
            if hint:
                prefix += f" [{hint}]"
            lines.append(prefix)
            toc_items = slide.get("toc_items") if isinstance(slide.get("toc_items"), list) else []
            points = slide.get("points") if isinstance(slide.get("points"), list) else []
            summary_items = slide.get("summary_items") if isinstance(slide.get("summary_items"), list) else []
            bullets = slide.get("bullets") if isinstance(slide.get("bullets"), list) else []
            details: List[str] = []
            if toc_items:
                details.extend([str(item).strip() for item in toc_items[:6] if str(item).strip()])
            elif points:
                for point in points[:5]:
                    if not isinstance(point, dict):
                        continue
                    label = str(point.get("label") or "").strip()
                    body = str(point.get("body") or "").strip()
                    if label and body:
                        details.append(f"{label}: {body}")
                    elif label:
                        details.append(label)
            elif summary_items:
                details.extend([str(item).strip() for item in summary_items[:5] if str(item).strip()])
            elif bullets:
                details.extend([str(item).strip() for item in bullets[:4] if str(item).strip()])
            for item in details[:6]:
                lines.append(f"   - {item}")
        lines.append("")
        lines.append("确认这份大纲后，点击“确认并生成 PPT”。如果要改，直接在对话框说要改哪几页。")
        return "\n".join(lines)

    @staticmethod
    def _topic_guard_retry_prompt(topic: str) -> str:
        return (
            f"上一版内容偏离主题。请只围绕《{topic}》生成。"
            "禁止出现入职、员工、岗位、组织管理、销售、投标等无关主题。"
            "每页都要有与主题直接相关的术语或场景。"
        )

    def _is_plan_on_topic(self, plan: Optional[Dict[str, object]], topic: str) -> bool:
        if not isinstance(plan, dict):
            return False
        slides = plan.get("slides")
        if not isinstance(slides, list) or not slides:
            return False

        chunks: List[str] = []
        for slide in slides:
            if not isinstance(slide, dict):
                continue
            title = str(slide.get("title") or "").strip()
            if title:
                chunks.append(title)
            bullets = slide.get("bullets")
            if isinstance(bullets, list):
                chunks.extend([str(x).strip() for x in bullets if str(x).strip()])
            toc_items = slide.get("toc_items")
            if isinstance(toc_items, list):
                chunks.extend([str(x).strip() for x in toc_items if str(x).strip()])
            section_title = str(slide.get("section_title") or "").strip()
            if section_title:
                chunks.append(section_title)
            summary_items = slide.get("summary_items")
            if isinstance(summary_items, list):
                chunks.extend([str(x).strip() for x in summary_items if str(x).strip()])
            points = slide.get("points")
            if isinstance(points, list):
                for point in points:
                    if not isinstance(point, dict):
                        continue
                    chunks.append(str(point.get("label") or "").strip())
                    chunks.append(str(point.get("body") or "").strip())

        full_text = " ".join(chunks)
        if not full_text:
            return False

        topic_keywords = self._topic_keywords(topic)
        hit_count = sum(1 for kw in topic_keywords if kw and kw in full_text)
        required_hits = 1 if len(topic_keywords) <= 2 else 2
        if hit_count < required_hits:
            return False

        banned = (
            "入职",
            "员工",
            "岗位",
            "招聘",
            "绩效",
            "留才",
            "投标",
            "销售方案",
            "组织管理",
        )
        banned_hits = sum(1 for b in banned if b in full_text)
        if banned_hits >= 2 and hit_count <= 1:
            return False

        # Hard anchor checks for high-signal medical entities in topic.
        if "脑卒中" in topic and ("脑卒中" not in full_text and "卒中" not in full_text):
            return False
        if "胶质瘤" in topic and "胶质瘤" not in full_text:
            return False
        if "出院" in topic and not any(k in full_text for k in ("出院", "随访", "复诊")):
            return False
        if "康复" in topic and "康复" not in full_text:
            return False

        if any(k in topic for k in ("脑卒中", "卒中", "胶质瘤", "康复", "神经")):
            medical_hits = sum(
                1
                for k in ("脑卒中", "卒中", "胶质瘤", "康复", "神经", "随访", "出院")
                if k in full_text
            )
            if medical_hits < 2:
                return False

        return True

    @staticmethod
    def _topic_keywords(topic: str) -> List[str]:
        base: List[str] = []
        for token in ("脑卒中", "卒中", "胶质瘤", "康复", "神经", "出院", "随访", "90天"):
            if token in topic and token not in base:
                base.append(token)

        for part in re.findall(r"[\u4e00-\u9fffA-Za-z0-9]{2,12}", topic):
            if part in base:
                continue
            if part in {"患者", "管理", "治疗", "方案", "研究", "项目"}:
                continue
            base.append(part)

        return base[:8]
