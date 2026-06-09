from pathlib import Path


def test_readme_documents_zipped_msix_ci_artifact():
    readme = _repo_root().joinpath("README.md").read_text(encoding="utf-8")

    assert "uploads a zipped AppPackages artifact" in readme
    assert "ppt-agent-studio-msix.zip" in readme


def test_readme_documents_demo_summary_json():
    readme = _repo_root().joinpath("README.md").read_text(encoding="utf-8")

    assert "summary JSON" in readme
    assert "Markdown summary" in readme
    assert "Create an executive summary slide at the beginning" in readme
    assert "demo-deck-r2-summary.json" in readme
    assert "demo-deck-r2-summary.md" in readme
    assert "deck_title" in readme
    assert "theme_name" in readme
    assert "summary_json_path" in readme
    assert "summary_markdown_path" in readme
    assert "event type flow" in readme


def test_readme_documents_theme_follow_up():
    readme = _repo_root().joinpath("README.md").read_text(encoding="utf-8")

    assert "Follow-up add/create/update/rename/remove slide and dark/light-theme requests" in readme
    assert "Add/create follow-ups can insert before or after first/last, ordinal, or numbered slide targets" in readme
    assert "Add/create follow-ups can also send new slides to the beginning or end" in readme
    assert "Duplicate follow-ups copy first/last, ordinal, or numbered slide targets before or after a target" in readme
    assert "Duplicate follow-ups can also send copied slides to the beginning or end" in readme
    assert "Move follow-ups reposition slides before or after first/last, ordinal, or numbered targets" in readme
    assert "Move follow-ups can also send slides to the beginning or end" in readme
    assert "Deck rename follow-ups update the deck title" in readme
    assert "Audience/style follow-ups update deck metadata" in readme
    assert "Update/rename and remove follow-ups honor first/last, ordinal, and numbered slide targets" in readme
    assert "light/clean theme requests" in readme
    assert "`Make it darker`" in readme
    assert "`Make it brighter`" in readme
    assert "design.apply_theme" in readme


def test_readme_documents_verify_script():
    readme = _repo_root().joinpath("README.md").read_text(encoding="utf-8")

    assert ".\\scripts\\verify.ps1" in readme
    assert "offline demo smoke" in readme
    assert "artifacts\\verify-demo" in readme


def test_readme_documents_artifact_directory_expands_user_home():
    readme = _repo_root().joinpath("README.md").read_text(encoding="utf-8")

    assert "`PPT_AGENT_ARTIFACTS_DIR` may use `~`" in readme
    assert "expanded to the user profile" in readme


def test_readme_documents_env_file_expands_user_home():
    readme = _repo_root().joinpath("README.md").read_text(encoding="utf-8")

    assert "`PPT_AGENT_ENV_FILE` may also use `~`" in readme
    assert "expanded before the runtime reads configuration" in readme


def test_readme_documents_blank_runtime_paths_are_ignored():
    readme = _repo_root().joinpath("README.md").read_text(encoding="utf-8")

    assert "Blank `PPT_AGENT_ENV_FILE` and `PPT_AGENT_ARTIFACTS_DIR` values are treated as unset" in readme


def test_readme_documents_local_endpoint_classification():
    readme = _repo_root().joinpath("README.md").read_text(encoding="utf-8")

    assert "private-network IPs" in readme
    assert "`.local`" in readme


def test_readme_documents_local_llm_without_api_key():
    readme = _repo_root().joinpath("README.md").read_text(encoding="utf-8")

    assert "Local endpoints can run the LLM planner without an API key" in readme


def test_readme_documents_blank_model_config_values_are_ignored():
    readme = _repo_root().joinpath("README.md").read_text(encoding="utf-8")

    assert "Blank `OPENAI_BASE_URL`, `OPENAI_MODEL`, and `OPENAI_EXTRA_HEADERS` values are treated as unset" in readme


def test_readme_documents_placeholder_api_keys_are_ignored():
    readme = _repo_root().joinpath("README.md").read_text(encoding="utf-8")

    assert "Placeholder API keys from `.env.example` are also treated as unset" in readme


def test_readme_documents_export_prefixed_env_file_values():
    readme = _repo_root().joinpath("README.md").read_text(encoding="utf-8")

    assert "Lines may optionally start with `export `" in readme


def test_readme_documents_settings_env_folder_action():
    readme = _repo_root().joinpath("README.md").read_text(encoding="utf-8")

    assert "Open Env Folder" in readme


def test_readme_documents_settings_env_file_template_action():
    readme = _repo_root().joinpath("README.md").read_text(encoding="utf-8")

    assert "Create Env File" in readme
    assert "does not overwrite" in readme


def test_readme_documents_export_action_state_guards():
    readme = _repo_root().joinpath("README.md").read_text(encoding="utf-8")

    assert "only appears when `pptx.ready` includes a usable export path" in readme
    assert "clears stale export actions when a newer Agent turn or deck revision starts" in readme
    assert "clears the missing path if the exported file was moved or deleted" in readme


def _repo_root() -> Path:
    directory = Path(__file__).resolve()
    while directory != directory.parent:
        if directory.joinpath("README.md").exists():
            return directory
        directory = directory.parent
    raise FileNotFoundError("README.md was not found")
