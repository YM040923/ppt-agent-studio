from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    host: str
    port: int
    openai_api_key: str
    openai_base_url: str
    openai_model: str

    @staticmethod
    def from_env() -> "Settings":
        data_dir = Path(os.getenv("PPT_AGENT_DATA_DIR", "data")).resolve()
        host = os.getenv("PPT_AGENT_HOST", "127.0.0.1")
        port = int(os.getenv("PPT_AGENT_PORT", "8787"))
        openai_api_key = os.getenv("OPENAI_API_KEY", "").strip()
        openai_base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").strip()
        openai_model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini").strip()

        return Settings(
            data_dir=data_dir,
            host=host,
            port=port,
            openai_api_key=openai_api_key,
            openai_base_url=openai_base_url.rstrip("/"),
            openai_model=openai_model,
        )
