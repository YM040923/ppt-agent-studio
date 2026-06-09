from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from ipaddress import ip_address, ip_network
from pathlib import Path
from urllib.parse import urlparse


LOCAL_MODEL_NETWORKS = tuple(
    ip_network(cidr)
    for cidr in (
        "10.0.0.0/8",
        "172.16.0.0/12",
        "192.168.0.0/16",
        "fc00::/7",
    )
)


@dataclass(frozen=True, repr=False)
class OpenAICompatibleConfig:
    base_url: str
    api_key: str
    model: str
    extra_headers: dict[str, str] = field(default_factory=dict)
    source: dict[str, str] = field(default_factory=dict)

    @property
    def has_api_key(self) -> bool:
        return bool(self.api_key.strip())

    @property
    def requires_api_key(self) -> bool:
        return self.endpoint_kind != "local"

    @property
    def endpoint_kind(self) -> str:
        parsed = urlparse(self.base_url)
        host = (parsed.hostname or "").strip().lower()
        if host == "localhost" or host.endswith(".local"):
            return "local"
        try:
            address = ip_address(host)
        except ValueError:
            return "cloud"
        is_local_network = any(address in network for network in LOCAL_MODEL_NETWORKS)
        return "local" if address.is_loopback or address.is_link_local or is_local_network else "cloud"

    @classmethod
    def from_env(cls, env_file: str | os.PathLike[str] | None = None) -> "OpenAICompatibleConfig":
        file_values = _read_env_file(_env_file_path(env_file))
        return cls(
            base_url=_config_value("OPENAI_BASE_URL", "https://api.openai.com/v1", file_values).strip().rstrip("/"),
            api_key=_api_key_from_config(_config_value("OPENAI_API_KEY", "", file_values)),
            model=_config_value("OPENAI_MODEL", "gpt-4.1-mini", file_values).strip(),
            extra_headers=_extra_headers_from_config(_config_value("OPENAI_EXTRA_HEADERS", "", file_values)),
            source={
                "base_url": _config_source("OPENAI_BASE_URL", file_values),
                "api_key": _config_source("OPENAI_API_KEY", file_values),
                "model": _config_source("OPENAI_MODEL", file_values),
                "extra_headers": _config_source("OPENAI_EXTRA_HEADERS", file_values),
            },
        )

    def __repr__(self) -> str:
        return (
            "OpenAICompatibleConfig("
            f"base_url={self.base_url!r}, "
            f"model={self.model!r}, "
            f"has_api_key={self.has_api_key!r}, "
            f"has_extra_headers={bool(self.extra_headers)!r})"
        )

    def safe_summary(self) -> dict[str, object]:
        return {
            "base_url": self.base_url,
            "model": self.model,
            "has_api_key": self.has_api_key,
            "has_extra_headers": bool(self.extra_headers),
            "endpoint_kind": self.endpoint_kind,
            "requires_api_key": self.requires_api_key,
            "source": {
                "base_url": self.source.get("base_url", "default"),
                "api_key": self.source.get("api_key", "default"),
                "model": self.source.get("model", "default"),
                "extra_headers": self.source.get("extra_headers", "default"),
            },
        }


def _config_value(name: str, default: str, file_values: dict[str, str]) -> str:
    value = os.environ.get(name)
    if value is not None and _is_configured_value(name, value):
        return value
    file_value = file_values.get(name)
    if file_value is not None and _is_configured_value(name, file_value):
        return file_value
    return default


def _config_source(name: str, file_values: dict[str, str]) -> str:
    value = os.environ.get(name)
    if value is not None and _is_configured_value(name, value):
        return "environment"
    file_value = file_values.get(name)
    if file_value is not None and _is_configured_value(name, file_value):
        return "env_file"
    return "default"


def _api_key_from_config(value: str) -> str:
    key = value.strip()
    if _is_placeholder_api_key(key):
        return ""
    return key


def _is_configured_value(name: str, value: str) -> bool:
    stripped = value.strip()
    if not stripped:
        return False
    return name != "OPENAI_API_KEY" or not _is_placeholder_api_key(stripped)


def _is_placeholder_api_key(value: str) -> bool:
    return value.casefold() in {"replace-with-your-api-key", "your-secret-key", "your-api-key"}


def _env_file_path(env_file: str | os.PathLike[str] | None) -> str | os.PathLike[str]:
    if env_file is not None and str(env_file).strip():
        return env_file
    value = os.getenv("PPT_AGENT_ENV_FILE")
    return value if value is not None and value.strip() else ".env.local"


def _read_env_file(env_file: str | os.PathLike[str] | None) -> dict[str, str]:
    if env_file is None:
        return {}
    path = Path(env_file).expanduser()
    if not path.is_file():
        return {}

    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        name, value = stripped.split("=", 1)
        name = name.strip()
        if not name:
            continue
        values[name] = _strip_env_value(value.strip())
    return values


def _strip_env_value(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _extra_headers_from_config(value: str) -> dict[str, str]:
    if not value.strip():
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as error:
        raise ValueError("OPENAI_EXTRA_HEADERS must be a JSON object") from error
    if not isinstance(parsed, dict):
        raise ValueError("OPENAI_EXTRA_HEADERS must be a JSON object")

    headers: dict[str, str] = {}
    for raw_name, raw_value in parsed.items():
        name = str(raw_name).strip()
        if not name or not isinstance(raw_value, str):
            continue
        header_value = raw_value.strip()
        if header_value:
            headers[name] = header_value
    return headers
