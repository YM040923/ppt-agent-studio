from __future__ import annotations

import posixpath
import re
import zipfile
from pathlib import Path
from typing import Dict, Iterable, List
from xml.etree import ElementTree as ET


P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"

NS = {
    "p": P_NS,
    "a": A_NS,
    "r": R_NS,
    "pr": PKG_REL_NS,
}


def slide_index_from_path(path: str) -> int:
    match = re.search(r"slide(\d+)\.xml$", path)
    if not match:
        return 10**9
    return int(match.group(1))


def layout_index_from_path(path: str) -> int:
    match = re.search(r"slideLayout(\d+)\.xml$", path)
    if not match:
        return 10**9
    return int(match.group(1))


def normalize_target(base_path: str, target: str) -> str:
    base_dir = posixpath.dirname(base_path)
    joined = posixpath.normpath(posixpath.join(base_dir, target))
    return joined.lstrip("./")


def list_matching(entries: Iterable[str], pattern: str) -> List[str]:
    regex = re.compile(pattern)
    return [e for e in entries if regex.match(e)]


class PptxArchive:
    """In-memory PPTX container to support read-modify-write."""

    def __init__(self, path: Path):
        self.path = path
        self.entries: Dict[str, bytes] = {}
        with zipfile.ZipFile(path, "r") as zf:
            for info in zf.infolist():
                self.entries[info.filename] = zf.read(info.filename)

    def list_entries(self) -> List[str]:
        return sorted(self.entries.keys())

    def has(self, entry: str) -> bool:
        return entry in self.entries

    def read_text(self, entry: str) -> str:
        return self.entries[entry].decode("utf-8")

    def write_text(self, entry: str, content: str) -> None:
        self.entries[entry] = content.encode("utf-8")

    def read_xml(self, entry: str) -> ET.Element:
        return ET.fromstring(self.entries[entry])

    def write_xml(self, entry: str, root: ET.Element) -> None:
        xml_bytes = ET.tostring(root, encoding="utf-8", xml_declaration=True)
        self.entries[entry] = xml_bytes

    def save(self, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for name, content in self.entries.items():
                zf.writestr(name, content)
