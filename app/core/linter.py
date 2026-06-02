from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List

from .pptx_utils import NS, R_NS, PptxArchive, list_matching, normalize_target, slide_index_from_path


@dataclass
class SlideLintIssue:
    slide: str
    level: str
    message: str


@dataclass
class _TextBoxStat:
    text: str
    align: str
    cx: int
    cy: int


class SlideLinter:
    RESIDUE_MARKERS = (
        "在此输入",
        "请输入",
        "点击添加",
        "示例",
        "样例",
        "lorem ipsum",
        "placeholder",
        "template",
    )
    GENERIC_FILLER_MARKERS = (
        "明确执行动作与责任分工",
        "设置复评时间点与量化指标",
        "并设置复评时间点与量化指标",
        "按阶段复评并动态调整",
        "同步记录关键风险与处置策略",
        "补充评估依据、训练频次和复评节奏",
        "明确筛查方法和复评节奏",
        "说明适用条件和安全边界",
    )

    def lint(self, pptx_path: Path) -> Dict[str, object]:
        archive = PptxArchive(pptx_path)
        slide_files = self._visible_slide_files(archive)

        issues: List[SlideLintIssue] = []

        for sf in slide_files:
            root = archive.read_xml(sf)
            texts = [el.text or "" for el in root.findall(".//a:t", NS)]
            merged = " ".join([t.strip() for t in texts if t.strip()])
            text_boxes = self._collect_text_boxes(root)
            issues.extend(self._quality_issues_for_text(sf, texts))

            if not merged:
                issues.append(SlideLintIssue(slide=sf, level="warn", message="Slide text appears empty"))
                continue

            line_like_count = len([x for x in texts if x.strip()])
            is_reference_like = self._is_reference_like(merged, line_like_count)

            if len(merged) > 360 and not is_reference_like:
                issues.append(
                    SlideLintIssue(
                        slide=sf,
                        level="warn",
                        message=f"Potential text density risk ({len(merged)} chars)",
                    )
                )

            if line_like_count > 28:
                issues.append(
                    SlideLintIssue(
                        slide=sf,
                        level="info",
                        message=f"Many text runs detected ({line_like_count}), manual polish may be useful",
                    )
                )

            lower_merged = merged.lower()
            marker_hits = [m for m in self.RESIDUE_MARKERS if m in merged or m in lower_merged]
            if marker_hits:
                issues.append(
                    SlideLintIssue(
                        slide=sf,
                        level="warn",
                        message=f"Possible template residue detected: {', '.join(marker_hits)}",
                    )
                )

            if re.search(r"\b(19|20)\d{2}\b", merged) and len(merged) > 120 and not is_reference_like:
                issues.append(
                    SlideLintIssue(
                        slide=sf,
                        level="info",
                        message="Contains year-based narrative text; verify it is intentional content",
                    )
                )

            is_toc_like = ("目录" in merged or "contents" in lower_merged) and line_like_count <= 8
            is_summary_like = any(token in merged for token in ("总结", "结语", "谢谢")) and line_like_count <= 10
            if not is_toc_like and not is_summary_like and not is_reference_like:
                sparse_issue = self._sparse_content_issue(sf, text_boxes)
                if sparse_issue is not None:
                    issues.append(sparse_issue)

            supporting_texts = self._supporting_part_texts(archive, sf)
            if supporting_texts:
                supporting_merged = " ".join([t.strip() for t in supporting_texts if t.strip()])
                supporting_lower = supporting_merged.lower()
                supporting_hits = [
                    m
                    for m in self.RESIDUE_MARKERS
                    if m in supporting_merged or m in supporting_lower
                ]
                if supporting_hits:
                    issues.append(
                        SlideLintIssue(
                            slide=sf,
                            level="warn",
                            message=f"Possible template residue detected: {', '.join(supporting_hits)}",
                        )
                    )

        return {
            "issue_count": len(issues),
            "issues": [asdict(x) for x in issues],
        }

    @classmethod
    def _quality_issues_for_text(cls, slide: str, texts: List[str]) -> List[SlideLintIssue]:
        cleaned = [re.sub(r"\s+", " ", text or "").strip() for text in texts]
        cleaned = [text for text in cleaned if text]
        issues: List[SlideLintIssue] = []
        if not cleaned:
            return issues

        merged = " ".join(cleaned)
        if re.search(r"\.{2,}|…+", merged):
            issues.append(SlideLintIssue(slide=slide, level="warn", message="Hard ellipsis detected"))

        repeated: Dict[str, int] = {}
        for text in cleaned:
            if len(text) < 6:
                continue
            repeated[text] = repeated.get(text, 0) + 1
        repeated_hits = [text for text, count in repeated.items() if count >= 3]

        filler_hits = [marker for marker in cls.GENERIC_FILLER_MARKERS if merged.count(marker) >= 2]
        if repeated_hits or filler_hits:
            issues.append(
                SlideLintIssue(
                    slide=slide,
                    level="warn",
                    message="generic repeated filler detected",
                )
            )

        return issues

    @staticmethod
    def _is_reference_like(merged: str, line_like_count: int) -> bool:
        lowered = merged.lower()
        if any(token in merged for token in ("参考文献", "参考资料", "主要参考", "引用来源")):
            return True
        if any(token in lowered for token in ("references", "bibliography")):
            return True

        citation_hits = len(re.findall(r"(?:\[\d+\]|（\d+）|\(\d+\))", merged))
        numbered_reference_hits = len(re.findall(r"(?:^|\s)\d{1,2}\.\s+\S", merged))
        year_hits = len(re.findall(r"\b(19|20)\d{2}\b", merged))
        journalish_hits = len(
            re.findall(
                r"\b(?:journal|medicine|chest|respiratory|clinical|guideline|consensus|doi)\b",
                lowered,
            )
        )
        if line_like_count >= 4 and citation_hits >= 3 and (year_hits >= 2 or journalish_hits >= 2):
            return True
        if line_like_count >= 6 and numbered_reference_hits >= 3 and (year_hits >= 2 or journalish_hits >= 2):
            return True
        return line_like_count >= 6 and year_hits >= 3 and journalish_hits >= 3

    @staticmethod
    def _collect_text_boxes(root) -> List[_TextBoxStat]:
        out: List[_TextBoxStat] = []
        for sp in root.findall(".//p:sp", NS):
            ext = sp.find("./p:spPr/a:xfrm/a:ext", NS)
            cx = int(ext.attrib.get("cx", "0")) if ext is not None else 0
            cy = int(ext.attrib.get("cy", "0")) if ext is not None else 0

            for para in sp.findall("./p:txBody/a:p", NS):
                parts = [(n.text or "").strip() for n in para.findall(".//a:t", NS)]
                text = " ".join([x for x in parts if x]).strip()
                if not text:
                    continue
                ppr = para.find("./a:pPr", NS)
                align = str(ppr.attrib.get("algn", "")).strip().lower() if ppr is not None else ""
                out.append(_TextBoxStat(text=text, align=align, cx=cx, cy=cy))
        return out

    @staticmethod
    def _sparse_content_issue(slide: str, boxes: List[_TextBoxStat]) -> SlideLintIssue | None:
        if not boxes:
            return None
        detail_boxes = [
            b
            for b in boxes
            if b.cx >= 4200000 and b.align in {"", "l", "just", "justlow", "dist", "thaidist"}
        ]
        if len(detail_boxes) < 3:
            return None

        avg_len = sum(len(b.text) for b in detail_boxes) / max(1, len(detail_boxes))
        short_count = len([b for b in detail_boxes if len(b.text) < 14])
        sparse_ratio = short_count / len(detail_boxes)

        if sparse_ratio >= 0.5 or avg_len < 16:
            return SlideLintIssue(
                slide=slide,
                level="warn",
                message=(
                    f"Potential whitespace/content sparsity in detail boxes "
                    f"(avg {avg_len:.1f} chars, short ratio {sparse_ratio:.2f})"
                ),
            )
        return None

    @classmethod
    def _supporting_part_texts(cls, archive: PptxArchive, slide_path: str) -> List[str]:
        texts: List[str] = []
        for part in cls._related_supporting_parts(archive, slide_path):
            if not archive.has(part):
                continue
            root = archive.read_xml(part)
            texts.extend([el.text or "" for el in root.findall(".//a:t", NS)])
        return texts

    @staticmethod
    def _related_supporting_parts(archive: PptxArchive, slide_path: str) -> List[str]:
        parts: List[str] = []

        def rels_path_for(part: str) -> str:
            parent = part.rsplit("/", 1)[0]
            name = part.rsplit("/", 1)[1]
            return f"{parent}/_rels/{name}.rels"

        def related_part(base: str, rel_suffix: str) -> str:
            rels_path = rels_path_for(base)
            if not archive.has(rels_path):
                return ""
            rel_root = archive.read_xml(rels_path)
            for rel in rel_root.findall("pr:Relationship", NS):
                rel_type = str(rel.attrib.get("Type", ""))
                if not rel_type.endswith(rel_suffix):
                    continue
                target = str(rel.attrib.get("Target", ""))
                if target:
                    return normalize_target(base, target)
            return ""

        layout = related_part(slide_path, "/slideLayout")
        if layout:
            parts.append(layout)
            master = related_part(layout, "/slideMaster")
            if master:
                parts.append(master)

        return parts

    @staticmethod
    def _visible_slide_files(archive: PptxArchive) -> List[str]:
        presentation_path = "ppt/presentation.xml"
        rels_path = "ppt/_rels/presentation.xml.rels"

        if not archive.has(presentation_path) or not archive.has(rels_path):
            return sorted(
                list_matching(archive.list_entries(), r"^ppt/slides/slide\d+\.xml$"),
                key=slide_index_from_path,
            )

        rel_root = archive.read_xml(rels_path)
        rid_to_target: Dict[str, str] = {}
        for rel in rel_root.findall("pr:Relationship", NS):
            rel_type = str(rel.attrib.get("Type", ""))
            if not rel_type.endswith("/slide"):
                continue
            rid = str(rel.attrib.get("Id", ""))
            target = str(rel.attrib.get("Target", ""))
            if rid and target:
                rid_to_target[rid] = normalize_target(presentation_path, target)

        pres_root = archive.read_xml(presentation_path)
        slide_list = pres_root.find("p:sldIdLst", NS)
        if slide_list is None:
            return sorted(
                list_matching(archive.list_entries(), r"^ppt/slides/slide\d+\.xml$"),
                key=slide_index_from_path,
            )

        ordered: List[str] = []
        for sld_id in list(slide_list):
            rid = sld_id.attrib.get(f"{{{R_NS}}}id", "")
            target = rid_to_target.get(rid)
            if target:
                ordered.append(target)

        if ordered:
            return ordered

        return sorted(
            list_matching(archive.list_entries(), r"^ppt/slides/slide\d+\.xml$"),
            key=slide_index_from_path,
        )
