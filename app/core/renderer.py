from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Set, Tuple
from xml.etree import ElementTree as ET

from .pptx_utils import NS, R_NS, PptxArchive, list_matching, normalize_target, slide_index_from_path


@dataclass
class _ParagraphRef:
    para: ET.Element
    text_nodes: List[ET.Element]
    text: str
    order: int
    shape_id: int
    shape_y: int
    shape_x: int
    shape_cx: int
    shape_cy: int
    placeholder_type: str
    is_placeholder: bool
    is_mirrored: bool
    text_align: str = ""
    slot_id: str = ""


@dataclass
class _SlideProfile:
    path: str
    index: int
    slot_count: int
    title_slot_count: int
    max_capacity: int
    min_capacity: int
    avg_capacity: int
    label_slot_count: int = 0
    detail_slot_count: int = 0
    copy_pattern: str = "general"


class TemplateRenderer:
    """Rewrite existing template slides with generated content."""

    def render(
        self,
        template_path: Path,
        plan: Dict[str, object],
        output_path: Path,
        template_spec: Dict[str, object] | None = None,
    ) -> Dict[str, object]:
        archive = PptxArchive(template_path)
        entries = archive.list_entries()

        slide_files = sorted(
            list_matching(entries, r"^ppt/slides/slide\d+\.xml$"),
            key=slide_index_from_path,
        )

        slides = plan.get("slides", [])
        if not isinstance(slides, list) or not slides:
            raise ValueError("Invalid plan: missing slides")

        target_count = len(slides)
        selected_slide_paths = self._route_slide_paths(
            archive=archive,
            slide_files=slide_files,
            planned_slides=slides,
        )
        if len(selected_slide_paths) != target_count:
            selected_slide_paths = [slide_files[i % len(slide_files)] for i in range(target_count)]
        selected_slide_paths = self._materialize_planned_slides(archive, selected_slide_paths)
        applied = 0

        for i in range(target_count):
            slide_path = selected_slide_paths[i]
            slide = slides[i] if isinstance(slides[i], dict) else {}
            title = str(slide.get("title", "")).strip()
            lines = self._slide_content_lines(slide, title)
            bindings = self._slot_bindings_for_slide(template_spec or {}, slide_path, slide)
            self._rewrite_slide_text(archive, slide_path, slide, lines, bindings)
            applied += 1

        self._reorder_selected_slides(archive, selected_slide_paths)
        self._remove_unreferenced_slide_parts(archive, selected_slide_paths)
        self._clear_template_residue_in_supporting_parts(archive)
        archive.save(output_path)
        return {
            "applied_slides": applied,
            "requested_slides": len(slides),
            "routed_slides": len(selected_slide_paths),
            "selected_slide_paths": selected_slide_paths,
            "template_slides": len(slide_files),
            "output_path": str(output_path),
        }

    def _route_slide_paths(
        self,
        archive: PptxArchive,
        slide_files: List[str],
        planned_slides: List[Dict[str, object]],
    ) -> List[str]:
        profiles = [self._profile_slide(archive, path) for path in slide_files]
        remaining = list(profiles)
        routed: List[str] = []

        for idx, slide in enumerate(planned_slides, start=1):
            if not profiles:
                break
            try:
                requested_prototype = int(slide.get("prototype_index", 0) or 0)
            except (TypeError, ValueError):
                requested_prototype = 0
            if requested_prototype:
                exact = [p for p in profiles if p.index == requested_prototype]
                if exact:
                    best = exact[0]
                    routed.append(best.path)
                    continue
            bullets_raw = slide.get("bullets", [])
            bullet_count = len(bullets_raw) if isinstance(bullets_raw, list) else 0
            needed_slots = max(2, 1 + bullet_count)
            hint = str(slide.get("prototype_hint", "content")).strip().lower() or "content"
            copy_pattern = str(slide.get("copy_pattern", "") or "").strip().lower()
            available_profiles = remaining if remaining else profiles

            if hint == "cover" or idx == 1:
                cover_candidates = [p for p in available_profiles if p.title_slot_count > 0 and p.slot_count <= 4]
                if cover_candidates:
                    best = min(cover_candidates, key=lambda p: (abs(p.slot_count - 2), p.index))
                    routed.append(best.path)
                    remaining = [p for p in remaining if p.path != best.path]
                    continue

            if hint == "toc" or idx == 2:
                toc_candidates = [p for p in available_profiles if 4 <= p.slot_count <= 10]
                if toc_candidates:
                    best = min(toc_candidates, key=lambda p: (abs(p.slot_count - 6), p.index))
                    routed.append(best.path)
                    remaining = [p for p in remaining if p.path != best.path]
                    continue

            candidate_pool = [p for p in available_profiles if p.title_slot_count > 0]
            if not candidate_pool:
                candidate_pool = available_profiles
            if hint not in {"cover", "toc"} and needed_slots <= 5:
                compact_pool = [p for p in candidate_pool if 3 <= p.slot_count <= 10]
                if compact_pool:
                    candidate_pool = compact_pool

            best = min(
                candidate_pool,
                key=lambda p: (
                    self._route_penalty(
                        profile=p,
                        needed_slots=needed_slots,
                        hint=hint,
                        slide_number=idx,
                        copy_pattern=copy_pattern,
                    ),
                    abs(p.slot_count - needed_slots),
                    p.index,
                ),
            )
            routed.append(best.path)
            remaining = [p for p in remaining if p.path != best.path]

        return routed

    def _materialize_planned_slides(self, archive: PptxArchive, source_slide_paths: List[str]) -> List[str]:
        if not source_slide_paths:
            return []

        presentation_path = "ppt/presentation.xml"
        rels_path = "ppt/_rels/presentation.xml.rels"
        content_types_path = "[Content_Types].xml"
        if not archive.has(presentation_path) or not archive.has(rels_path) or not archive.has(content_types_path):
            return source_slide_paths

        existing_slide_paths = list_matching(archive.list_entries(), r"^ppt/slides/slide\d+\.xml$")
        next_slide_index = max([slide_index_from_path(path) for path in existing_slide_paths] or [0]) + 1

        pres_root = archive.read_xml(presentation_path)
        slide_list = pres_root.find("p:sldIdLst", NS)
        if slide_list is None:
            return source_slide_paths

        rel_root = archive.read_xml(rels_path)
        existing_rids = [
            str(rel.attrib.get("Id", ""))
            for rel in rel_root.findall("pr:Relationship", NS)
            if str(rel.attrib.get("Id", "")).startswith("rId")
        ]
        rid_numbers = []
        for rid in existing_rids:
            try:
                rid_numbers.append(int(rid[3:]))
            except ValueError:
                continue
        next_rid = max(rid_numbers or [0]) + 1

        existing_ids = []
        for node in list(slide_list):
            try:
                existing_ids.append(int(node.attrib.get("id", "0")))
            except ValueError:
                continue
        next_slide_id = max(existing_ids or [255]) + 1

        ct_root = archive.read_xml(content_types_path)
        ct_tag = ct_root.tag.split("}", 1)[0].strip("{") if ct_root.tag.startswith("{") else ""
        override_tag = f"{{{ct_tag}}}Override" if ct_tag else "Override"
        known_parts = {
            str(node.attrib.get("PartName", ""))
            for node in ct_root.findall(f".//{override_tag}")
        }

        materialized_paths: List[str] = []
        new_slide_nodes: List[ET.Element] = []
        for source_path in source_slide_paths:
            if not archive.has(source_path):
                continue
            dest_path = f"ppt/slides/slide{next_slide_index}.xml"
            next_slide_index += 1
            archive.entries[dest_path] = archive.entries[source_path]

            source_rels = self._slide_rels_path(source_path)
            if archive.has(source_rels):
                archive.entries[self._slide_rels_path(dest_path)] = archive.entries[source_rels]

            rid = f"rId{next_rid}"
            next_rid += 1
            rel_node = ET.SubElement(rel_root, f"{{{NS['pr']}}}Relationship")
            rel_node.attrib.update(
                {
                    "Id": rid,
                    "Type": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide",
                    "Target": dest_path.replace("ppt/", ""),
                }
            )

            slide_node = ET.Element(f"{{{NS['p']}}}sldId")
            slide_node.attrib["id"] = str(next_slide_id)
            slide_node.attrib[f"{{{R_NS}}}id"] = rid
            next_slide_id += 1
            new_slide_nodes.append(slide_node)
            materialized_paths.append(dest_path)

            part_name = f"/{dest_path}"
            if part_name not in known_parts:
                override = ET.SubElement(ct_root, override_tag)
                override.attrib.update(
                    {
                        "PartName": part_name,
                        "ContentType": "application/vnd.openxmlformats-officedocument.presentationml.slide+xml",
                    }
                )
                known_parts.add(part_name)

        if len(materialized_paths) != len(source_slide_paths):
            return source_slide_paths

        for child in list(slide_list):
            slide_list.remove(child)
        for node in new_slide_nodes:
            slide_list.append(node)

        archive.write_xml(presentation_path, pres_root)
        archive.write_xml(rels_path, rel_root)
        archive.write_xml(content_types_path, ct_root)
        return materialized_paths

    @staticmethod
    def _slide_rels_path(slide_path: str) -> str:
        name = slide_path.rsplit("/", 1)[-1]
        return f"ppt/slides/_rels/{name}.rels"

    def copy_pattern_summary(self, template_path: Path, slide_count: int) -> List[Dict[str, object]]:
        archive = PptxArchive(template_path)
        slide_files = sorted(
            list_matching(archive.list_entries(), r"^ppt/slides/slide\d+\.xml$"),
            key=slide_index_from_path,
        )
        profiles = [self._profile_slide(archive, path) for path in slide_files[:slide_count]]
        out: List[Dict[str, object]] = []
        for idx, profile in enumerate(profiles, start=1):
            pattern = profile.copy_pattern
            if idx in {1, 2}:
                pattern = "cover_toc"
            out.append(
                {
                    "index": idx,
                    "copy_pattern": pattern,
                    "slot_count": profile.slot_count,
                    "label_slot_count": profile.label_slot_count,
                    "detail_slot_count": profile.detail_slot_count,
                }
            )
        return out

    def _profile_slide(self, archive: PptxArchive, slide_path: str) -> _SlideProfile:
        root = archive.read_xml(slide_path)
        paragraphs = self._collect_paragraphs(root)
        editable = self._select_editable_paragraphs(paragraphs)

        capacities = [self._slot_capacity(p) for p in editable]
        title_slot_count = len(
            [p for p in editable if p.placeholder_type.lower() in {"title", "ctrtitle", "subtitle"}]
        )
        label_slot_count = len([p for p in editable if self._looks_like_label_slot(p)])
        detail_slot_count = len([p for p in editable if self._looks_like_detail_slot(p)])
        copy_pattern = self._classify_copy_pattern(editable)

        if not capacities:
            capacities = [16]

        return _SlideProfile(
            path=slide_path,
            index=slide_index_from_path(slide_path),
            slot_count=len(editable),
            title_slot_count=title_slot_count,
            max_capacity=max(capacities),
            min_capacity=min(capacities),
            avg_capacity=int(sum(capacities) / max(1, len(capacities))),
            label_slot_count=label_slot_count,
            detail_slot_count=detail_slot_count,
            copy_pattern=copy_pattern,
        )

    @staticmethod
    def _route_penalty(
        profile: _SlideProfile,
        needed_slots: int,
        hint: str,
        slide_number: int,
        copy_pattern: str = "",
    ) -> int:
        shortage = max(0, needed_slots - profile.slot_count)
        score = shortage * 60 + abs(profile.slot_count - needed_slots) * 8

        if hint == "cover" or slide_number == 1:
            if profile.title_slot_count <= 0:
                score += 80
            score += abs(profile.slot_count - 2) * 10
        elif hint == "toc" or slide_number == 2:
            if profile.slot_count < 4:
                score += 36
            score += abs(profile.slot_count - 6) * 6
        elif hint in {"section", "transition"}:
            if profile.title_slot_count <= 0:
                score += 120
            score += max(0, profile.slot_count - 2) * 24
            if profile.slot_count <= 3:
                score -= 30
        elif hint in {"closing", "end"}:
            if profile.title_slot_count <= 0:
                score += 100
            score += max(0, profile.slot_count - 3) * 18
        else:
            if profile.title_slot_count <= 0:
                score += 220
            if profile.slot_count <= 1:
                score += 400
            if profile.slot_count <= 2:
                score += 220
            if profile.slot_count >= 14:
                score += 16
            if profile.slot_count >= 8 and profile.min_capacity <= 16 and profile.max_capacity >= 160:
                score += 120
            oversupply = max(0, profile.slot_count - max(needed_slots, 5))
            score += oversupply * 14
            score += abs(profile.slot_count - max(4, needed_slots)) * 3

        score += profile.index
        if copy_pattern and copy_pattern in {"label_detail", "process", "dense_grid", "general"}:
            if profile.copy_pattern == copy_pattern:
                score -= 70
            elif profile.copy_pattern != "general":
                score += 35
        return score

    def _reorder_selected_slides(self, archive: PptxArchive, selected_slide_paths: List[str]) -> None:
        if not selected_slide_paths:
            return

        presentation_path = "ppt/presentation.xml"
        rels_path = "ppt/_rels/presentation.xml.rels"
        if not archive.has(presentation_path) or not archive.has(rels_path):
            return

        rel_root = archive.read_xml(rels_path)
        rid_to_target: Dict[str, str] = {}
        for rel in rel_root.findall("pr:Relationship", NS):
            rel_type = str(rel.attrib.get("Type", ""))
            if not rel_type.endswith("/slide"):
                continue
            rel_id = str(rel.attrib.get("Id", ""))
            target = str(rel.attrib.get("Target", ""))
            if rel_id and target:
                rid_to_target[rel_id] = normalize_target(presentation_path, target)

        if not rid_to_target:
            return

        pres_root = archive.read_xml(presentation_path)
        slide_list = pres_root.find("p:sldIdLst", NS)
        if slide_list is None:
            return

        nodes_by_target: Dict[str, ET.Element] = {}
        for sld_id in list(slide_list):
            rel_id = sld_id.attrib.get(f"{{{R_NS}}}id", "")
            target = rid_to_target.get(rel_id)
            if target:
                nodes_by_target[target] = sld_id

        ordered_nodes: List[ET.Element] = []
        used: Set[str] = set()
        for path in selected_slide_paths:
            if path in used:
                continue
            node = nodes_by_target.get(path)
            if node is not None:
                ordered_nodes.append(node)
                used.add(path)

        if not ordered_nodes:
            return

        for child in list(slide_list):
            slide_list.remove(child)
        for node in ordered_nodes:
            slide_list.append(node)

        archive.write_xml(presentation_path, pres_root)

    def _remove_unreferenced_slide_parts(self, archive: PptxArchive, selected_slide_paths: List[str]) -> None:
        keep = set(selected_slide_paths)
        if not keep:
            return

        presentation_path = "ppt/presentation.xml"
        rels_path = "ppt/_rels/presentation.xml.rels"
        content_types_path = "[Content_Types].xml"

        if archive.has(rels_path):
            rel_root = archive.read_xml(rels_path)
            for rel in list(rel_root.findall("pr:Relationship", NS)):
                rel_type = str(rel.attrib.get("Type", ""))
                if not rel_type.endswith("/slide"):
                    continue
                target = normalize_target(presentation_path, str(rel.attrib.get("Target", "")))
                if target not in keep:
                    rel_root.remove(rel)
            archive.write_xml(rels_path, rel_root)

        if archive.has(content_types_path):
            ct_root = archive.read_xml(content_types_path)
            for node in list(ct_root):
                if not node.tag.endswith("Override"):
                    continue
                part_name = str(node.attrib.get("PartName", "")).lstrip("/")
                if re.fullmatch(r"ppt/slides/slide\d+\.xml", part_name) and part_name not in keep:
                    ct_root.remove(node)
            archive.write_xml(content_types_path, ct_root)

        for entry in list(archive.entries.keys()):
            if re.fullmatch(r"ppt/slides/slide\d+\.xml", entry) and entry not in keep:
                archive.entries.pop(entry, None)
                archive.entries.pop(self._slide_rels_path(entry), None)

    def _rewrite_slide_text(
        self,
        archive: PptxArchive,
        slide_path: str,
        slide: Dict[str, object],
        lines: List[str],
        slot_bindings: List[Dict[str, object]] | None = None,
    ) -> None:
        previous_role = str(getattr(self, "_active_slide_role", "") or "")
        self._active_slide_role = str(slide.get("prototype_hint") or "").strip()
        root = archive.read_xml(slide_path)
        try:
            original_texts = {
                (tnode.text or "").strip()
                for tnode in root.findall(".//a:t", NS)
                if (tnode.text or "").strip()
            }
            paragraphs = self._collect_paragraphs(root)
            if not paragraphs:
                return

            cleaned = [x for x in [line.strip() for line in lines] if x]
            if not cleaned:
                return

            target_paragraphs = self._select_editable_paragraphs(
                paragraphs,
                include_decorative_numbers=str(slide.get("prototype_hint") or "").strip() == "section",
            )
            include_bound_mirrored_slots = False
            try:
                include_bound_mirrored_slots = int(slide.get("prototype_index") or 0) in {6, 8}
            except (TypeError, ValueError):
                include_bound_mirrored_slots = False
            if include_bound_mirrored_slots and isinstance(slot_bindings, list) and slot_bindings:
                bound_slot_ids = {
                    str(binding.get("slot_id") or "").strip()
                    for binding in slot_bindings
                    if isinstance(binding, dict) and str(binding.get("slot_id") or "").strip()
                }
                existing_orders = {pref.order for pref in target_paragraphs}
                target_paragraphs.extend(
                    pref
                    for pref in paragraphs
                    if pref.slot_id in bound_slot_ids and pref.order not in existing_orders
                )
            if not target_paragraphs:
                return

            assignment = self._build_contract_assignment(target_paragraphs, slide, slot_bindings or {}, paragraphs)
            if not assignment:
                assignment = self._build_assignment(target_paragraphs, cleaned)
            assigned_orders: set[int] = set(assignment.keys())
            editable_shapes = {p.shape_id for p in target_paragraphs}

            for pref in target_paragraphs:
                text = assignment.get(pref.order, "")
                if text:
                    self._set_paragraph_text(pref, text)
                else:
                    self._clear_paragraph_text(pref)

            for pref in paragraphs:
                if pref.shape_id in editable_shapes and pref.order not in assigned_orders:
                    self._clear_paragraph_text(pref)

            for pref in paragraphs:
                if pref.shape_id in editable_shapes:
                    continue
                if not pref.text:
                    continue
                if self._should_preserve_noneditable_text(pref.text):
                    continue
                self._clear_paragraph_text(pref)

            # Mirror-flipped text boxes in this template family render unreadable.
            # Keep shape geometry but clear mirrored text to avoid visual corruption.
            if any(not p.is_mirrored for p in paragraphs):
                for pref in paragraphs:
                    if pref.is_mirrored and pref.order not in assigned_orders:
                        self._clear_paragraph_text(pref)

            if not any(re.search(r"\b(19|20)\d{2}\b", line) for line in cleaned):
                for pref in paragraphs:
                    if re.fullmatch(r"(19|20)\d{2}", pref.text.strip()):
                        self._clear_paragraph_text(pref)
                for tnode in root.findall(".//a:t", NS):
                    raw = (tnode.text or "").strip()
                    if re.fullmatch(r"(19|20)\d{2}", raw):
                        tnode.text = ""

            assigned_texts: Set[str] = set()
            for value in assignment.values():
                text = value.strip()
                if not text:
                    continue
                assigned_texts.add(text)
                for part in re.split(r"[\r\n]+", text):
                    token = part.strip().lstrip("-").strip()
                    if token:
                        assigned_texts.add(token)

            if original_texts:
                for tnode in root.findall(".//a:t", NS):
                    raw = (tnode.text or "").strip()
                    if not raw:
                        continue
                    if raw not in original_texts:
                        continue
                    if raw in assigned_texts:
                        continue
                    if self._should_preserve_noneditable_text(raw):
                        continue
                    tnode.text = ""

            archive.write_xml(slide_path, root)
        finally:
            self._active_slide_role = previous_role

    @staticmethod
    def _slide_content_lines(slide: Dict[str, object], title: str) -> List[str]:
        lines = [title] if title else []
        subtitle = str(slide.get("subtitle") or "").strip()
        if subtitle:
            lines.append(subtitle)
        toc_items = slide.get("toc_items", [])
        if isinstance(toc_items, list) and toc_items:
            lines.extend([str(item).strip() for item in toc_items if str(item).strip()])
        points = slide.get("points", [])
        if isinstance(points, list) and points:
            for item in points:
                if not isinstance(item, dict):
                    continue
                label = str(item.get("label") or "").strip()
                body = str(item.get("body") or "").strip()
                if label and body:
                    lines.append(f"{label}：{body}")
                elif label:
                    lines.append(label)
                elif body:
                    lines.append(body)
        summary_items = slide.get("summary_items", [])
        if isinstance(summary_items, list) and summary_items:
            lines.extend([str(item).strip() for item in summary_items if str(item).strip()])
        bullets_raw = slide.get("bullets", [])
        if isinstance(bullets_raw, list):
            lines.extend([str(x).strip() for x in bullets_raw if str(x).strip()])
        return [line for line in lines if line]

    @staticmethod
    def _slot_bindings_for_slide(
        template_spec: Dict[str, object],
        slide_path: str,
        slide: Dict[str, object] | None = None,
    ) -> List[Dict[str, object]]:
        if not template_spec:
            return []
        ai = template_spec.get("ai_standardization", {})
        if not isinstance(ai, dict):
            return []
        bindings = ai.get("slot_bindings", [])
        if not isinstance(bindings, list):
            return []
        prototype_index = 0
        if isinstance(slide, dict):
            try:
                prototype_index = int(slide.get("prototype_index", 0) or 0)
            except (TypeError, ValueError):
                prototype_index = 0
        if prototype_index <= 0:
            prototype_index = slide_index_from_path(slide_path)
        out: List[Dict[str, object]] = []
        for item in bindings:
            if not isinstance(item, dict):
                continue
            try:
                idx = int(item.get("prototype_index", 0) or 0)
            except (TypeError, ValueError):
                continue
            if idx == prototype_index:
                out.append(item)
        return out

    def _build_contract_assignment(
        self,
        targets: List[_ParagraphRef],
        slide: Dict[str, object],
        slot_bindings: List[Dict[str, object]] | Dict[str, object],
        all_paragraphs: List[_ParagraphRef] | None = None,
    ) -> Dict[int, str]:
        if not targets or not isinstance(slot_bindings, list) or not slot_bindings:
            return {}
        target_by_slot = {pref.slot_id: pref for pref in targets if pref.slot_id}
        if not target_by_slot:
            return {}

        points = [p for p in slide.get("points", []) if isinstance(p, dict)] if isinstance(slide.get("points"), list) else []
        toc_items = [str(x).strip() for x in slide.get("toc_items", []) if str(x).strip()] if isinstance(slide.get("toc_items"), list) else []
        summary_items = [str(x).strip() for x in slide.get("summary_items", []) if str(x).strip()] if isinstance(slide.get("summary_items"), list) else []
        bullets = [str(x).strip() for x in slide.get("bullets", []) if str(x).strip()] if isinstance(slide.get("bullets"), list) else []
        assignment: Dict[int, str] = {}
        counters: Dict[str, int] = {}
        body_binding_count = len([b for b in slot_bindings if isinstance(b, dict) and str(b.get("semantic") or "body").strip() == "body"])
        point_body_binding_count = len([b for b in slot_bindings if isinstance(b, dict) and str(b.get("semantic") or "").strip() == "point_body"])
        visible_page_title = False
        target_orders = {pref.order for pref in targets}
        for binding in slot_bindings:
            if not isinstance(binding, dict):
                continue
            if str(binding.get("semantic") or "").strip() != "page_title":
                continue
            pref = target_by_slot.get(str(binding.get("slot_id") or "").strip())
            if (
                pref is not None
                and (
                    self._is_title_slot(pref)
                    or (
                        pref.shape_cx > 0
                        and pref.shape_cy > 0
                        and pref.shape_x < 100000000
                        and pref.shape_y < 100000000
                    )
                )
            ):
                visible_page_title = True
                break
        if not visible_page_title and all_paragraphs:
            for pref in all_paragraphs:
                if pref.order in target_orders:
                    continue
                if self._looks_like_visible_template_title(pref):
                    visible_page_title = True
                    break
        title_for_visible_body = ""
        if str(slide.get("prototype_hint") or "").strip() == "content" and not visible_page_title:
            title_for_visible_body = str(slide.get("title") or "").strip()
        title_prefix_used = False
        compact_card_body_values: Dict[str, str] = {}
        if body_binding_count >= 4 and len(bullets) >= 3:
            body_slots = [
                target_by_slot.get(str(b.get("slot_id") or "").strip())
                for b in slot_bindings
                if isinstance(b, dict) and str(b.get("semantic") or "body").strip() == "body"
            ]
            body_slots = [slot for slot in body_slots if slot is not None]
            card_slots = [
                slot
                for slot in body_slots
                if 1800000 <= slot.shape_cx <= 3400000 and 1800000 <= slot.shape_cy <= 3400000
            ]
            footer_slots = [
                slot
                for slot in body_slots
                if slot.shape_y >= 4300000 and slot.shape_cx >= 8000000 and slot.shape_cy <= 1800000
            ]
            if len(card_slots) >= 3 and footer_slots:
                card_slots = sorted(card_slots, key=lambda slot: (slot.shape_y, slot.shape_x))[:3]
                footer_slot = max(footer_slots, key=lambda slot: slot.shape_cx * slot.shape_cy)
                detail_lines: List[str] = []
                for offset, bullet in enumerate(bullets):
                    label, body = self._split_label_body(bullet)
                    if offset < len(card_slots):
                        compact_card_body_values[card_slots[offset].slot_id] = label or body
                    if label and body:
                        detail_lines.append(f"- {label}：{body}")
                    else:
                        detail_lines.append(f"- {body or label}")
                compact_card_body_values[footer_slot.slot_id] = "\n".join(detail_lines)

        def with_visible_title_prefix(value: str) -> str:
            nonlocal title_prefix_used
            clean = str(value or "").strip()
            if not clean or not title_for_visible_body or title_prefix_used:
                return clean
            title_clean = re.sub(r"\s+", "", title_for_visible_body)
            value_clean = re.sub(r"\s+", "", clean)
            title_prefix_used = True
            if title_clean and title_clean[:8] in value_clean:
                return clean
            return f"{title_for_visible_body}\n{clean}"

        def active_slot() -> _ParagraphRef | None:
            active_slot_id = str(counters.get("_active_slot_id", "") or "")
            return target_by_slot.get(active_slot_id)

        def label_for_item(raw: str, fallback: str = "") -> str:
            label, _ = self._split_label_body(raw)
            return (label or fallback or raw).strip()

        def next_value(semantic: str) -> str:
            offset = counters.get(semantic, 0)
            counters[semantic] = offset + 1
            if semantic in {"deck_title", "page_title"}:
                return str(slide.get("title") or "").strip()
            if semantic == "section_title":
                if (
                    str(slide.get("prototype_hint") or "").strip() == "section"
                    and offset == 0
                    and str(slide.get("section_number") or "").strip()
                ):
                    return str(slide.get("section_number") or "").strip()
                return str(slide.get("section_title") or slide.get("title") or "").strip()
            if semantic == "subtitle":
                return str(slide.get("subtitle") or "").strip()
            if semantic == "presenter":
                return self._first_matching_line(bullets, ("汇报人", "报告人", "主讲", "作者"))
            if semantic == "date":
                return self._first_matching_line(bullets, ("日期", "时间", "202", "203"))
            if semantic == "toc_item":
                return toc_items[offset] if offset < len(toc_items) else ""
            if semantic == "point_label":
                if offset < len(points):
                    return str(points[offset].get("label") or "").strip()
                if offset < len(bullets):
                    label, body = self._split_label_body(bullets[offset])
                    return label if label and label != body else f"要点{offset + 1}"
                return ""
            if semantic == "point_body":
                if point_body_binding_count <= 1 and len(points) > 1:
                    return with_visible_title_prefix(self._format_point_lines(points))
                if offset == point_body_binding_count - 1 and len(points) > point_body_binding_count:
                    return with_visible_title_prefix(self._format_point_lines(points[offset:]))
                if offset < len(points):
                    return with_visible_title_prefix(str(points[offset].get("body") or "").strip())
                if point_body_binding_count <= 1 and len(bullets) > 1:
                    return with_visible_title_prefix("\n".join([f"- {item}" for item in bullets]))
                if offset == point_body_binding_count - 1 and len(bullets) > point_body_binding_count:
                    return with_visible_title_prefix("\n".join([f"- {item}" for item in bullets[offset:]]))
                if offset < len(bullets):
                    label, body = self._split_label_body(bullets[offset])
                    return with_visible_title_prefix(body or label or bullets[offset])
                return ""
            if semantic in {"summary_item", "closing_message"}:
                if semantic == "closing_message":
                    return str(slide.get("title") or "谢谢聆听").strip()
                return summary_items[offset] if offset < len(summary_items) else ""
            if semantic == "body":
                active_slot_id = str(counters.get("_active_slot_id", "") or "")
                if active_slot_id in compact_card_body_values:
                    return with_visible_title_prefix(compact_card_body_values[active_slot_id])
                slot = active_slot()
                if slot is not None and (self._looks_like_label_slot(slot) or self._slot_capacity(slot) < 32):
                    if offset < len(points):
                        return str(points[offset].get("label") or "").strip()
                    if offset < len(bullets):
                        label = label_for_item(bullets[offset])
                        return label if label != bullets[offset].strip() else ""
                if offset < len(bullets):
                    if body_binding_count > 1 and offset == body_binding_count - 1 and len(bullets) > body_binding_count:
                        return with_visible_title_prefix("\n".join([f"- {item}" for item in bullets[offset:]]))
                    return with_visible_title_prefix(bullets[offset])
                if offset < len(points):
                    if body_binding_count <= 1 and len(points) > 1:
                        return with_visible_title_prefix(self._format_point_lines(points))
                    if body_binding_count > 1 and offset == body_binding_count - 1 and len(points) > body_binding_count:
                        return with_visible_title_prefix(self._format_point_lines(points[offset:]))
                    if title_for_visible_body and not title_prefix_used:
                        return with_visible_title_prefix(self._format_point_lines(points[offset : offset + 1]))
                    label = str(points[offset].get("label") or "").strip()
                    body = str(points[offset].get("body") or "").strip()
                    return f"{label}：{body}".strip("：")
                if summary_items:
                    return with_visible_title_prefix("\n".join([f"- {item}" for item in summary_items]))
                return ""
            return ""

        for binding in slot_bindings:
            if not isinstance(binding, dict):
                continue
            semantic = str(binding.get("semantic") or "body").strip()
            if semantic == "ignore":
                continue
            slot_id = str(binding.get("slot_id") or "").strip()
            pref = target_by_slot.get(slot_id)
            if pref is None:
                continue
            counters["_active_slot_id"] = slot_id  # type: ignore[assignment]
            value = next_value(semantic)
            if value:
                assignment[pref.order] = self._fit_text_to_slot(pref, value)
        counters.pop("_active_slot_id", None)

        return assignment

    @staticmethod
    def _format_point_lines(points: List[Dict[str, object]]) -> str:
        lines: List[str] = []
        for point in points:
            label = str(point.get("label") or "").strip()
            body = str(point.get("body") or "").strip()
            if label and body:
                lines.append(f"- {label}：{body}")
            elif label:
                lines.append(f"- {label}")
            elif body:
                lines.append(f"- {body}")
        return "\n".join(lines)

    @staticmethod
    def _split_label_body(text: str) -> Tuple[str, str]:
        raw = str(text or "").strip()
        match = re.match(r"^([^:：]{2,18})[:：]\s*(.+)$", raw)
        if match:
            return match.group(1).strip(), match.group(2).strip()
        compact = re.sub(r"\s+", " ", raw).strip()
        if len(re.sub(r"\s+", "", compact)) > 14:
            return "", raw
        if re.search(r"[A-Za-z]", compact):
            label = " ".join(compact.split()[:3]).strip("，,。.;；:：")
        else:
            label = compact[:10].strip("，,。.;；:：")
        return label, raw

    @staticmethod
    def _first_matching_line(lines: List[str], tokens: Tuple[str, ...]) -> str:
        for line in lines:
            if any(token in line for token in tokens):
                return line
        return ""

    def _collect_paragraphs(self, root: ET.Element) -> List[_ParagraphRef]:
        shaped: List[
            tuple[int, int, int, int, int, int, ET.Element, List[ET.Element], str, bool, str, bool, str, str]
        ] = []
        shapes = root.findall(".//p:sp", NS)

        for shape_idx, sp in enumerate(shapes):
            y, x, cx, cy = self._shape_geometry(sp)
            placeholder_type, is_placeholder = self._placeholder_info(sp)
            is_mirrored = self._is_mirrored_shape(sp)

            for para_idx, para in enumerate(sp.findall("./p:txBody/a:p", NS)):
                text_nodes = para.findall(".//a:t", NS)
                text = " ".join([(n.text or "").strip() for n in text_nodes if (n.text or "").strip()]).strip()
                has_run = para.find(".//a:r", NS) is not None
                text_align = self._paragraph_alignment(para)

                # Keep empty placeholder paragraphs so cover/title placeholders can be filled.
                if not text and not text_nodes and not has_run and not is_placeholder:
                    continue

                shaped.append(
                    (
                        y,
                        x,
                        cx,
                        cy,
                        shape_idx,
                        para_idx,
                        para,
                        text_nodes,
                        text,
                        is_placeholder,
                        placeholder_type,
                        is_mirrored,
                        text_align,
                        f"s{shape_idx + 1}_{para_idx + 1}",
                    )
                )

        shaped.sort(key=lambda x: (x[0], x[1], x[2], x[3]))

        out: List[_ParagraphRef] = []
        for order, item in enumerate(shaped):
            (
                y,
                x,
                cx,
                cy,
                shape_idx,
                _,
                para,
                text_nodes,
                text,
                is_placeholder,
                placeholder_type,
                is_mirrored,
                text_align,
                slot_id,
            ) = item
            out.append(
                _ParagraphRef(
                    para=para,
                    text_nodes=text_nodes,
                    text=text,
                    order=order,
                    shape_id=shape_idx,
                    shape_y=y,
                    shape_x=x,
                    shape_cx=cx,
                    shape_cy=cy,
                    placeholder_type=placeholder_type,
                    is_placeholder=is_placeholder,
                    is_mirrored=is_mirrored,
                    text_align=text_align,
                    slot_id=slot_id,
                )
            )
        return out

    @staticmethod
    def _paragraph_alignment(para: ET.Element) -> str:
        ppr = para.find("./a:pPr", NS)
        if ppr is None:
            return ""
        return str(ppr.attrib.get("algn", "")).strip().lower()

    def _shape_geometry(self, sp: ET.Element) -> tuple[int, int, int, int]:
        off = sp.find("./p:spPr/a:xfrm/a:off", NS)
        ext = sp.find("./p:spPr/a:xfrm/a:ext", NS)
        y = self._to_int(off.attrib.get("y") if off is not None else None)
        x = self._to_int(off.attrib.get("x") if off is not None else None)
        cx = self._to_int(ext.attrib.get("cx") if ext is not None else None, fallback=0)
        cy = self._to_int(ext.attrib.get("cy") if ext is not None else None, fallback=0)
        return y, x, cx, cy

    def _placeholder_info(self, sp: ET.Element) -> tuple[str, bool]:
        ph = sp.find("./p:nvSpPr/p:nvPr/p:ph", NS)
        if ph is None:
            return "", False
        return str(ph.attrib.get("type", "")).strip(), True

    def _is_mirrored_shape(self, sp: ET.Element) -> bool:
        xfrm = sp.find("./p:spPr/a:xfrm", NS)
        if xfrm is None:
            return False
        return xfrm.attrib.get("flipH") == "1" or xfrm.attrib.get("flipV") == "1"

    @staticmethod
    def _to_int(raw: str | None, fallback: int = 10**9) -> int:
        if not raw:
            return fallback
        try:
            return int(raw)
        except ValueError:
            return fallback

    def _select_editable_paragraphs(
        self,
        paragraphs: List[_ParagraphRef],
        *,
        include_decorative_numbers: bool = False,
    ) -> List[_ParagraphRef]:
        non_mirrored = [p for p in paragraphs if not p.is_mirrored]
        pool = non_mirrored if non_mirrored else paragraphs

        candidates: List[_ParagraphRef] = []
        for pref in pool:
            if pref.is_placeholder:
                if self._is_aux_placeholder(pref.placeholder_type):
                    continue
                candidates.append(pref)
                continue

            if pref.text and self._is_decorative_text(pref.text):
                if include_decorative_numbers and re.fullmatch(r"\d{1,2}", pref.text.strip()):
                    candidates.append(pref)
                    continue
                continue

            if pref.text:
                candidates.append(pref)
                continue

            # Keep large blank text boxes used as custom content containers.
            if pref.shape_cx >= 1600000 and pref.shape_cy >= 320000:
                candidates.append(pref)

        if not candidates:
            return []

        def _priority(pref: _ParagraphRef) -> tuple[int, int, int, int]:
            ph = pref.placeholder_type.lower()
            if ph in {"title", "ctrtitle", "subtitle"}:
                p = 0
            elif pref.is_placeholder:
                p = 1
            elif self._is_placeholder_like(pref.text):
                p = 2
            else:
                p = 3
            return p, pref.shape_y, pref.shape_x, pref.order

        ranked = sorted(candidates, key=_priority)
        if len(ranked) <= 14:
            return ranked

        # Extremely dense templates may pre-build many paragraphs in a few shapes.
        # Cap editable paragraphs per shape to reduce overflow risk.
        trimmed: List[_ParagraphRef] = []
        per_shape: Dict[int, int] = {}
        for pref in ranked:
            limit = 2 if pref.is_placeholder else 1
            used = per_shape.get(pref.shape_id, 0)
            if used >= limit:
                continue
            per_shape[pref.shape_id] = used + 1
            trimmed.append(pref)
        return trimmed if trimmed else ranked

    @staticmethod
    def _is_aux_placeholder(placeholder_type: str) -> bool:
        ph = (placeholder_type or "").strip().lower()
        return ph in {"dt", "ftr", "sldnum", "hdr"}

    def _build_assignment(self, targets: List[_ParagraphRef], cleaned_lines: List[str]) -> Dict[int, str]:
        self._active_content_slot_count = 0
        self._active_detail_slot_count = 0
        if not targets or not cleaned_lines:
            return {}

        assignment: Dict[int, str] = {}
        used: set[int] = set()

        title_slot = self._pick_title_slot(targets)
        if title_slot is not None:
            assignment[title_slot.order] = self._fit_text_to_slot(title_slot, cleaned_lines[0])
            used.add(title_slot.order)
            remaining_lines = cleaned_lines[1:]
        else:
            remaining_lines = cleaned_lines

        content_slots = [p for p in targets if p.order not in used]
        if not content_slots or not remaining_lines:
            return assignment
        self._active_content_slot_count = len(content_slots)
        self._active_detail_slot_count = len([slot for slot in content_slots if self._looks_like_detail_slot(slot)])

        pair_assignment, used_slots, remaining_after_pairs = self._assign_label_detail_slots(
            content_slots,
            remaining_lines,
        )
        assignment.update(pair_assignment)

        residual_slots = [slot for slot in content_slots if slot.order not in used_slots]
        if residual_slots and remaining_after_pairs:
            assignment.update(self._assign_by_capacity(residual_slots, remaining_after_pairs))

        self._active_content_slot_count = 0
        self._active_detail_slot_count = 0
        return assignment

    def _assign_label_detail_slots(
        self,
        content_slots: List[_ParagraphRef],
        lines: List[str],
    ) -> Tuple[Dict[int, str], Set[int], List[str]]:
        label_slots = sorted(
            [slot for slot in content_slots if self._looks_like_label_slot(slot)],
            key=lambda p: (p.shape_y, p.shape_x, p.order),
        )
        detail_slots = sorted(
            [slot for slot in content_slots if self._looks_like_detail_slot(slot)],
            key=lambda p: (p.shape_y, p.shape_x, p.order),
        )
        if not label_slots or not detail_slots:
            return {}, set(), list(lines)

        pair_count = min(len(label_slots), len(detail_slots))
        if pair_count <= 0:
            return {}, set(), list(lines)

        pairs: List[Tuple[_ParagraphRef, _ParagraphRef]] = []
        available_details = detail_slots.copy()
        for label in label_slots[:pair_count]:
            chosen_idx = min(
                range(len(available_details)),
                key=lambda idx: abs(available_details[idx].shape_y - label.shape_y) + abs(available_details[idx].shape_x - label.shape_x),
            )
            pairs.append((label, available_details.pop(chosen_idx)))
            if not available_details:
                break
        if not pairs:
            return {}, set(), list(lines)

        normalized_lines = [self._normalize_slot_text(line) for line in lines if self._normalize_slot_text(line)]
        if not normalized_lines:
            return {}, set(), list(lines)

        # Each source line can feed a "label + detail" pair if it contains separators such as "：".
        while len(normalized_lines) < len(pairs):
            expanded = self._expand_lines_for_slots(normalized_lines, len(pairs))
            if len(expanded) <= len(normalized_lines):
                break
            normalized_lines = expanded

        assignment: Dict[int, str] = {}
        used: Set[int] = set()
        consumed = 0
        for pair_index, (label_slot, detail_slot) in enumerate(pairs):
            if pair_index >= len(normalized_lines):
                break
            line = normalized_lines[pair_index]
            label_text, detail_text = self._split_line_for_pair(line)
            if not label_text:
                continue
            if not detail_text:
                detail_text = line

            assignment[label_slot.order] = self._fit_text_to_slot(label_slot, label_text)
            assignment[detail_slot.order] = self._fit_text_to_slot(detail_slot, detail_text)
            used.add(label_slot.order)
            used.add(detail_slot.order)
            consumed = pair_index + 1

        return assignment, used, normalized_lines[consumed:]

    def _assign_by_capacity(self, content_slots: List[_ParagraphRef], remaining_lines: List[str]) -> Dict[int, str]:
        if not content_slots or not remaining_lines:
            return {}
        if len(content_slots) == 1:
            slot = content_slots[0]
            return {slot.order: self._fit_text_to_slot(slot, self._format_lines(remaining_lines))}

        if len(remaining_lines) < len(content_slots):
            if len(content_slots) >= 16:
                min_target = 16
            elif len(content_slots) >= 12:
                min_target = 12
            else:
                min_target = 8
            target_lines = min(len(content_slots), max(len(remaining_lines), min_target))
            remaining_lines = self._expand_lines_for_slots(remaining_lines, target_lines)

        assignment: Dict[int, str] = {}
        slots_by_capacity = sorted(content_slots, key=self._slot_capacity)
        small_count = len(slots_by_capacity) // 2
        small_slots = slots_by_capacity[:small_count]
        large_slots = slots_by_capacity[small_count:]

        pool = list(remaining_lines)
        for slot in small_slots:
            if not pool:
                break
            idx = min(range(len(pool)), key=lambda i: len(pool[i]))
            assignment[slot.order] = self._fit_text_to_slot(slot, pool.pop(idx))

        for slot in sorted(large_slots, key=self._slot_capacity, reverse=True):
            if not pool:
                break
            idx = max(range(len(pool)), key=lambda i: len(pool[i]))
            assignment[slot.order] = self._fit_text_to_slot(slot, pool.pop(idx))

        if pool:
            merge_slot = max(content_slots, key=self._slot_capacity)
            merge_cap = self._slot_capacity(merge_slot)
            if len(content_slots) == 1 and (merge_slot.shape_cx <= 0 or merge_slot.is_placeholder):
                return assignment
            if len(content_slots) == 1 and merge_cap <= 28:
                return assignment
            if merge_cap <= 20:
                return assignment

            existing = assignment.get(merge_slot.order, "")
            merged_extra = self._format_lines(pool)
            merged = f"{existing}\n{merged_extra}".strip() if existing else merged_extra
            assignment[merge_slot.order] = self._fit_text_to_slot(merge_slot, merged)
        return assignment

    @staticmethod
    def _looks_like_label_slot(pref: _ParagraphRef) -> bool:
        if pref.placeholder_type.lower() in {"title", "ctrtitle", "subtitle"}:
            return False
        if pref.shape_cx <= 0:
            return False
        return pref.text_align in {"ctr"} and pref.shape_cx <= 3600000

    @staticmethod
    def _looks_like_detail_slot(pref: _ParagraphRef) -> bool:
        if pref.placeholder_type.lower() in {"title", "ctrtitle", "subtitle"}:
            return False
        if pref.shape_cx <= 0:
            return False
        if pref.shape_cx < 4200000:
            return False
        return pref.text_align in {"", "l", "just", "justlow", "dist", "thaidist"}

    def _classify_copy_pattern(self, editable: List[_ParagraphRef]) -> str:
        if not editable:
            return "general"

        content = [p for p in editable if not self._is_title_slot(p)]
        if not content:
            return "cover_toc"

        label_count = len([p for p in content if self._looks_like_label_slot(p)])
        detail_count = len([p for p in content if self._looks_like_detail_slot(p)])
        slot_count = len(content)

        if label_count >= 2 and detail_count >= 2 and abs(label_count - detail_count) <= 2:
            return "label_detail"

        if slot_count >= 8:
            capacities = [self._slot_capacity(p) for p in content]
            if capacities and max(capacities) <= 56:
                return "dense_grid"

        if self._looks_like_process_layout(content):
            return "process"

        return "general"

    @staticmethod
    def _looks_like_process_layout(content: List[_ParagraphRef]) -> bool:
        if len(content) < 3 or len(content) > 8:
            return False
        xs = [p.shape_x for p in content if p.shape_x < 10**8]
        ys = [p.shape_y for p in content if p.shape_y < 10**8]
        if len(xs) < 3 or len(ys) < 3:
            return False
        horizontal_span = max(xs) - min(xs)
        vertical_span = max(ys) - min(ys)
        return horizontal_span >= 3600000 and vertical_span <= 1800000

    @staticmethod
    def _split_line_for_pair(line: str) -> Tuple[str, str]:
        raw = (line or "").strip()
        if not raw:
            return "", ""

        for sep in ("：", ":", "—", "-", "｜", "|"):
            if sep not in raw:
                continue
            lead, tail = raw.split(sep, 1)
            lead = lead.strip()
            tail = tail.strip()
            if 2 <= len(lead) <= 16 and tail:
                return lead, raw
        if len(raw) <= 16:
            return raw, raw
        return raw[: min(12, len(raw))].strip(), raw

    def _pick_title_slot(self, targets: List[_ParagraphRef]) -> _ParagraphRef | None:
        title_like = [p for p in targets if p.placeholder_type.lower() in {"title", "ctrtitle", "subtitle"}]
        if title_like:
            return min(title_like, key=lambda p: (p.shape_y, p.shape_x, p.order))
        return None

    @staticmethod
    def _format_lines(lines: List[str]) -> str:
        cleaned = [line.strip() for line in lines if line.strip()]
        if not cleaned:
            return ""
        if len(cleaned) == 1:
            return cleaned[0]
        return "\n".join([f"- {line}" for line in cleaned])

    @staticmethod
    def _expand_lines_for_slots(lines: List[str], target_count: int) -> List[str]:
        cleaned = [line.strip() for line in lines if line.strip()]
        if target_count <= 0 or not cleaned:
            return cleaned
        if len(cleaned) >= target_count:
            return cleaned

        expanded = list(cleaned)
        fragments: List[str] = []
        for line in cleaned:
            for frag in re.split(r"[，,。；;：:、]", line):
                token = frag.strip()
                if len(token) < 4:
                    continue
                if token in expanded or token in fragments:
                    continue
                fragments.append(token)

        while fragments and len(expanded) < target_count:
            expanded.append(fragments.pop(0))

        suffixes = ["评估重点", "实施路径", "协作分工", "风险控制", "效果指标", "随访安排"]
        seed_index = 0
        guard = 0
        while len(expanded) < target_count and guard < target_count * 6:
            base = cleaned[seed_index % len(cleaned)]
            suffix = suffixes[len(expanded) % len(suffixes)]
            candidate = f"{base[:16]} {suffix}".strip()
            if candidate not in expanded:
                expanded.append(candidate)
            seed_index += 1
            guard += 1

        return expanded

    def _slot_capacity(self, pref: _ParagraphRef) -> int:
        if pref.shape_cx <= 0 or pref.shape_cy <= 0:
            return 42
        width_units = pref.shape_cx / 110000
        height_units = pref.shape_cy / 260000
        cap = int(width_units * max(1.0, height_units) * 1.2)
        if pref.shape_cx < 2800000:
            cap = min(cap, 48 if pref.shape_cy >= 1700000 else 14)
        elif pref.shape_cx < 3200000:
            cap = min(cap, 56 if pref.shape_cy >= 1700000 else 18)
        elif pref.shape_cx < 3800000:
            cap = min(cap, 64 if pref.shape_cy >= 1700000 else 24)
        if pref.shape_cy < 900000:
            if pref.shape_cx >= 7000000:
                cap = min(cap, 88)
            elif pref.shape_cx >= 5200000:
                cap = min(cap, 72)
            elif pref.shape_cx >= 3800000:
                cap = min(cap, 56)
            else:
                cap = min(cap, 20)
        return max(10, min(cap, 180))

    def _fit_text_to_slot(self, pref: _ParagraphRef, text: str) -> str:
        clean = self._normalize_slot_text(text)
        if not clean:
            return ""
        clean = self._enrich_detail_slot_text(pref, clean)
        if self._prefer_single_line(pref, clean):
            min_size = self._single_line_min_size(pref)
            max_units = self._max_visual_units_for_single_line(pref, min_size)
            if self._visual_units(clean) <= max_units:
                return clean
            return self._truncate_to_visual_units(clean, max(3.0, max_units - 0.8))
        cap = self._slot_capacity(pref)
        if self._is_title_slot(pref):
            cap = max(cap, 72)
        if len(clean) <= cap:
            return clean
        clipped = self._clip_to_complete_phrase(clean, max(1, cap))
        if (
            not self._is_title_slot(pref)
            and len(clipped) < len(clean)
            and len(re.sub(r"\s+", "", clipped)) >= 8
            and not re.search(r"[。！？!?；;，,、：:]", clipped)
        ):
            return ""
        return clipped

    def _enrich_detail_slot_text(self, pref: _ParagraphRef, text: str) -> str:
        clean = text.strip()
        if not clean:
            return ""
        if not self._looks_like_detail_slot(pref):
            return clean
        if "：" not in clean and ":" not in clean and len(clean) <= 14:
            return clean
        min_len, _ = self._detail_target_range(pref)
        if len(clean) >= min_len:
            return clean

        head = ""
        tail = clean
        for sep in ("：", ":", "—", "-", "|", "｜"):
            if sep not in clean:
                continue
            h, t = clean.split(sep, 1)
            h = h.strip()
            t = t.strip()
            if h and t:
                head = h
                tail = t
                break

        if len(tail) >= 12:
            return clean

        supplements = [
            "明确筛查方法和复评节奏",
            "说明适用条件和安全边界",
            "记录目标和复评依据",
            "同步观察风险信号",
        ]
        idx = 0
        while len(tail) < min_len and idx < len(supplements):
            suffix = supplements[idx]
            if suffix not in tail:
                tail = f"{tail}，{suffix}" if tail else suffix
            idx += 1

        if head:
            return f"{head}：{tail}"
        return tail

    def _detail_target_range(self, pref: _ParagraphRef) -> Tuple[int, int]:
        cap = self._slot_capacity(pref)
        if cap >= 80:
            min_len, max_len = 28, 52
        elif cap >= 64:
            min_len, max_len = 24, 44
        elif cap >= 48:
            min_len, max_len = 20, 36
        elif cap >= 36:
            min_len, max_len = 16, 30
        else:
            min_len, max_len = 12, 24

        content_slots = int(getattr(self, "_active_content_slot_count", 0) or 0)
        detail_slots = int(getattr(self, "_active_detail_slot_count", 0) or 0)
        if content_slots >= 10 or detail_slots >= 6:
            min_len -= 4
            max_len -= 6
        elif content_slots >= 8 or detail_slots >= 5:
            min_len -= 2
            max_len -= 4
        elif content_slots <= 4 and detail_slots <= 2:
            min_len += 4
            max_len += 6

        min_len = max(10, min_len)
        max_len = max(min_len + 6, max_len)
        return min_len, max_len

    def _set_paragraph_text(self, pref: _ParagraphRef, text: str) -> None:
        if not pref.text_nodes:
            pref.text_nodes = self._ensure_text_nodes(pref.para)
        if not pref.text_nodes:
            return
        self._remove_soft_line_breaks(pref.para)
        pref.text_nodes[0].text = text
        self._ensure_readable_typography(pref, text)
        for node in pref.text_nodes[1:]:
            node.text = ""

    @staticmethod
    def _clear_paragraph_text(pref: _ParagraphRef) -> None:
        if not pref.text_nodes:
            pref.text_nodes = TemplateRenderer._ensure_text_nodes(pref.para)
        for node in pref.text_nodes:
            node.text = ""

    @staticmethod
    def _ensure_text_nodes(para: ET.Element) -> List[ET.Element]:
        existing = para.findall(".//a:t", NS)
        if existing:
            return existing

        run = para.find("./a:r", NS)
        if run is None:
            run = ET.Element(f"{{{NS['a']}}}r")
            ET.SubElement(run, f"{{{NS['a']}}}rPr")
            end_para = para.find("./a:endParaRPr", NS)
            if end_para is not None:
                children = list(para)
                para.insert(children.index(end_para), run)
            else:
                para.append(run)

        text_node = run.find("./a:t", NS)
        if text_node is None:
            text_node = ET.SubElement(run, f"{{{NS['a']}}}t")
        return [text_node]

    @staticmethod
    def _remove_soft_line_breaks(para: ET.Element) -> None:
        br_tag = f"{{{NS['a']}}}br"
        for node in para.iter():
            for child in list(node):
                if child.tag == br_tag:
                    node.remove(child)

    def _ensure_readable_typography(self, pref: _ParagraphRef, text: str) -> None:
        min_size = 2800 if self._is_title_slot(pref) else 1800
        run_props = pref.para.findall(".//a:rPr", NS)
        if not run_props:
            return
        if str(getattr(self, "_active_slide_role", "") or "") == "section":
            if re.fullmatch(r"\d{1,2}", str(text or "").strip()):
                for rpr in run_props:
                    rpr.attrib["sz"] = "6400"
                return
            if pref.shape_cx >= 2400000 and pref.shape_cy >= 600000:
                for rpr in run_props:
                    rpr.attrib["sz"] = "3600"
                return
        current_sizes = [self._to_int(rpr.attrib.get("sz"), fallback=0) for rpr in run_props]
        non_zero_sizes = [size for size in current_sizes if size > 0]
        base_size = max(non_zero_sizes) if non_zero_sizes else min_size

        if self._prefer_single_line(pref, text):
            target_size = self._fit_single_line_font_size(pref, text, base_size)
            for rpr in run_props:
                rpr.attrib["sz"] = str(target_size)
            return

        for rpr in run_props:
            raw = rpr.attrib.get("sz")
            sz = self._to_int(raw, fallback=0)
            if sz < min_size:
                rpr.attrib["sz"] = str(min_size)

    @staticmethod
    def _normalize_slot_text(text: str) -> str:
        raw = re.sub(r"\r\n?", "\n", text or "")
        lines = [re.sub(r"[ \t]+", " ", part).strip() for part in raw.split("\n")]
        clean = "\n".join([part for part in lines if part])
        if not clean:
            return ""
        normalized_lines = []
        for part in clean.split("\n"):
            item = re.sub(r"^\s*[-•·]\s*", "", part).strip()
            item = re.sub(r"^\s*\d{1,2}[\.\)、）]\s*", "", item).strip()
            normalized_lines.append(item)
        clean = "\n".join(normalized_lines).strip()
        clean = re.sub(r"\.{2,}|…+", "", clean).strip()
        return clean

    @staticmethod
    def _is_title_slot(pref: _ParagraphRef) -> bool:
        return pref.placeholder_type.lower() in {"title", "ctrtitle", "subtitle"}

    @staticmethod
    def _looks_like_visible_template_title(pref: _ParagraphRef) -> bool:
        text = re.sub(r"\s+", "", pref.text or "")
        if not text:
            return False
        if pref.shape_cx <= 0 or pref.shape_cy <= 0:
            return False
        if pref.shape_x >= 100000000 or pref.shape_y >= 100000000:
            return False
        if pref.shape_y > 900000:
            return False
        if pref.shape_cx < 4500000:
            return False
        if len(text) > 32:
            return False
        if re.fullmatch(r"(19|20)\d{2}", text):
            return False
        if "——" in text or "页脚" in text:
            return False
        return True

    def _prefer_single_line(self, pref: _ParagraphRef, text: str) -> bool:
        if not text or "\n" in text or "\r" in text:
            return False
        if self._is_title_slot(pref):
            return True
        if (
            len(text) <= 16
            and not re.search(r"[，。；：,:;、\s]", text)
            and 0 < pref.shape_cx <= 2400000
        ):
            return True
        if pref.shape_cx <= 0 or pref.shape_cy <= 0:
            return False
        if pref.shape_cy <= 620000 and pref.shape_cx >= 1300000:
            return True
        if pref.shape_cx <= 2200000 and pref.shape_cy <= 1500000 and len(text) <= 20:
            return True
        return pref.shape_cy <= 760000 and self._slot_capacity(pref) <= 22 and len(text) <= 42

    def _single_line_min_size(self, pref: _ParagraphRef) -> int:
        return 2000 if self._is_title_slot(pref) else 1600

    def _fit_single_line_font_size(self, pref: _ParagraphRef, text: str, base_size: int) -> int:
        min_size = self._single_line_min_size(pref)
        max_size = max(min_size, base_size)
        if not self._is_title_slot(pref):
            if pref.shape_cx <= 2600000:
                max_size = min(max_size, 2000)
            elif pref.shape_cx <= 3200000:
                max_size = min(max_size, 2200)
        units = self._visual_units(text)
        if units <= 0 or pref.shape_cx <= 0:
            return max(min_size, min(max_size, base_size))

        effective_width = max(400000, pref.shape_cx - 220000)
        width_pt = effective_width / 12700.0
        # 1.08 is intentionally conservative to avoid visual wrap in narrow label boxes.
        target_pt = width_pt / (units * 1.08)
        target_size = int(target_pt * 100)
        if target_size <= 0:
            target_size = min_size
        return max(min_size, min(max_size, target_size))

    def _max_visual_units_for_single_line(self, pref: _ParagraphRef, font_size: int) -> float:
        if pref.shape_cx <= 0 or font_size <= 0:
            return 20.0
        effective_width = max(400000, pref.shape_cx - 220000)
        width_pt = effective_width / 12700.0
        font_pt = font_size / 100.0
        if font_pt <= 0:
            return 20.0
        return max(4.0, width_pt / (font_pt * 1.08))

    @staticmethod
    def _char_visual_unit(ch: str) -> float:
        if not ch:
            return 0.0
        if ch.isspace():
            return 0.32
        if ord(ch) < 128:
            return 0.58
        return 1.0

    @classmethod
    def _visual_units(cls, text: str) -> float:
        return sum(cls._char_visual_unit(ch) for ch in text)

    def _truncate_to_visual_units(self, text: str, max_units: float) -> str:
        if max_units <= 0:
            return ""
        taken: List[str] = []
        used = 0.0
        for ch in text:
            unit = self._char_visual_unit(ch)
            if used + unit > max_units:
                break
            taken.append(ch)
            used += unit
        clipped = "".join(taken).rstrip(" ,.;:，。；：、/-")
        if not clipped:
            clipped = text[:1]
        if clipped == text:
            return clipped
        return self._clip_to_complete_phrase(clipped, len(clipped))

    @staticmethod
    def _clip_to_complete_phrase(text: str, max_chars: int) -> str:
        clean = str(text or "").strip()
        if len(clean) <= max_chars:
            return clean
        if max_chars <= 0:
            return ""
        clipped = clean[:max_chars].rstrip(" ,.;:，。；：、/-")
        if not clipped:
            return ""

        sentence_boundaries = [m.end() for m in re.finditer(r"[。！？!?；;]", clipped)]
        useful_sentences = [idx for idx in sentence_boundaries if idx >= max(8, int(max_chars * 0.45))]
        if useful_sentences:
            return clipped[: useful_sentences[-1]].rstrip(" ,.;:，。；：、/-")

        comma_boundaries = [m.end() for m in re.finditer(r"[，,、]", clipped)]
        useful_commas = [idx for idx in comma_boundaries if idx >= max(10, int(max_chars * 0.55))]
        if useful_commas:
            return clipped[: useful_commas[-1]].rstrip(" ,.;:，。；：、/-")

        label_match = re.match(r"^([^：:]{1,14}[：:])(.+)$", clean)
        if label_match:
            label = label_match.group(1)
            remaining = max_chars - len(label)
            if remaining >= 6:
                body = TemplateRenderer._clip_to_complete_phrase(label_match.group(2), remaining)
                if body:
                    return f"{label}{body}".rstrip(" ,.;:，。；：、/-")
            return label.rstrip("：:")

        if len(clipped) < len(clean) and max_chars < 40:
            compact = re.sub(r"\s+", "", clipped)
            if len(compact) >= 10 and not re.search(r"[。！？!?；;，,、]", compact):
                return ""

        return clipped.rstrip(" ,.;:，。；：、/-")

    @staticmethod
    def _clear_template_residue_in_supporting_parts(archive: PptxArchive) -> None:
        markers = (
            "请输入",
            "在此输入",
            "点击添加",
            "示例",
            "样例",
            "lorem",
            "ipsum",
            "placeholder",
        )
        support_parts = sorted(
            list_matching(archive.list_entries(), r"^ppt/(slideLayouts|slideMasters)/.+\.xml$")
        )
        for part in support_parts:
            root = archive.read_xml(part)
            changed = False
            for tnode in root.findall(".//a:t", NS):
                raw = (tnode.text or "").strip()
                if not raw:
                    continue
                lower = raw.lower()
                if any(marker in raw or marker in lower for marker in markers):
                    tnode.text = ""
                    changed = True
            if changed:
                archive.write_xml(part, root)

    @staticmethod
    def _should_preserve_noneditable_text(text: str) -> bool:
        clean = re.sub(r"\s+", " ", text).strip()
        if not clean:
            return True

        protected_values = {
            "NANJING MEDICAL UNIVERSITY",
            "南京医科大学",
            "博学至精",
            "明德至善",
            "博学至精 明德至善",
        }
        if clean in protected_values:
            return True
        return False

    @staticmethod
    def _is_decorative_text(text: str) -> bool:
        clean = text.strip()
        if not clean:
            return True

        compact = re.sub(r"\s+", "", clean)
        if compact.lower() in {"contents"}:
            return True
        if compact in {"目录", "——", "—"}:
            return True
        if "博学至精" in compact and "明德至善" in compact:
            return True
        if compact in {"一段文字页", "两段文字页", "三段文字页"}:
            return True
        if re.fullmatch(r"[0-9０-９]{1,3}", compact):
            return True
        if re.fullmatch(r"[A-Z][A-Z\s]{1,20}", clean):
            return True
        if len(compact) <= 2 and re.fullmatch(r"[\W_]+", compact):
            return True
        return False

    @staticmethod
    def _is_placeholder_like(text: str) -> bool:
        clean = text.strip()
        lower = clean.lower()
        placeholder_tokens = (
            "请输入",
            "在此输入",
            "点击添加",
            "示例",
            "样例",
            "lorem",
            "ipsum",
            "placeholder",
            "demo",
            "template",
            "一段文字页",
            "两段文字页",
            "三段文字页",
            "国内研究",
            "国外研究",
        )
        if any(token in lower for token in placeholder_tokens):
            return True
        if re.search(r"\b(19|20)\d{2}\b", clean):
            return True
        if len(clean) >= 24 and re.search(r"[，。；、,.]", clean):
            return True
        return False

    @staticmethod
    def extract_slide_texts(pptx_path: Path) -> Dict[str, str]:
        archive = PptxArchive(pptx_path)
        out: Dict[str, str] = {}
        for slide_path in sorted(
            list_matching(archive.list_entries(), r"^ppt/slides/slide\d+\.xml$"),
            key=slide_index_from_path,
        ):
            root = archive.read_xml(slide_path)
            texts = [n.text or "" for n in root.findall(".//a:t", NS)]
            normalized = " ".join([x.strip() for x in texts if x.strip()])
            out[slide_path] = normalized
        return out
