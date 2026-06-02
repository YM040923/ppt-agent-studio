from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List
from xml.etree import ElementTree as ET

from .pptx_utils import (
    NS,
    PptxArchive,
    layout_index_from_path,
    list_matching,
    normalize_target,
    slide_index_from_path,
)


@dataclass
class LayoutSpec:
    path: str
    name: str
    layout_type: str
    placeholder_count: int


@dataclass
class SlidePrototype:
    index: int
    path: str
    layout_path: str
    text_preview: str
    shape_count: int
    image_count: int
    text_slots: List[Dict[str, object]]


@dataclass
class TemplateSpec:
    template_id: str
    template_name: str
    created_at: str
    slide_count: int
    layout_count: int
    master_count: int
    theme_count: int
    layouts: List[LayoutSpec]
    prototypes: List[SlidePrototype]
    stats: Dict[str, int]

    def to_dict(self) -> Dict[str, object]:
        return {
            "template_id": self.template_id,
            "template_name": self.template_name,
            "created_at": self.created_at,
            "slide_count": self.slide_count,
            "layout_count": self.layout_count,
            "master_count": self.master_count,
            "theme_count": self.theme_count,
            "layouts": [asdict(x) for x in self.layouts],
            "prototypes": [asdict(x) for x in self.prototypes],
            "stats": dict(self.stats),
        }


