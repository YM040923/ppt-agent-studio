from __future__ import annotations

from pathlib import Path

from .config import Settings
from .http_server import build_server
from .service import GenerationService


def main() -> None:
    settings = Settings.from_env()
    service = GenerationService(settings)
    static_dir = Path(__file__).resolve().parent / "static"

    server = build_server(settings.host, settings.port, service, static_dir)
    print(f"PPT Agent MVP running at http://{settings.host}:{settings.port}")
    print(f"Data dir: {settings.data_dir}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
