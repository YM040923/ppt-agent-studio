from __future__ import annotations

import cgi
import json
import mimetypes
from email.utils import encode_rfc2231
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Tuple
from urllib.parse import parse_qs, urlparse

from .service import GenerationService


def json_response(handler: BaseHTTPRequestHandler, status: int, payload: Dict[str, Any]) -> None:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(data)))
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(data)


def content_disposition_value(filename: str) -> str:
    fallback = "".join(ch if 32 <= ord(ch) < 127 and ch not in {'"', "\\", ";"} else "_" for ch in filename)
    fallback = fallback or "download.pptx"
    encoded = encode_rfc2231(filename, "UTF-8")
    return f'attachment; filename="{fallback}"; filename*={encoded}'


class AppHandler(BaseHTTPRequestHandler):
    service: GenerationService = None  # type: ignore[assignment]
    static_dir: Path = Path()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/health":
            json_response(self, HTTPStatus.OK, {"ok": True})
            return

        if path == "/api/templates":
            json_response(self, HTTPStatus.OK, self.service.list_templates())
            return

        if path == "/api/template":
            query = parse_qs(parsed.query)
            template_id = (query.get("id") or [""])[0]
            if not template_id:
                json_response(self, HTTPStatus.BAD_REQUEST, {"error": "Missing template id"})
                return
            template = self.service.get_template(template_id)
            if not template:
                json_response(self, HTTPStatus.NOT_FOUND, {"error": "Template not found"})
                return
            json_response(self, HTTPStatus.OK, template)
            return

        if path == "/api/template/export":
            query = parse_qs(parsed.query)
            template_id = (query.get("id") or [""])[0]
            if not template_id:
                json_response(self, HTTPStatus.BAD_REQUEST, {"error": "Missing template id"})
                return
            try:
                template = self.service.get_template(template_id)
                if not template:
                    json_response(self, HTTPStatus.NOT_FOUND, {"error": "Template not found"})
                    return
                output_path = self.service.export_standardized_template(template_id)
            except ValueError as exc:
                json_response(self, HTTPStatus.NOT_FOUND, {"error": str(exc)})
                return
            stem = Path(str(template.get("template_name") or "template.pptx")).stem or "template"
            self._serve_file(output_path, force_download_name=f"{stem}-standardized-preview.pptx")
            return

        if path == "/api/settings":
            json_response(self, HTTPStatus.OK, self.service.get_runtime_settings())
            return

        if path == "/api/ai/check":
            json_response(self, HTTPStatus.OK, self.service.check_ai_connection())
            return

        if path == "/api/project":
            query = parse_qs(parsed.query)
            project_id = (query.get("id") or [""])[0]
            if not project_id:
                json_response(self, HTTPStatus.BAD_REQUEST, {"error": "Missing project id"})
                return
            project = self.service.get_project(project_id)
            if not project:
                json_response(self, HTTPStatus.NOT_FOUND, {"error": "Project not found"})
                return
            json_response(self, HTTPStatus.OK, project)
            return

        if path == "/api/download":
            query = parse_qs(parsed.query)
            project_id = (query.get("id") or [""])[0]
            if not project_id:
                json_response(self, HTTPStatus.BAD_REQUEST, {"error": "Missing project id"})
                return
            project = self.service.get_project(project_id)
            if not project:
                json_response(self, HTTPStatus.NOT_FOUND, {"error": "Project not found"})
                return
            output_path = Path(str(project.get("output_pptx_path") or ""))
            if not output_path.exists():
                json_response(self, HTTPStatus.NOT_FOUND, {"error": "Output file not found"})
                return
            self._serve_file(output_path, force_download_name=f"{project['topic']}.pptx")
            return

        self._serve_static(path)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/templates":
            self._handle_upload_template()
            return

        if path == "/api/projects":
            self._handle_create_project()
            return

        if path == "/api/settings":
            self._handle_update_settings()
            return

        if path == "/api/plan":
            self._handle_plan_project()
            return

        if path == "/api/generate":
            self._handle_generate_project()
            return

        if path == "/api/confirm-plan":
            self._handle_confirm_plan()
            return

        json_response(self, HTTPStatus.NOT_FOUND, {"error": "Route not found"})

    def do_DELETE(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/template":
            query = parse_qs(parsed.query)
            template_id = (query.get("id") or [""])[0]
            if not template_id:
                json_response(self, HTTPStatus.BAD_REQUEST, {"error": "Missing template id"})
                return
            if self.service.delete_template(template_id):
                json_response(self, HTTPStatus.OK, {"ok": True})
                return
            json_response(self, HTTPStatus.NOT_FOUND, {"error": "Template not found"})
            return

        json_response(self, HTTPStatus.NOT_FOUND, {"error": "Route not found"})

    def _handle_upload_template(self) -> None:
        content_type = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in content_type:
            json_response(self, HTTPStatus.BAD_REQUEST, {"error": "Content-Type must be multipart/form-data"})
            return

        env = {
            "REQUEST_METHOD": "POST",
            "CONTENT_TYPE": content_type,
            "CONTENT_LENGTH": self.headers.get("Content-Length", "0"),
        }
        form = cgi.FieldStorage(fp=self.rfile, headers=self.headers, environ=env)
        file_item = form["file"] if "file" in form else None
        if file_item is None or getattr(file_item, "file", None) is None:
            json_response(self, HTTPStatus.BAD_REQUEST, {"error": "Missing file field"})
            return

        filename = file_item.filename or "template.pptx"
        data = file_item.file.read()
        if not data:
            json_response(self, HTTPStatus.BAD_REQUEST, {"error": "Empty file"})
            return

        try:
            result = self.service.upload_template(filename, data)
        except Exception as exc:  # noqa: BLE001
            json_response(self, HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc)})
            return

        json_response(self, HTTPStatus.OK, result)

    def _handle_create_project(self) -> None:
        payload, err = self._read_json()
        if err:
            json_response(self, HTTPStatus.BAD_REQUEST, {"error": err})
            return
        try:
            project = self.service.create_project(
                topic=str(payload.get("topic", "")).strip(),
                template_id=str(payload.get("template_id", "")).strip(),
                slide_count=int(payload.get("slide_count", 10)),
                audience=str(payload.get("audience", "")).strip(),
                tone=str(payload.get("tone", "")).strip(),
            )
        except ValueError as exc:
            json_response(self, HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return
        except Exception as exc:  # noqa: BLE001
            json_response(self, HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc)})
            return

        json_response(self, HTTPStatus.OK, project)

    def _handle_update_settings(self) -> None:
        payload, err = self._read_json()
        if err:
            json_response(self, HTTPStatus.BAD_REQUEST, {"error": err})
            return
        try:
            out = self.service.update_runtime_settings(payload)
        except Exception as exc:  # noqa: BLE001
            json_response(self, HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc)})
            return
        json_response(self, HTTPStatus.OK, out)

    def _handle_plan_project(self) -> None:
        payload, err = self._read_json()
        if err:
            json_response(self, HTTPStatus.BAD_REQUEST, {"error": err})
            return

        project_id = str(payload.get("project_id", "")).strip()
        if not project_id:
            json_response(self, HTTPStatus.BAD_REQUEST, {"error": "Missing project_id"})
            return

        message = str(payload.get("message", "")).strip()
        try:
            out = self.service.plan_project(
                project_id=project_id,
                message=message,
                allow_without_ai=bool(payload.get("allow_without_ai")),
            )
        except ValueError as exc:
            json_response(self, HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return
        except Exception as exc:  # noqa: BLE001
            json_response(self, HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc)})
            return
        json_response(self, HTTPStatus.OK, out)

    def _handle_generate_project(self) -> None:
        payload, err = self._read_json()
        if err:
            json_response(self, HTTPStatus.BAD_REQUEST, {"error": err})
            return

        project_id = str(payload.get("project_id", "")).strip()
        if not project_id:
            json_response(self, HTTPStatus.BAD_REQUEST, {"error": "Missing project_id"})
            return

        try:
            project = self.service.generate_project(project_id)
        except ValueError as exc:
            json_response(self, HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return
        except Exception as exc:  # noqa: BLE001
            json_response(self, HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc)})
            return

        json_response(self, HTTPStatus.OK, project)

    def _handle_confirm_plan(self) -> None:
        payload, err = self._read_json()
        if err:
            json_response(self, HTTPStatus.BAD_REQUEST, {"error": err})
            return

        project_id = str(payload.get("project_id", "")).strip()
        if not project_id:
            json_response(self, HTTPStatus.BAD_REQUEST, {"error": "Missing project_id"})
            return

        try:
            project = self.service.confirm_project_plan(project_id)
        except ValueError as exc:
            json_response(self, HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return
        except Exception as exc:  # noqa: BLE001
            json_response(self, HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc)})
            return

        json_response(self, HTTPStatus.OK, project)

    def _read_json(self) -> Tuple[Dict[str, Any], str]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return {}, "Invalid Content-Length"
        raw = self.rfile.read(length)
        if not raw:
            return {}, "Empty body"
        try:
            return json.loads(raw.decode("utf-8")), ""
        except json.JSONDecodeError:
            return {}, "Invalid JSON"

    def _serve_static(self, path: str) -> None:
        rel = "index.html" if path in ("/", "") else path.lstrip("/")
        file_path = self.static_dir / rel
        if not file_path.exists() or not file_path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND, "Not Found")
            return
        self._serve_file(file_path)

    def _serve_file(self, file_path: Path, force_download_name: str = "") -> None:
        content = file_path.read_bytes()
        content_type, _ = mimetypes.guess_type(file_path.name)
        content_type = content_type or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        if force_download_name:
            self.send_header("Content-Disposition", content_disposition_value(force_download_name))
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, format: str, *args: Any) -> None:
        # Keep server output clean for local agent logs.
        return


def build_server(host: str, port: int, service: GenerationService, static_dir: Path) -> ThreadingHTTPServer:
    AppHandler.service = service
    AppHandler.static_dir = static_dir
    return ThreadingHTTPServer((host, port), AppHandler)
