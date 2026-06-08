from pathlib import Path


def test_verify_script_runs_core_local_checks():
    script_path = _repo_root().joinpath("scripts", "verify.ps1")

    assert script_path.exists()

    script = script_path.read_text(encoding="utf-8")

    assert "$env:PYTHONPATH" in script
    assert "agent\\src" in script
    assert "python -m pytest agent\\tests -q" in script
    assert "python -m ppt_agent_studio.runtime.demo" in script
    assert "--artifact-dir artifacts\\verify-demo" in script
    assert '--follow-up "Add a risk mitigation slide"' in script
    assert "dotnet test desktop\\PptAgentStudio.App.Tests\\PptAgentStudio.App.Tests.csproj" in script
    assert "dotnet build desktop\\PptAgentStudio.App\\PptAgentStudio.App.csproj" in script
    assert "dotnet run --project" in script
    assert "startup-smoke: process stayed alive for 8 seconds" in script


def _repo_root() -> Path:
    directory = Path(__file__).resolve()
    while directory != directory.parent:
        if directory.joinpath("README.md").exists():
            return directory
        directory = directory.parent
    raise FileNotFoundError("README.md was not found")
