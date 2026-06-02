from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from typing import Dict, List, Optional


class AIAdapter:
    """OpenAI-compatible planner adapter.

    Returns None if generation cannot be completed.
    """

    def __init__(self, api_key: str, base_url: str, model: str):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model

    def available(self) -> bool:
        return bool(self.api_key)

    def check_connection(self) -> Dict[str, object]:
        if not self.api_key:
            return {"ok": False, "reason": "no_api_key", "message": "未配置 API Key"}
        if not self.base_url or not self.model:
            return {"ok": False, "reason": "incomplete_config", "message": "AI Base URL 或模型名称未配置完整"}

        req = urllib.request.Request(
            url=f"{self.base_url}/models",
            method="GET",
            headers={"Authorization": f"Bearer {self.api_key}"},
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                status = int(getattr(resp, "status", 200) or 200)
        except urllib.error.HTTPError as exc:
            return {
                "ok": False,
                "reason": f"http_{exc.code}",
                "message": f"AI 连接测试失败：HTTP {exc.code}",
            }
        except (urllib.error.URLError, TimeoutError) as exc:
            return {
                "ok": False,
                "reason": "network_error",
                "message": f"AI 连接测试失败：{exc}",
            }

        return {
            "ok": 200 <= status < 300,
            "reason": "ok" if 200 <= status < 300 else f"http_{status}",
            "message": "AI 连接测试通过" if 200 <= status < 300 else f"AI 连接测试失败：HTTP {status}",
        }

    def generate_plan(
        self,
        topic: str,
        slide_count: int,
        template_spec: Dict[str, object],
        audience: str = "",
        tone: str = "",
        conversation: Optional[List[Dict[str, str]]] = None,
        copy_patterns: Optional[List[Dict[str, object]]] = None,
    ) -> Optional[Dict[str, object]]:
        if not self.available():
            return None

        layout_summary = self._layout_summary(template_spec)
        template_contract = self._template_contract_summary(template_spec)
        topic_keywords = self._topic_keywords(topic)
        hard_anchor_terms = self._hard_anchor_terms(topic)

        prompt = {
            "task": "Generate a slide plan for template-driven presentation editing.",
            "constraints": {
                "slide_count": slide_count,
                "each_slide_bullets": "4-6",
                "title_max_chars": 24,
                "bullet_max_chars": 88,
                "point_body_target_chars": "55-90 Chinese chars for main body slots",
                "must_be_chinese": True,
            },
            "topic": topic,
            "topic_keywords": topic_keywords,
            "hard_anchor_terms": hard_anchor_terms,
            "forbidden_unrelated_terms": ["入职", "员工", "岗位", "招聘", "销售", "投标", "组织管理"],
            "audience": audience or "通用受众",
            "tone": tone or "专业清晰",
            "conversation": conversation or [],
            "template_layouts": layout_summary,
            "template_contract": template_contract,
            "copy_patterns": copy_patterns or [],
            "output_schema": {
                "deck_title": "string",
                "slides": [
                    {
                        "index": "int (1..slide_count)",
                        "title": "short string, not a sentence",
                        "subtitle": "optional cover subtitle",
                        "toc_items": ["short chapter title, only for TOC slides"],
                        "section_title": "short chapter title, only for transition slides",
                        "points": [
                            {"label": "2-8 Chinese chars", "body": "complete concrete body text"}
                        ],
                        "summary_items": ["short summary point, only for closing slides"],
                        "bullets": ["fallback strings only when structured fields do not fit"],
                        "prototype_hint": "cover|toc|section|content|closing",
                        "copy_pattern": "cover_toc|label_detail|process|dense_grid|general",
                    }
                ],
            },
            "rules": [
                "Output JSON only, no markdown.",
                "先生成一份可直接填入模板文本框的 PPT 终极大纲完全体，再考虑版式；不要只给短标题或短知识点。",
                "First create a complete outline that can be filled into template slots; do not rely on vague bullets.",
                "Ensure slide indices are continuous from 1.",
                "The first slide must be a cover and should fill the deck_title slot.",
                "The second slide should be a table of contents with only major section titles.",
                "A PPT is organized by TOC sections: every toc_items entry must have one matching section transition slide.",
                "After the TOC, structure the deck as repeated groups: section transition slide, then one or more content slides for that section.",
                "Use section transition slides to introduce major parts; section_title must equal the corresponding TOC item.",
                "After each section transition, select content slides that fit the number of knowledge points.",
                "Prefer varied content layouts; do not repeat the same content pattern on every page unless the outline demands it.",
                "For medical, teaching, or PBL topics, organize the story around 病例线索, evidence chain, diagnosis reasoning, mechanism explanation, treatment decisions, follow-up, and patient education.",
                "禁止使用 疾病概述/病因机制/临床诊断/治疗随访 这种四段百科目录作为最终目录；rewrite it into case-driven chapter titles when the topic supports a clinical story.",
                "Do not make the outline look like four identical encyclopedia chapters; mix case clues, mechanism explanation, diagnosis reasoning, treatment decisions, follow-up, and patient education when the topic supports it.",
                "Use closing as the last slide when the template contract contains a closing route.",
                "Deck title should stay aligned with the topic.",
                "Keep TOC item titles short, respecting template_contract.content_rules.toc_title_max_chars.",
                "Titles must be short labels, not long explanatory sentences.",
                "Use toc_items for TOC pages, points[{label, body}] for content pages, and summary_items for closing pages.",
                "For content slides, include at least one hard anchor term in title or bullets.",
                "Keep titles and mini-headings concise; avoid long chained phrases.",
                "Each content bullet should prefer the format: short heading + colon + concrete detail.",
                "Heading should be concise (about 4-12 Chinese chars), detail should be specific and informative.",
                "Allow detail to wrap naturally in body text boxes; avoid over-short generic fragments.",
                "Each slide should contain concrete, non-generic bullets.",
                "Do not write visible ellipses such as ... or ……; produce complete text that fits the slot.",
                "Do not repeat filler phrases such as 明确执行动作与责任分工 or 设置复评时间点与量化指标.",
                "Every slide must stay in the given topic domain.",
                "Do not introduce unrelated business/HR topics.",
                "Use copy_patterns by slide index when present.",
                "For label_detail slides, write short labels with concrete detail.",
                "For points[].body, write a teachable sentence of about 55-90 Chinese characters: include meaning, evidence/action, and clinical or business consequence.",
                "Avoid 1-sentence fragments shorter than 40 Chinese characters in main body fields.",
                "For process slides, make bullets stage/action/result oriented.",
                "For dense_grid slides, keep entries compact and parallel.",
                "Never plan body text that requires shrinking below template_contract.content_rules.min_body_font_size_pt.",
            ],
        }

        body = {
            "model": self.model,
            "temperature": 0.2,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a strict JSON planner for PPT content. "
                        "Before rendering, produce a complete outline that can be directly filled into template text slots. "
                        "Prefer authored, case-driven narrative over generic encyclopedia chaptering. "
                        "You must follow user conversation adjustments and keep output concise."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(prompt, ensure_ascii=False),
                },
            ],
        }

        content = self._chat_json(body)
        if not content:
            return None

        parsed = self._extract_json(content)
        if not parsed:
            return None

        return self._normalize_plan(parsed, slide_count, topic, copy_patterns=copy_patterns)

    def polish_plan(
        self,
        topic: str,
        draft_plan: Dict[str, object],
        template_spec: Dict[str, object],
        conversation: Optional[List[Dict[str, str]]] = None,
        copy_patterns: Optional[List[Dict[str, object]]] = None,
    ) -> Optional[Dict[str, object]]:
        if not self.available():
            return None
        slides = draft_plan.get("slides")
        if not isinstance(slides, list) or len(slides) < 3:
            return None

        layout_summary = self._layout_summary(template_spec)
        template_contract = self._template_contract_summary(template_spec)
        hard_anchor_terms = self._hard_anchor_terms(topic)
        slide_count = len(slides)

        prompt = {
            "task": "Polish an existing slide plan for template-based PPT rendering.",
            "topic": topic,
            "hard_anchor_terms": hard_anchor_terms,
            "constraints": {
                "slide_count": slide_count,
                "keep_index_and_order": True,
                "keep_prototype_hint": True,
                "title_max_chars": 24,
                "bullet_max_chars": 88,
                "point_body_target_chars": "55-90 Chinese chars for main body slots",
                "must_be_chinese": True,
            },
            "style_rules": [
                "Do not change slide count, slide order, or slide indices.",
                "Keep first slide as cover and second slide as table of contents.",
                "For content slides, each bullet should follow 'short heading + colon + concrete detail'.",
                "Heading length around 4-12 Chinese chars.",
                "Detail should include action/object/condition or indicator, avoid generic short fragments.",
                "Keep details rich enough for body text boxes; allow wrapping naturally.",
                "Use copy_patterns by slide index when present.",
                "Keep TOC items short and preserve one section transition slide for every TOC item.",
                "Do not collapse all sections into a single transition slide.",
                "Respect template_contract slot bindings and font-size limits.",
                "For label_detail slides, write short labels with concrete detail.",
                "For points[].body, write a teachable sentence of about 55-90 Chinese characters with meaning, evidence/action, and consequence.",
                "Avoid body fragments shorter than 40 Chinese characters unless the slide is a cover, TOC, or transition.",
                "For process slides, make bullets stage/action/result oriented.",
                "For dense_grid slides, keep entries compact and parallel.",
            ],
            "template_layouts": layout_summary,
            "template_contract": template_contract,
            "copy_patterns": copy_patterns or [],
            "conversation": conversation or [],
            "draft_plan": draft_plan,
            "output_schema": {
                "deck_title": "string",
                "slides": [
                    {
                        "index": "int (same as input)",
                        "title": "short string",
                        "subtitle": "optional cover subtitle",
                        "toc_items": ["short chapter title"],
                        "section_title": "short chapter title",
                        "points": [{"label": "short", "body": "complete concrete body text"}],
                        "summary_items": ["short summary point"],
                        "bullets": ["fallback strings"],
                        "prototype_hint": "cover|toc|section|content|closing (same as input)",
                        "copy_pattern": "same as copy_patterns when present",
                    }
                ],
            },
        }

        body = {
            "model": self.model,
            "temperature": 0.15,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a strict JSON plan polisher for PPT text. "
                        "Keep structure stable and improve only wording quality."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(prompt, ensure_ascii=False),
                },
            ],
        }

        content = self._chat_json(body)
        if not content:
            return None
        parsed = self._extract_json(content)
        if not parsed:
            return None

        polished = self._normalize_plan(parsed, slide_count, topic, copy_patterns=copy_patterns)
        if isinstance(polished, dict):
            polished["source"] = "ai_polished"
        return polished

    def standardize_template(self, template_spec: Dict[str, object]) -> Optional[Dict[str, object]]:
        if not self.available():
            return None

        prompt = {
            "task": "Standardize a PowerPoint template for an automated PPT generation agent.",
            "agent": "template_standardization_agent",
            "goal": (
                "Read extracted PPTX template metadata and text-slot typography. Classify each prototype slide "
                "as cover, table of contents, section transition, content, process, dense grid, label-detail, "
                "or closing. Bind important text slots such as deck title, presenter, date, toc items, section "
                "title, page title, point labels, and body content so the generation step can preserve template "
                "fonts, sizes, alignment, and layout intent."
            ),
            "template": {
                "slide_count": template_spec.get("slide_count", 0),
                "layout_count": template_spec.get("layout_count", 0),
                "master_count": template_spec.get("master_count", 0),
                "layouts": template_spec.get("layouts", [])[:20],
                "prototypes": template_spec.get("prototypes", [])[:30],
                "stats": template_spec.get("stats", {}),
            },
            "role_definitions": {
                "cover": "title page or opening page",
                "toc": "table of contents, agenda, overview",
                "section": "chapter divider or transition page",
                "content": "normal title plus body content page",
                "process": "timeline, steps, workflow, arrows, stages",
                "dense_grid": "many parallel blocks/cards/metrics",
                "label_detail": "short label plus explanatory detail blocks",
                "closing": "ending, thank you, Q&A, contact page",
            },
            "copy_patterns": ["cover_toc", "label_detail", "process", "dense_grid", "general"],
            "output_schema": {
                "summary": "string",
                "deck_flow": ["cover", "toc", "section", "content", "section", "content", "closing"],
                "layout_roles": [{"layout": "string", "role": "cover|toc|section|content|process|dense_grid|label_detail", "confidence": "number"}],
                "slide_routes": [{"prototype_index": "int", "role": "string", "copy_pattern": "string"}],
                "slot_bindings": [
                    {
                        "prototype_index": "int",
                        "slot_id": "string from prototype.text_slots",
                        "semantic": "deck_title|presenter|date|toc_item|section_title|page_title|point_label|point_body|body|closing_message|ignore",
                        "min_font_size_pt": "number"
                    }
                ],
                "content_rules": {
                    "min_body_font_size_pt": 16,
                    "toc_title_max_chars": 14,
                    "prefer_varied_content_layouts": True,
                    "allow_layout_adaptation": True
                },
                "normalization_notes": ["string"],
            },
            "rules": [
                "Output JSON only, no markdown.",
                "Prefer practical generation routing over visual description.",
                "Preserve all text slots; mark decorative or unsafe slots as ignore rather than deleting them.",
                "Use original font size and font face from text_slots as the default style contract.",
                "Deck flow should follow: cover, toc, then repeating section transition + content pages for every TOC item, then closing when available.",
                "Cover title should use the largest title slot; presenter and date should use smaller meta slots.",
                "TOC should contain only major section titles and keep each item short.",
                "Section transition pages should contain one major section title and should be marked role section.",
                "Content pages should be chosen by how many knowledge points they need to hold; prefer varied content layouts.",
                "If no exact content layout exists, allow adapting a similar content slide while preserving the template style.",
                "Body text may shrink for complex topics, but min_body_font_size_pt must be at least 16.",
                "Never invent slide indices that are not present in prototypes.",
                "When uncertain, choose content/general with low confidence.",
                "Use concise Chinese strings for summary and notes.",
            ],
        }

        body = {
            "model": self.model,
            "temperature": 0.1,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a PowerPoint template standardization agent. "
                        "Return strict JSON metadata that a PPT generation pipeline can use."
                    ),
                },
                {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
            ],
        }

        content = self._chat_json(body)
        if not content:
            return None
        parsed = self._extract_json(content)
        if not parsed:
            return None
        return self._normalize_template_standardization(parsed, template_spec)

    @staticmethod
    def _layout_summary(template_spec: Dict[str, object]) -> List[Dict[str, object]]:
        summary: List[Dict[str, object]] = []
        for layout in template_spec.get("layouts", [])[:8]:
            summary.append(
                {
                    "name": layout.get("name", ""),
                    "type": layout.get("layout_type", ""),
                    "ph": layout.get("placeholder_count", 0),
                }
            )
        return summary

    @staticmethod
    def _template_contract_summary(template_spec: Dict[str, object]) -> Dict[str, object]:
        ai = template_spec.get("ai_standardization", {})
        if not isinstance(ai, dict):
            ai = {}
        rules = ai.get("content_rules", {}) if isinstance(ai.get("content_rules"), dict) else {}
        prototypes = []
        for prototype in template_spec.get("prototypes", [])[:20]:
            if not isinstance(prototype, dict):
                continue
            slots = []
            text_slots = prototype.get("text_slots", []) if isinstance(prototype.get("text_slots"), list) else []
            for slot in text_slots[:12]:
                if not isinstance(slot, dict):
                    continue
                slots.append(
                    {
                        "slot_id": slot.get("slot_id", ""),
                        "role_hint": slot.get("role_hint", ""),
                        "font_size_pt": slot.get("font_size_pt"),
                        "font_face": slot.get("font_face", ""),
                        "placeholder_type": slot.get("placeholder_type", ""),
                        "text": AIAdapter._compact_line(str(slot.get("text") or ""), max_chars=40, prefer_prefix=False),
                    }
                )
            prototypes.append(
                {
                    "index": prototype.get("index"),
                    "layout_path": prototype.get("layout_path", ""),
                    "text_slots": slots,
                }
            )

        try:
            min_body = int(rules.get("min_body_font_size_pt", 16) or 16)
        except (TypeError, ValueError):
            min_body = 16
        try:
            toc_max = int(rules.get("toc_title_max_chars", 14) or 14)
        except (TypeError, ValueError):
            toc_max = 14

        return {
            "deck_flow": ai.get("deck_flow", ["cover", "toc", "section", "content", "closing"]),
            "slide_routes": ai.get("slide_routes", []),
            "slot_bindings": ai.get("slot_bindings", []),
            "content_rules": {
                "min_body_font_size_pt": max(16, min_body),
                "toc_title_max_chars": max(8, min(24, toc_max)),
                "prefer_varied_content_layouts": bool(rules.get("prefer_varied_content_layouts", True)),
                "allow_layout_adaptation": bool(rules.get("allow_layout_adaptation", True)),
            },
            "prototypes": prototypes,
        }

    @staticmethod
    def _normalize_template_standardization(
        raw: Dict[str, object],
        template_spec: Dict[str, object],
    ) -> Dict[str, object]:
        layouts_raw = template_spec.get("layouts", [])
        prototypes_raw = template_spec.get("prototypes", [])
        known_layouts = {
            str(item.get("name") or item.get("path") or "").strip()
            for item in layouts_raw
            if isinstance(item, dict)
        }
        known_indices = {
            int(item.get("index"))
            for item in prototypes_raw
            if isinstance(item, dict) and str(item.get("index") or "").isdigit()
        }
        known_slot_keys = set()
        for item in prototypes_raw:
            if not isinstance(item, dict):
                continue
            try:
                proto_index = int(item.get("index", 0))
            except (TypeError, ValueError):
                continue
            for slot in item.get("text_slots", []) if isinstance(item.get("text_slots"), list) else []:
                if isinstance(slot, dict) and str(slot.get("slot_id") or "").strip():
                    known_slot_keys.add((proto_index, str(slot.get("slot_id")).strip()))

        allowed_roles = {"cover", "toc", "section", "content", "process", "dense_grid", "label_detail", "closing"}
        allowed_patterns = {"cover_toc", "label_detail", "process", "dense_grid", "general"}
        allowed_flow = ["cover", "toc", "section", "content", "process", "dense_grid", "label_detail", "closing"]
        allowed_semantics = {
            "deck_title",
            "presenter",
            "date",
            "toc_item",
            "section_title",
            "page_title",
            "point_label",
            "point_body",
            "body",
            "closing_message",
            "ignore",
        }

        layout_roles = []
        raw_layout_roles = raw.get("layout_roles", []) if isinstance(raw.get("layout_roles"), list) else []
        for item in raw_layout_roles:
            if not isinstance(item, dict):
                continue
            layout = str(item.get("layout") or "").strip()
            role = str(item.get("role") or "content").strip()
            if role not in allowed_roles:
                role = "content"
            try:
                confidence = max(0.0, min(1.0, float(item.get("confidence", 0.5))))
            except (TypeError, ValueError):
                confidence = 0.5
            if layout and (not known_layouts or layout in known_layouts):
                layout_roles.append({"layout": layout, "role": role, "confidence": confidence})

        slide_routes = []
        raw_slide_routes = raw.get("slide_routes", []) if isinstance(raw.get("slide_routes"), list) else []
        for item in raw_slide_routes:
            if not isinstance(item, dict):
                continue
            try:
                prototype_index = int(item.get("prototype_index", 0))
            except (TypeError, ValueError):
                continue
            if known_indices and prototype_index not in known_indices:
                continue
            role = str(item.get("role") or "content").strip()
            pattern = str(item.get("copy_pattern") or "general").strip()
            if role not in allowed_roles:
                role = "content"
            if pattern not in allowed_patterns:
                pattern = "general"
            slide_routes.append({"prototype_index": prototype_index, "role": role, "copy_pattern": pattern})

        deck_flow = []
        raw_deck_flow = raw.get("deck_flow", []) if isinstance(raw.get("deck_flow"), list) else []
        for item in raw_deck_flow:
            role = str(item or "").strip()
            if role in allowed_flow:
                deck_flow.append(role)
        if not deck_flow:
            deck_flow = ["cover", "toc", "section", "content", "closing"]

        slot_bindings = []
        raw_slot_bindings = raw.get("slot_bindings", []) if isinstance(raw.get("slot_bindings"), list) else []
        for item in raw_slot_bindings:
            if not isinstance(item, dict):
                continue
            try:
                prototype_index = int(item.get("prototype_index", 0))
            except (TypeError, ValueError):
                continue
            slot_id = str(item.get("slot_id") or "").strip()
            if not slot_id:
                continue
            if known_slot_keys and (prototype_index, slot_id) not in known_slot_keys:
                continue
            semantic = str(item.get("semantic") or "body").strip()
            if semantic not in allowed_semantics:
                semantic = "body"
            try:
                min_size = float(item.get("min_font_size_pt", 16))
            except (TypeError, ValueError):
                min_size = 16.0
            min_size = max(16.0, min(44.0, min_size))
            slot_bindings.append(
                {
                    "prototype_index": prototype_index,
                    "slot_id": slot_id,
                    "semantic": semantic,
                    "min_font_size_pt": int(min_size) if min_size.is_integer() else min_size,
                }
            )

        raw_rules = raw.get("content_rules", {}) if isinstance(raw.get("content_rules"), dict) else {}
        try:
            min_body = float(raw_rules.get("min_body_font_size_pt", 16))
        except (TypeError, ValueError):
            min_body = 16.0
        min_body = max(16.0, min(24.0, min_body))
        try:
            toc_max = int(raw_rules.get("toc_title_max_chars", 14))
        except (TypeError, ValueError):
            toc_max = 14
        content_rules = {
            "min_body_font_size_pt": int(min_body) if min_body.is_integer() else min_body,
            "toc_title_max_chars": max(8, min(24, toc_max)),
            "prefer_varied_content_layouts": bool(raw_rules.get("prefer_varied_content_layouts", True)),
            "allow_layout_adaptation": bool(raw_rules.get("allow_layout_adaptation", True)),
        }

        notes = [
            AIAdapter._compact_line(str(note), max_chars=80, prefer_prefix=False)
            for note in raw.get("normalization_notes", [])
            if str(note).strip()
        ] if isinstance(raw.get("normalization_notes"), list) else []

        return {
            "agent": "template_standardization_agent",
            "ai_used": True,
            "summary": AIAdapter._compact_line(str(raw.get("summary") or "已完成 AI 模板标准化分析"), max_chars=120, prefer_prefix=False),
            "deck_flow": deck_flow[:20],
            "layout_roles": layout_roles[:20],
            "slide_routes": slide_routes[:30],
            "slot_bindings": slot_bindings[:80],
            "content_rules": content_rules,
            "normalization_notes": notes[:10],
        }

    def _chat_json(self, body: Dict[str, object]) -> Optional[str]:
        url = f"{self.base_url}/chat/completions"
        req = urllib.request.Request(
            url=url,
            method="POST",
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
        )

        try:
            with urllib.request.urlopen(req, timeout=90) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError):
            return None

        try:
            return str(payload["choices"][0]["message"]["content"])
        except (KeyError, IndexError, TypeError):
            return None

    def _extract_json(self, content: str) -> Optional[Dict[str, object]]:
        content = content.strip()
        if content.startswith("{") and content.endswith("}"):
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                return None

        match = re.search(r"\{[\s\S]*\}", content)
        if not match:
            return None

        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None

    def _normalize_plan(
        self,
        raw: Dict[str, object],
        requested_count: int,
        topic: str,
        copy_patterns: Optional[List[Dict[str, object]]] = None,
    ) -> Optional[Dict[str, object]]:
        slides = raw.get("slides")
        if not isinstance(slides, list) or not slides:
            return None

        safe_count = max(3, min(requested_count, len(slides)))
        hard_anchor_terms = self._hard_anchor_terms(topic)
        normalized_slides = []
        pattern_by_index = self._copy_pattern_by_index(copy_patterns)

        for idx, slide in enumerate(slides[:safe_count], start=1):
            if not isinstance(slide, dict):
                continue

            title = self._compact_line(str(slide.get("title", "")).strip() or f"第{idx}页", max_chars=24)
            subtitle = self._compact_line(str(slide.get("subtitle", "")).strip(), max_chars=36, prefer_prefix=False)
            toc_items = self._normalize_string_list(slide.get("toc_items"), max_chars=14, max_count=8)
            summary_items = self._normalize_string_list(slide.get("summary_items"), max_chars=28, max_count=8)
            points = self._normalize_points(slide.get("points"), max_count=8)
            bullets_raw = slide.get("bullets", [])
            bullets = []
            if isinstance(bullets_raw, list):
                bullets = [
                    self._compact_line(str(x).strip(), max_chars=88, prefer_prefix=False)
                    for x in bullets_raw
                    if str(x).strip()
                ]
            hint = str(slide.get("prototype_hint", "content")).strip() or "content"
            if idx == 1:
                hint = "cover"
            elif idx == 2:
                hint = "toc"
            anchor = hard_anchor_terms[0] if hard_anchor_terms else ""
            pattern = pattern_by_index.get(idx) or str(slide.get("copy_pattern", "") or "").strip() or hint
            has_structured_content = bool(toc_items or points or summary_items)
            if has_structured_content:
                bullets = []
            elif not bullets:
                bullets = [f"{topic} 关键点{idx}"]
            if bullets and hint not in {"cover", "toc"}:
                bullets = self._ensure_bullet_density(bullets, min_count=4, max_count=6)
                bullets = self._polish_slide_bullets_for_pattern(
                    bullets=bullets,
                    pattern=pattern,
                    anchor=anchor,
                )
                bullets = [self._compact_line(b, max_chars=88, prefer_prefix=False) for b in bullets]
            elif bullets:
                bullets = [self._compact_line(b, max_chars=36, prefer_prefix=False) for b in bullets]
            safe_pattern = pattern if pattern in {"cover_toc", "label_detail", "process", "dense_grid", "general"} else "general"

            normalized_slides.append(
                {
                    "index": idx,
                    "title": title,
                    "subtitle": subtitle,
                    "toc_items": toc_items,
                    "section_title": self._compact_line(
                        str(slide.get("section_title") or title).strip(),
                        max_chars=16,
                        prefer_prefix=False,
                    ),
                    "points": points,
                    "summary_items": summary_items,
                    "bullets": bullets[:6],
                    "prototype_hint": hint,
                    "copy_pattern": safe_pattern,
                }
            )

        if len(normalized_slides) < 3:
            return None

        normalized_slides = self._enforce_section_transitions(normalized_slides)
        normalized_slides = self._enforce_topic_anchor(normalized_slides, topic, hard_anchor_terms)
        deck_title_raw = str(raw.get("deck_title") or topic).strip()
        deck_title = self._compact_line(deck_title_raw, max_chars=24, prefer_prefix=False)
        if hard_anchor_terms and not any(term in deck_title for term in hard_anchor_terms):
            deck_title = self._compact_line(topic, max_chars=24, prefer_prefix=False)

        return {
            "deck_title": deck_title or topic,
            "slides": normalized_slides,
            "source": "ai",
        }

    @staticmethod
    def _enforce_section_transitions(slides: List[Dict[str, object]]) -> List[Dict[str, object]]:
        if len(slides) < 4:
            return slides
        toc_slide = slides[1]
        toc_items = toc_slide.get("toc_items") if isinstance(toc_slide.get("toc_items"), list) else []
        sections = [str(item).strip() for item in toc_items if str(item).strip()]
        if not sections:
            return slides

        tail_slides: List[Dict[str, object]] = []
        body_slides: List[Dict[str, object]] = []
        for slide in slides[2:]:
            hint = str(slide.get("prototype_hint") or "").strip().lower()
            if hint in {"closing", "end", "reference"}:
                if hint == "end":
                    slide["prototype_hint"] = "closing"
                tail_slides.append(slide)
            else:
                body_slides.append(slide)

        existing_sections: Dict[str, Dict[str, object]] = {}
        orphan_sections: List[Dict[str, object]] = []
        content_by_section: Dict[str, List[Dict[str, object]]] = {section: [] for section in sections}
        unassigned_content: List[Dict[str, object]] = []

        for slide in body_slides:
            hint = str(slide.get("prototype_hint") or "").strip().lower()
            title = str(slide.get("section_title") or slide.get("title") or "").strip()
            display_title = str(slide.get("title") or "").strip()
            if hint == "section":
                if title in content_by_section and title not in existing_sections:
                    existing_sections[title] = slide
                else:
                    orphan_sections.append(slide)
                continue
            if (
                title
                and title not in content_by_section
                and any(token in f"{title}{display_title}" for token in ("总结", "参考", "文献", "结束"))
            ):
                if any(token in f"{title}{display_title}" for token in ("参考", "文献")):
                    slide["prototype_hint"] = "reference"
                elif str(slide.get("prototype_hint") or "").strip().lower() not in {"closing", "end"}:
                    slide["prototype_hint"] = "closing"
                tail_slides.append(slide)
                continue
            if title in content_by_section:
                content_by_section[title].append(slide)
            else:
                unassigned_content.append(slide)

        for offset, slide in enumerate(unassigned_content):
            section_title = sections[offset % len(sections)]
            slide["section_title"] = section_title
            content_by_section[section_title].append(slide)

        rebuilt: List[Dict[str, object]] = slides[:2]
        for section_title in sections:
            section_slide = existing_sections.get(section_title)
            if section_slide is None and orphan_sections:
                section_slide = orphan_sections.pop(0)
            if section_slide is None:
                section_slide = {
                    "title": section_title,
                    "section_title": section_title,
                    "toc_items": [],
                    "points": [],
                    "summary_items": [],
                    "bullets": [],
                    "prototype_hint": "section",
                    "copy_pattern": "general",
                }
            section_slide["title"] = section_title
            section_slide["section_title"] = section_title
            section_slide["prototype_hint"] = "section"
            section_slide["copy_pattern"] = "general"
            section_slide["points"] = []
            section_slide["summary_items"] = []
            section_slide["bullets"] = []
            rebuilt.append(section_slide)
            for content_slide in content_by_section.get(section_title, []):
                content_slide["prototype_hint"] = "content"
                content_slide["section_title"] = section_title
                rebuilt.append(content_slide)

        rebuilt.extend(orphan_sections)
        rebuilt.extend(tail_slides)
        for index, slide in enumerate(rebuilt, start=1):
            slide["index"] = index
        slides[:] = rebuilt
        return slides

    @classmethod
    def _normalize_points(cls, raw: object, max_count: int) -> List[Dict[str, str]]:
        if not isinstance(raw, list):
            return []
        out: List[Dict[str, str]] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            label = cls._compact_heading(str(item.get("label") or "").strip())
            body = cls._compact_line(str(item.get("body") or "").strip(), max_chars=118, prefer_prefix=False)
            body = cls._strip_visible_ellipsis(body)
            body = cls._expand_point_body_text(label, body)
            if not label or not body:
                continue
            out.append({"label": label, "body": body})
            if len(out) >= max_count:
                break
        return out

    @staticmethod
    def _expand_point_body_text(label: str, body: str) -> str:
        body = str(body or "").strip()
        if len(body) >= 40:
            return body
        label = str(label or "").strip()
        if not body:
            body = "补充核心判断"
        additions = [
            f"围绕{label or '该要点'}明确评估依据、执行动作和复评指标。",
            "说明适用条件、风险信号和下一步处理边界。",
        ]
        for addition in additions:
            if addition not in body:
                body = f"{body}{addition}"
            if len(body) >= 46:
                break
        return body[:118]

    @classmethod
    def _normalize_string_list(cls, raw: object, max_chars: int, max_count: int) -> List[str]:
        if not isinstance(raw, list):
            return []
        out: List[str] = []
        for item in raw:
            text = cls._compact_line(str(item or "").strip(), max_chars=max_chars, prefer_prefix=False)
            text = cls._strip_visible_ellipsis(text)
            if text:
                out.append(text)
            if len(out) >= max_count:
                break
        return out

    @staticmethod
    def _copy_pattern_by_index(copy_patterns: Optional[List[Dict[str, object]]]) -> Dict[int, str]:
        out: Dict[int, str] = {}
        for item in copy_patterns or []:
            try:
                idx = int(item.get("index", 0))
            except (TypeError, ValueError):
                continue
            pattern = str(item.get("copy_pattern", "")).strip()
            if idx > 0 and pattern:
                out[idx] = pattern
        return out

    @staticmethod
    def _split_heading_detail(text: str) -> tuple[str, str]:
        clean = re.sub(r"\s+", " ", text or "").strip()
        if not clean:
            return "", ""
        for sep in ("：", ":", "—", "-", "｜", "|"):
            if sep not in clean:
                continue
            head, tail = clean.split(sep, 1)
            head = head.strip()
            tail = tail.strip()
            if head and tail:
                return head, tail
        return "", clean

    @staticmethod
    def _compact_heading(text: str) -> str:
        clean = re.sub(r"\s+", " ", text or "").strip()
        if not clean:
            return ""
        clean = re.sub(r"[，。；;、]+$", "", clean).strip()
        if len(clean) <= 12:
            return clean
        for sep in ("，", ",", " ", "、", "：", ":", "（", "("):
            if sep not in clean:
                continue
            head = clean.split(sep, 1)[0].strip()
            if 4 <= len(head) <= 12:
                return head
        return clean[:12].strip()

    @staticmethod
    def _expand_detail_text(detail: str, anchor: str = "") -> str:
        clean = re.sub(r"\s+", " ", detail or "").strip()
        clean = re.sub(r"[，。；;]+$", "", clean).strip()
        if not clean:
            clean = "补充评估依据、训练频次和复评节奏"
        elif len(clean) < 8:
            clean = f"{clean}，补充适用条件和安全边界"
        elif len(clean) < 14:
            clean = f"{clean}，记录训练频次和复评依据"
        elif len(clean) < 18:
            clean = f"{clean}，按阶段监测效果并动态调整"

        if anchor and anchor not in clean and len(clean) < 22:
            clean = f"围绕{anchor}{clean}"
        return clean

    @classmethod
    def _polish_bullet_for_layout(cls, text: str, anchor: str = "") -> str:
        clean = re.sub(r"\s+", " ", text or "").strip()
        if not clean:
            return ""
        heading, detail = cls._split_heading_detail(clean)
        heading = cls._compact_heading(heading or clean)
        detail = cls._expand_detail_text(detail if heading else clean, anchor=anchor)
        if not heading:
            heading = cls._compact_heading(detail)
        if not heading:
            return detail
        return f"{heading}：{detail}"

    @classmethod
    def _polish_slide_bullets(cls, bullets: List[str], hint: str, anchor: str = "") -> List[str]:
        polished: List[str] = []
        hint_key = (hint or "").strip().lower()
        min_detail = 18
        if hint_key == "cover":
            min_detail = 12
        elif hint_key == "toc":
            min_detail = 10
        elif hint_key == "content":
            min_detail = 20

        for bullet in bullets:
            row = cls._polish_bullet_for_layout(bullet, anchor=anchor)
            head, detail = cls._split_heading_detail(row)
            if head and len(detail) < min_detail:
                guard = 0
                while len(detail) < min_detail and guard < 6:
                    before = detail
                    detail = cls._expand_detail_text(detail, anchor=anchor)
                    if detail == before:
                        detail = f"{detail}，并细化执行条件与评估标准"
                    guard += 1
                row = f"{cls._compact_heading(head)}：{detail}"
            polished.append(row)
        return polished

    @classmethod
    def _polish_slide_bullets_for_pattern(
        cls,
        bullets: List[str],
        pattern: str = "general",
        anchor: str = "",
    ) -> List[str]:
        pattern_key = (pattern or "general").strip().lower()
        if pattern_key in {"cover_toc", "toc", "cover"}:
            return [cls._compact_line(b, max_chars=32, prefer_prefix=False) for b in bullets if b.strip()]

        if pattern_key == "dense_grid":
            out = []
            for bullet in bullets:
                row = cls._polish_bullet_for_layout(bullet, anchor=anchor)
                out.append(cls._compact_line(row, max_chars=42, prefer_prefix=False))
            return out

        if pattern_key == "process":
            out = []
            for bullet in bullets:
                row = cls._polish_bullet_for_layout(bullet, anchor=anchor)
                head, detail = cls._split_heading_detail(row)
                if head and len(detail) < 16:
                    detail = cls._expand_detail_text(detail, anchor=anchor)
                out.append(f"{cls._compact_heading(head)}：{detail}" if head else detail)
            return out

        if pattern_key == "label_detail":
            return cls._polish_slide_bullets(bullets, hint="content", anchor=anchor)

        return cls._polish_slide_bullets(bullets, hint="content", anchor=anchor)

    @staticmethod
    def _compact_line(text: str, max_chars: int, prefer_prefix: bool = True) -> str:
        clean = re.sub(r"\s+", " ", text or "").strip()
        if not clean:
            return ""
        clean = AIAdapter._strip_visible_ellipsis(clean)
        if len(clean) <= max_chars:
            return clean
        if prefer_prefix:
            for sep in ("：", ":", "，", ",", "；", ";", "。", "/", "|"):
                if sep not in clean:
                    continue
                lead = clean.split(sep, 1)[0].strip()
                if 4 <= len(lead) <= max_chars:
                    return lead
        return clean[:max(1, max_chars)].rstrip(" ，,；;。:")

    @staticmethod
    def _strip_visible_ellipsis(text: str) -> str:
        clean = re.sub(r"\.{3,}|…+", "", text or "")
        return re.sub(r"\s+", " ", clean).strip()

    @staticmethod
    def _ensure_bullet_density(bullets: List[str], min_count: int, max_count: int) -> List[str]:
        cleaned = [b.strip() for b in bullets if b and b.strip()]
        if not cleaned:
            return []

        if len(cleaned) > max_count:
            return cleaned[:max_count]

        expanded = list(cleaned)
        fragments: List[str] = []
        for line in cleaned:
            for part in re.split(r"[，,。；;：:、]", line):
                token = part.strip()
                if len(token) < 4:
                    continue
                if token in expanded or token in fragments:
                    continue
                fragments.append(token)

        while fragments and len(expanded) < min_count:
            expanded.append(fragments.pop(0))

        suffixes = ["评估重点", "实施路径", "风险控制", "效果指标", "随访安排", "协作分工"]
        idx = 0
        guard = 0
        while len(expanded) < min_count and guard < min_count * 6:
            base = cleaned[idx % len(cleaned)]
            suffix = suffixes[len(expanded) % len(suffixes)]
            candidate = f"{base[:24]} {suffix}".strip()
            if candidate not in expanded:
                expanded.append(candidate)
            idx += 1
            guard += 1

        return expanded[:max_count]

    @staticmethod
    def _topic_keywords(topic: str) -> List[str]:
        out: List[str] = []
        for token in ("脑卒中", "卒中", "胶质瘤", "康复", "神经", "出院", "随访", "90天"):
            if token in topic and token not in out:
                out.append(token)
        for part in re.findall(r"[\u4e00-\u9fffA-Za-z0-9]{2,12}", topic):
            if part in out:
                continue
            if part in {"患者", "管理", "治疗", "方案", "研究", "项目"}:
                continue
            out.append(part)
        return out[:8]

    @staticmethod
    def _hard_anchor_terms(topic: str) -> List[str]:
        anchors: List[str] = []
        for token in ("胶质瘤", "脑卒中", "卒中", "康复", "神经", "肿瘤", "出院", "随访"):
            if token in topic and token not in anchors:
                anchors.append(token)
        return anchors[:3]

    @staticmethod
    def _enforce_topic_anchor(
        slides: List[Dict[str, object]],
        topic: str,
        hard_anchor_terms: List[str],
    ) -> List[Dict[str, object]]:
        if not slides:
            return slides
        anchor = hard_anchor_terms[0] if hard_anchor_terms else topic[:8]

        fixed: List[Dict[str, object]] = []
        for slide in slides:
            index = int(slide.get("index") or 0)
            title = str(slide.get("title") or "").strip()
            bullets_raw = slide.get("bullets", [])
            bullets = [str(x).strip() for x in bullets_raw if str(x).strip()] if isinstance(bullets_raw, list) else []
            toc_items = slide.get("toc_items", []) if isinstance(slide.get("toc_items"), list) else []
            points = slide.get("points", []) if isinstance(slide.get("points"), list) else []
            summary_items = slide.get("summary_items", []) if isinstance(slide.get("summary_items"), list) else []

            structured_chunks: List[str] = []
            structured_chunks.extend([str(x).strip() for x in toc_items if str(x).strip()])
            structured_chunks.extend([str(x).strip() for x in summary_items if str(x).strip()])
            for point in points:
                if not isinstance(point, dict):
                    continue
                structured_chunks.append(str(point.get("label") or "").strip())
                structured_chunks.append(str(point.get("body") or "").strip())

            full_text = " ".join([title] + bullets + structured_chunks)
            has_anchor = any(term in full_text for term in hard_anchor_terms) if hard_anchor_terms else bool(anchor)

            if index == 1 and topic not in title:
                title = AIAdapter._compact_line(topic, max_chars=24, prefer_prefix=False)
                has_anchor = True

            if index >= 3 and not has_anchor:
                if points and isinstance(points[0], dict):
                    body = str(points[0].get("body") or "").strip()
                    points[0]["body"] = f"围绕{anchor}，{body}" if body else f"围绕{anchor}给出核心干预路径"
                elif bullets:
                    head = bullets[0]
                    if "：" not in head and ":" not in head:
                        bullets[0] = f"{anchor}：{head}"
                    elif not head.startswith(anchor):
                        bullets[0] = f"{anchor} {head}"
                elif not summary_items and not toc_items:
                    bullets = [f"{anchor}：围绕主题给出核心干预路径"]

            fixed.append(
                {
                    "index": index,
                    "title": title,
                    "subtitle": str(slide.get("subtitle") or ""),
                    "toc_items": toc_items,
                    "section_title": str(slide.get("section_title") or title),
                    "points": points,
                    "summary_items": summary_items,
                    "bullets": bullets[:6],
                    "prototype_hint": str(slide.get("prototype_hint") or "content"),
                    "copy_pattern": str(slide.get("copy_pattern") or "general"),
                }
            )
        return fixed
