from pathlib import Path


def test_env_example_does_not_contain_machine_specific_paths():
    text = _repo_root().joinpath(".env.example").read_text(encoding="utf-8")

    assert "E:\\MyProjects" not in text
    assert "C:\\Users" not in text


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


def _repo_root() -> Path:
    directory = Path(__file__).resolve()
    while directory != directory.parent:
        if directory.joinpath(".env.example").exists():
            return directory
        directory = directory.parent
    raise FileNotFoundError(".env.example was not found")
