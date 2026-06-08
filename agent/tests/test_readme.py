from pathlib import Path


def test_readme_documents_zipped_msix_ci_artifact():
    readme = _repo_root().joinpath("README.md").read_text(encoding="utf-8")

    assert "uploads a zipped AppPackages artifact" in readme
    assert "ppt-agent-studio-msix.zip" in readme


def test_readme_documents_demo_summary_json():
    readme = _repo_root().joinpath("README.md").read_text(encoding="utf-8")

    assert "summary JSON" in readme
    assert "demo-deck-r2-summary.json" in readme


def test_readme_documents_theme_follow_up():
    readme = _repo_root().joinpath("README.md").read_text(encoding="utf-8")

    assert "Follow-up add/update/remove slide and dark-theme requests" in readme
    assert "design.apply_theme" in readme


def test_readme_documents_verify_script():
    readme = _repo_root().joinpath("README.md").read_text(encoding="utf-8")

    assert ".\\scripts\\verify.ps1" in readme


def test_readme_documents_local_endpoint_classification():
    readme = _repo_root().joinpath("README.md").read_text(encoding="utf-8")

    assert "private-network IPs" in readme
    assert "`.local`" in readme


def _repo_root() -> Path:
    directory = Path(__file__).resolve()
    while directory != directory.parent:
        if directory.joinpath("README.md").exists():
            return directory
        directory = directory.parent
    raise FileNotFoundError("README.md was not found")
