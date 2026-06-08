from pathlib import Path


def test_readme_documents_zipped_msix_ci_artifact():
    readme = _repo_root().joinpath("README.md").read_text(encoding="utf-8")

    assert "uploads a zipped AppPackages artifact" in readme
    assert "ppt-agent-studio-msix.zip" in readme


def test_readme_documents_demo_summary_json():
    readme = _repo_root().joinpath("README.md").read_text(encoding="utf-8")

    assert "summary JSON" in readme
    assert "demo-deck-r2-summary.json" in readme
    assert "deck_title" in readme
    assert "theme_name" in readme
    assert "summary_json_path" in readme


def test_readme_documents_theme_follow_up():
    readme = _repo_root().joinpath("README.md").read_text(encoding="utf-8")

    assert "Follow-up add/create/update/remove slide and dark/light-theme requests" in readme
    assert "light/clean theme requests" in readme
    assert "`Make it darker`" in readme
    assert "`Make it brighter`" in readme
    assert "design.apply_theme" in readme


def test_readme_documents_verify_script():
    readme = _repo_root().joinpath("README.md").read_text(encoding="utf-8")

    assert ".\\scripts\\verify.ps1" in readme
    assert "offline demo smoke" in readme
    assert "artifacts\\verify-demo" in readme


def test_readme_documents_local_endpoint_classification():
    readme = _repo_root().joinpath("README.md").read_text(encoding="utf-8")

    assert "private-network IPs" in readme
    assert "`.local`" in readme


def test_readme_documents_local_llm_without_api_key():
    readme = _repo_root().joinpath("README.md").read_text(encoding="utf-8")

    assert "Local endpoints can run the LLM planner without an API key" in readme


def test_readme_documents_settings_env_folder_action():
    readme = _repo_root().joinpath("README.md").read_text(encoding="utf-8")

    assert "Open Env Folder" in readme


def test_readme_documents_settings_env_file_template_action():
    readme = _repo_root().joinpath("README.md").read_text(encoding="utf-8")

    assert "Create Env File" in readme
    assert "does not overwrite" in readme


def _repo_root() -> Path:
    directory = Path(__file__).resolve()
    while directory != directory.parent:
        if directory.joinpath("README.md").exists():
            return directory
        directory = directory.parent
    raise FileNotFoundError("README.md was not found")