class TemplateNormalizer:
    def normalize(self, template_id: str, template_name: str, template_path: Path) -> Dict[str, object]:
        archive = PptxArchive(template_path)
        entries = archive.list_entries()

        slide_files = sorted(
            list_matching(entries, r"^ppt/slides/slide\d+\.xml$"),
            key=slide_index_from_path,
        )
        layout_files = sorted(
            list_matching(entries, r"^ppt/slideLayouts/slideLayout\d+\.xml$"),
            key=layout_index_from_path,
        )
        master_files = list_matching(entries, r"^ppt/slideMasters/slideMaster\d+\.xml$")
        theme_files = list_matching(entries, r"^ppt/theme/theme\d+\.xml$")

        layouts: List[LayoutSpec] = []
        layout_lookup: Dict[str, LayoutSpec] = {}

        for lf in layout_files:
            xml_text = archive.read_text(lf)
            root = ET.fromstring(xml_text)
            csld = root.find("p:cSld", NS)
            name = csld.attrib.get("name", "") if csld is not None else ""
            layout_type = root.attrib.get("type", "")
            placeholder_count = len(re.findall(r"<p:ph\b", xml_text))
            spec = LayoutSpec(
                path=lf,
                name=name,
                layout_type=layout_type,
                placeholder_count=placeholder_count,
            )
            layouts.append(spec)
            layout_lookup[lf] = spec

        prototypes: List[SlidePrototype] = []
        slide_text_nodes_total = 0
        slide_image_refs_total = 0

        for sf in slide_files:
            rel_path = f"ppt/slides/_rels/{Path(sf).name}.rels"
            layout_path = ""
            image_count = 0

            if archive.has(rel_path):
                rel_root = archive.read_xml(rel_path)
                for rel in rel_root.findall("pr:Relationship", NS):
                    rel_type = rel.attrib.get("Type", "")
                    target = rel.attrib.get("Target", "")
                    if rel_type.endswith("/slideLayout"):
                        layout_path = normalize_target(rel_path, target)
                    elif rel_type.endswith("/image"):
                        image_count += 1

            slide_xml = archive.read_text(sf)
            slide_root = ET.fromstring(slide_xml)
            text_nodes = [el.text or "" for el in slide_root.findall(".//a:t", NS)]
            slide_text_nodes_total += len(text_nodes)
            slide_image_refs_total += image_count

            joined_text = " ".join([t.strip() for t in text_nodes if t and t.strip()])
            text_preview = joined_text[:140]

            prototype = SlidePrototype(
                index=slide_index_from_path(sf),
                path=sf,
                layout_path=layout_path,
                text_preview=text_preview,
                shape_count=len(re.findall(r"<p:sp>", slide_xml)),
                image_count=image_count,
                text_slots=self._extract_text_slots(slide_root, slide_index_from_path(sf)),
            )
            prototypes.append(prototype)

        spec = TemplateSpec(
            template_id=template_id,
            template_name=template_name,
            created_at=datetime.now(timezone.utc).isoformat(),
            slide_count=len(slide_files),
            layout_count=len(layout_files),
            master_count=len(master_files),
            theme_count=len(theme_files),
            layouts=layouts,
            prototypes=sorted(prototypes, key=lambda x: x.index),
            stats={
                "text_nodes_total": slide_text_nodes_total,
                "image_refs_total": slide_image_refs_total,
            },
        )

        return spec.to_dict()

    def _extract_text_slots(self, slide_root: ET.Element, slide_index: int) -> List[Dict[str, object]]:
        slots: List[Dict[str, object]] = []
        shaped: List[tuple[int, int, int, int, Dict[str, object]]] = []

        for shape_order, sp in enumerate(slide_root.findall(".//p:sp", NS), start=1):
            y, x, cx, cy = self._shape_geometry(sp)
            placeholder_type = self._placeholder_type(sp)
            shape_name = self._shape_name(sp)

            for para_order, para in enumerate(sp.findall("./p:txBody/a:p", NS), start=1):
                texts = [node.text or "" for node in para.findall(".//a:t", NS)]
                text = " ".join([t.strip() for t in texts if t and t.strip()]).strip()
                if not text and para.find(".//a:r", NS) is None and not placeholder_type:
                    continue
                slot = {
                    "slot_id": f"s{shape_order}_{para_order}",
                    "shape_name": shape_name,
                    "text": text,
                    "role_hint": self._slot_role_hint(
                        slide_index=slide_index,
                        text=text,
                        placeholder_type=placeholder_type,
                        shape_y=y,
                        shape_cy=cy,
                    ),
                    "placeholder_type": placeholder_type,
                    "x": x,
                    "y": y,
                    "cx": cx,
                    "cy": cy,
                    "font_size_pt": self._paragraph_font_size_pt(para),
                    "font_face": self._paragraph_font_face(para),
                    "bold": self._paragraph_bool_attr(para, "b"),
                    "italic": self._paragraph_bool_attr(para, "i"),
                    "alignment": self._paragraph_alignment(para),
                }
                shaped.append((y, x, cy, cx, slot))

        for _, _, _, _, slot in sorted(shaped, key=lambda item: (item[0], item[1], item[2], item[3])):
            slots.append(slot)
        return slots

    @staticmethod
    def _shape_geometry(sp: ET.Element) -> tuple[int, int, int, int]:
        off = sp.find("./p:spPr/a:xfrm/a:off", NS)
        ext = sp.find("./p:spPr/a:xfrm/a:ext", NS)
        return (
            TemplateNormalizer._to_int(off.attrib.get("y") if off is not None else None),
            TemplateNormalizer._to_int(off.attrib.get("x") if off is not None else None),
            TemplateNormalizer._to_int(ext.attrib.get("cx") if ext is not None else None, fallback=0),
            TemplateNormalizer._to_int(ext.attrib.get("cy") if ext is not None else None, fallback=0),
        )

    @staticmethod
    def _shape_name(sp: ET.Element) -> str:
        c_nv_pr = sp.find("./p:nvSpPr/p:cNvPr", NS)
        if c_nv_pr is None:
            return ""
        return str(c_nv_pr.attrib.get("name", "")).strip()

    @staticmethod
    def _placeholder_type(sp: ET.Element) -> str:
        ph = sp.find("./p:nvSpPr/p:nvPr/p:ph", NS)
        if ph is None:
            return ""
        return str(ph.attrib.get("type", "")).strip().lower()

    @staticmethod
    def _slot_role_hint(slide_index: int, text: str, placeholder_type: str, shape_y: int, shape_cy: int) -> str:
        compact = re.sub(r"\s+", "", text or "")
        ph = (placeholder_type or "").lower()
        if ph in {"title", "ctrtitle"}:
            if slide_index == 1:
                return "cover_title"
            return "page_title"
        if ph == "subtitle":
            return "subtitle"
        if any(token in compact for token in ("汇报人", "报告人", "日期", "时间", "单位")):
            return "meta"
        if compact in {"目录", "contents", "CONTENT"}:
            return "toc_title"
        if shape_y < 1200000 and shape_cy <= 900000:
            return "page_title"
        return "body"

    @staticmethod
    def _paragraph_font_size_pt(para: ET.Element) -> float | int | None:
        sizes = []
        for rpr in para.findall(".//a:rPr", NS):
            raw = rpr.attrib.get("sz")
            if not raw:
                continue
            try:
                sizes.append(int(raw) / 100)
            except ValueError:
                continue
        if not sizes:
            return None
        value = max(sizes)
        return int(value) if float(value).is_integer() else value

    @staticmethod
    def _paragraph_font_face(para: ET.Element) -> str:
        for tag in ("a:ea", "a:latin", "a:cs"):
            for node in para.findall(f".//{tag}", NS):
                face = str(node.attrib.get("typeface", "")).strip()
                if face:
                    return face
        return ""

    @staticmethod
    def _paragraph_bool_attr(para: ET.Element, attr: str) -> bool:
        for rpr in para.findall(".//a:rPr", NS):
            raw = str(rpr.attrib.get(attr, "")).strip().lower()
            if raw in {"1", "true", "on"}:
                return True
        return False

    @staticmethod
    def _paragraph_alignment(para: ET.Element) -> str:
        ppr = para.find("./a:pPr", NS)
        if ppr is None:
            return ""
        return str(ppr.attrib.get("algn", "")).strip().lower()

    @staticmethod
    def _to_int(raw: str | None, fallback: int = 10**9) -> int:
        if not raw:
            return fallback
        try:
            return int(raw)
        except ValueError:
            return fallback
