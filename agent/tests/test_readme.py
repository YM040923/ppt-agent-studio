from pathlib import Path


def test_readme_documents_zipped_msix_ci_artifact():
    readme = _repo_root().joinpath("README.md").read_text(encoding="utf-8")

    assert "uploads a zipped AppPackages artifact" in readme
    assert "ppt-agent-studio-msix.zip" in readme


def _repo_root() -> Path:
    directory = Path(__file__).resolve()
    while directory != directory.parent:
        if directory.joinpath("README.md").exists():
            return directory
        directory = directory.parent
    raise FileNotFoundError("README.md was not found")
