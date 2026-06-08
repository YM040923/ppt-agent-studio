from pathlib import Path


def test_contributing_documents_core_local_checks():
    contributing = _repo_root().joinpath("CONTRIBUTING.md").read_text(encoding="utf-8")

    assert "python -m pytest agent\\tests -q" in contributing
    assert "dotnet test desktop\\PptAgentStudio.App.Tests\\PptAgentStudio.App.Tests.csproj" in contributing
    assert ".\\scripts\\verify.ps1" in contributing
    assert "python -m ppt_agent_studio.runtime.demo" in contributing
    assert ".env.local" in contributing


def _repo_root() -> Path:
    directory = Path(__file__).resolve()
    while directory != directory.parent:
        if directory.joinpath("README.md").exists():
            return directory
        directory = directory.parent
    raise FileNotFoundError("repository root was not found")
