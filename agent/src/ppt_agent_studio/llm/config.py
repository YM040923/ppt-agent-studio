from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True, repr=False)
class OpenAICompatibleConfig:
    base_url: str
    api_key: str
    model: str

    @property
    def has_api_key(self) -> bool:
        return bool(self.api_key.strip())

    @classmethod
    def from_env(cls) -> "OpenAICompatibleConfig":
        return cls(
            base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").strip().rstrip("/"),
            api_key=os.getenv("OPENAI_API_KEY", "").strip(),
            model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini").strip(),
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
