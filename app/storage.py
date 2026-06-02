from __future__ import annotations

import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional
from uuid import uuid4


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class Storage:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.templates_dir = data_dir / "templates"
        self.projects_dir = data_dir / "projects"
        self.settings_path = data_dir / "settings.json"
        self.templates_dir.mkdir(parents=True, exist_ok=True)
        self.projects_dir.mkdir(parents=True, exist_ok=True)

    def create_template(self, template_name: str, content: bytes) -> Dict[str, object]:
        template_id = uuid4().hex
        folder = self.templates_dir / template_id
        folder.mkdir(parents=True, exist_ok=True)

        pptx_path = folder / "template.pptx"
        meta_path = folder / "template.json"

        with open(pptx_path, "wb") as f:
            f.write(content)

        meta = {
            "template_id": template_id,
            "template_name": template_name,
            "pptx_path": str(pptx_path),
            "created_at": _now_iso(),
        }
        self._write_json(meta_path, meta)
        return meta

    def save_template_spec(self, template_id: str, spec: Dict[str, object]) -> None:
        path = self.templates_dir / template_id / "spec.json"
        self._write_json(path, spec)

    def list_templates(self) -> List[Dict[str, object]]:
        out: List[Dict[str, object]] = []
        for child in sorted(self.templates_dir.iterdir()):
            if not child.is_dir():
                continue
            meta = self._read_json(child / "template.json")
            if not meta:
                continue
            spec = self._read_json(child / "spec.json") or {}
            out.append(
                {
                    **meta,
                    "slide_count": spec.get("slide_count"),
                    "layout_count": spec.get("layout_count"),
                    "master_count": spec.get("master_count"),
                }
            )
        return out

    def get_template(self, template_id: str) -> Optional[Dict[str, object]]:
        folder = self.templates_dir / template_id
        meta = self._read_json(folder / "template.json")
        if not meta:
            return None
        spec = self._read_json(folder / "spec.json") or {}
        meta["spec"] = spec
        return meta

    def delete_template(self, template_id: str) -> bool:
        if not re.fullmatch(r"[0-9a-fA-F]{32}", template_id or ""):
            return False
        folder = (self.templates_dir / template_id).resolve()
        templates_root = self.templates_dir.resolve()
        if templates_root not in folder.parents or not folder.exists() or not folder.is_dir():
            return False
        shutil.rmtree(folder)
        return True

    def create_project(
        self,
        topic: str,
        template_id: str,
        slide_count: int,
        audience: str = "",
        tone: str = "",
    ) -> Dict[str, object]:
        project_id = uuid4().hex
        folder = self.projects_dir / project_id
        folder.mkdir(parents=True, exist_ok=True)

        project = {
            "project_id": project_id,
            "topic": topic,
            "template_id": template_id,
            "slide_count": int(slide_count),
            "audience": audience,
            "tone": tone,
            "status": "created",
            "created_at": _now_iso(),
            "updated_at": _now_iso(),
            "output_pptx_path": "",
            "plan": None,
            "draft_plan": None,
            "outline_confirmed": False,
            "conversation": [],
            "lint_report": None,
            "render_report": None,
        }
        self._write_json(folder / "project.json", project)
        return project

    def update_project(self, project_id: str, patch: Dict[str, object]) -> Optional[Dict[str, object]]:
        path = self.projects_dir / project_id / "project.json"
        project = self._read_json(path)
        if not project:
            return None
        project.update(patch)
        project["updated_at"] = _now_iso()
        self._write_json(path, project)
        return project

    def get_project(self, project_id: str) -> Optional[Dict[str, object]]:
        return self._read_json(self.projects_dir / project_id / "project.json")

    def project_output_path(self, project_id: str) -> Path:
        return self.projects_dir / project_id / "generated.pptx"

    def get_runtime_settings(self, defaults: Dict[str, object]) -> Dict[str, object]:
        saved = self._read_json(self.settings_path) or {}
        merged = {
            "openai_api_key": str(saved.get("openai_api_key") or defaults.get("openai_api_key") or ""),
            "openai_base_url": str(saved.get("openai_base_url") or defaults.get("openai_base_url") or ""),
            "openai_model": str(saved.get("openai_model") or defaults.get("openai_model") or ""),
        }
        return merged

    def save_runtime_settings(self, settings: Dict[str, object]) -> Dict[str, object]:
        current = self._read_json(self.settings_path) or {}
        current.update(settings)
        self._write_json(self.settings_path, current)
        return current

    def _read_json(self, path: Path) -> Optional[Dict[str, object]]:
        if not path.exists():
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _write_json(self, path: Path, data: Dict[str, object]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
