from pathlib import Path


def test_architecture_documents_preview_ready_theme_name():
    architecture = _repo_root().joinpath("docs", "architecture.md").read_text(encoding="utf-8")

    assert "`preview.ready`" in architecture
    assert "`theme_name`" in architecture


def test_architecture_documents_pptx_ready_theme_name():
    architecture = _repo_root().joinpath("docs", "architecture.md").read_text(encoding="utf-8")

    assert "`pptx.ready` payload includes the exported PowerPoint `path`, `deck_title`, `slide_count`, and `theme_name`" in architecture


def test_architecture_documents_runtime_config_requires_api_key():
    architecture = _repo_root().joinpath("docs", "architecture.md").read_text(encoding="utf-8")

    assert "`runtime.config`" in architecture
    assert "`requires_api_key`" in architecture


def test_architecture_documents_deck_scoped_plan_events():
    architecture = _repo_root().joinpath("docs", "architecture.md").read_text(encoding="utf-8")

    assert "`plan.updated` events include `deck_id`" in architecture
    assert "treats `plan.updated`, `deck.updated`, `tool.completed`, `preview.ready`, and `pptx.ready` as deck-scoped" in architecture


def test_architecture_documents_failed_follow_up_plan_events():
    architecture = _repo_root().joinpath("docs", "architecture.md").read_text(encoding="utf-8")

    assert "invalid numbered follow-up targets emit a failed `plan.updated`" in architecture
    assert "agent turn failures emit a failed `plan.updated`" in architecture
    assert "`failure_message`" in architecture


def test_architecture_documents_settings_env_folder_action():
    architecture = _repo_root().joinpath("docs", "architecture.md").read_text(encoding="utf-8")

    assert "Open Env Folder" in architecture


def test_architecture_documents_settings_env_file_template_action():
    architecture = _repo_root().joinpath("docs", "architecture.md").read_text(encoding="utf-8")

    assert "Create Env File" in architecture
    assert "does not overwrite" in architecture


def test_architecture_documents_stable_preview_slide_ids():
    architecture = _repo_root().joinpath("docs", "architecture.md").read_text(encoding="utf-8")

    assert "stable `data-slide-id`" in architecture
    assert "`showSlideById`" in architecture


def test_architecture_documents_expanded_deck_tool_registry():
    architecture = _repo_root().joinpath("docs", "architecture.md").read_text(encoding="utf-8")

    assert "deck title updates" in architecture
    assert "slide update/add/move/remove tools" in architecture
    assert "tool arguments are JSON-object-shaped" in architecture
    assert "declared top-level JSON types" in architecture
    assert "Add/create follow-ups can also send new slides to the beginning or end" in architecture
    assert "Duplicate follow-ups can insert copied slides before or after first/last, ordinal, or numbered slide targets" in architecture
    assert "Duplicate follow-ups can also send copied slides to the beginning or end" in architecture


def test_architecture_documents_dict_message_content():
    architecture = _repo_root().joinpath("docs", "architecture.md").read_text(encoding="utf-8")

    assert "dictionary-shaped message content" in architecture


def test_architecture_documents_choice_fallback_parsing():
    architecture = _repo_root().joinpath("docs", "architecture.md").read_text(encoding="utf-8")

    assert "first non-blank choice with usable text" in architecture


def _repo_root() -> Path:
    directory = Path(__file__).resolve()
    while directory != directory.parent:
        if directory.joinpath("docs", "architecture.md").exists():
            return directory
        directory = directory.parent
    raise FileNotFoundError("docs/architecture.md was not found")
