from pathlib import Path


def test_architecture_documents_preview_ready_theme_name():
    architecture = _repo_root().joinpath("docs", "architecture.md").read_text(encoding="utf-8")

    assert "`preview.ready`" in architecture
    assert "`theme_name`" in architecture


def _repo_root() -> Path:
    directory = Path(__file__).resolve()
    while directory != directory.parent:
        if directory.joinpath("docs", "architecture.md").exists():
            return directory
        directory = directory.parent
    raise FileNotFoundError("docs/architecture.md was not found")
