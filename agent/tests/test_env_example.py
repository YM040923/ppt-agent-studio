from pathlib import Path


def test_env_example_does_not_contain_machine_specific_paths():
    text = _repo_root().joinpath(".env.example").read_text(encoding="utf-8")

    assert "E:\\MyProjects" not in text
    assert "C:\\Users" not in text


def test_env_example_documents_cloud_and_local_model_profiles():
    text = _repo_root().joinpath(".env.example").read_text(encoding="utf-8")

    assert "# Cloud OpenAI-compatible example:" in text
    assert "# OPENAI_BASE_URL=https://api.openai.com/v1" in text
    assert "# Local model server examples:" in text
    assert "# OPENAI_BASE_URL=http://127.0.0.1:11434/v1" in text
    assert "# OPENAI_BASE_URL=http://modelbox.local:8000/v1" in text
    assert "sk-" not in text


def test_public_docs_do_not_contain_machine_specific_paths():
    root = _repo_root()
    docs = [
        root.joinpath("README.md"),
        *root.joinpath("docs").glob("*.md"),
    ]

    for path in docs:
        text = path.read_text(encoding="utf-8")
        assert "E:\\MyProjects" not in text
        assert "C:\\Users" not in text


def test_gitignore_protects_local_secrets_and_generated_artifacts():
    patterns = {
        line.strip()
        for line in _repo_root().joinpath(".gitignore").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    }

    assert ".env.local" in patterns
    assert ".env" in patterns
    assert "artifacts/" in patterns
    assert "*.pptx" in patterns
    assert "bin/" in patterns
    assert "obj/" in patterns


def _repo_root() -> Path:
    directory = Path(__file__).resolve()
    while directory != directory.parent:
        if directory.joinpath(".env.example").exists():
            return directory
        directory = directory.parent
    raise FileNotFoundError(".env.example was not found")
