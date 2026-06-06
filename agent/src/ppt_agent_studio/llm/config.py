from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, repr=False)
class OpenAICompatibleConfig:
    base_url: str
    api_key: str
    model: str

    @property
    def has_api_key(self) -> bool:
        return bool(self.api_key.strip())

    @classmethod
    def from_env(cls, env_file: str | os.PathLike[str] | None = None) -> "OpenAICompatibleConfig":
        file_values = _read_env_file(env_file if env_file is not None else os.getenv("PPT_AGENT_ENV_FILE", ".env.local"))
        return cls(
            base_url=_config_value("OPENAI_BASE_URL", "https://api.openai.com/v1", file_values).strip().rstrip("/"),
            api_key=_config_value("OPENAI_API_KEY", "", file_values).strip(),
            model=_config_value("OPENAI_MODEL", "gpt-4.1-mini", file_values).strip(),
        )

    def __repr__(self) -> str:
        return (
            "OpenAICompatibleConfig("
            f"base_url={self.base_url!r}, "
            f"model={self.model!r}, "
            f"has_api_key={self.has_api_key!r})"
        )

    def safe_summary(self) -> dict[str, object]:
        return {
            "base_url": self.base_url,
            "model": self.model,
            "has_api_key": self.has_api_key,
        }


def _config_value(name: str, default: str, file_values: dict[str, str]) -> str:
    value = os.environ.get(name)
    if value is not None:
        return value
    return file_values.get(name, default)


def _read_env_file(env_file: str | os.PathLike[str] | None) -> dict[str, str]:
    if env_file is None:
        return {}
    path = Path(env_file)
    if not path.exists():
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
