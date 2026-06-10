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
    assert '--follow-up "Create an executive summary slide at the beginning"' in script
    assert "dotnet test desktop\\PptAgentStudio.App.Tests\\PptAgentStudio.App.Tests.csproj" in script
    assert "dotnet build desktop\\PptAgentStudio.App\\PptAgentStudio.App.csproj" in script
    assert "dotnet run --project" in script
    assert "startup-smoke: process stayed alive for 8 seconds" in script


def test_stage_agent_runtime_downloads_wheels_for_embedded_python():
    script_path = _repo_root().joinpath("scripts", "stage-agent-runtime.ps1")

    assert script_path.exists()

    script = script_path.read_text(encoding="utf-8")

    assert "pip download" in script
    assert "--python-version" in script
    assert '$platformTag = "win_$Architecture"' in script
    assert "--platform $platformTag" in script
    assert 'Copy-Item -LiteralPath $wheel.FullName -Destination $wheelZip' in script
    assert "Expand-Archive -Path $wheelZip" in script
    assert "Rename-Item" in script
    assert '".pyd"' in script
    assert "PYTHONDONTWRITEBYTECODE" in script
    assert "__pycache__" in script
    assert "*.pyc" in script
    assert "*.dist-info" in script
    assert "bootstrap.pypa.io" not in script


def test_staged_agent_runtime_smoke_uses_embedded_python():
    script_path = _repo_root().joinpath("scripts", "test-staged-agent-runtime.ps1")

    assert script_path.exists()

    script = script_path.read_text(encoding="utf-8")

    assert "AgentRuntime" in script
    assert "python\\python.exe" in script
    assert "handle_client_message" in script
    assert "runtime.config" in script
    assert "staged-runtime-smoke: runtime.config ok" in script
    assert "New-TemporaryFile" in script
    assert "Set-Content -LiteralPath" in script
    assert '-c "' not in script


def _repo_root() -> Path:
    directory = Path(__file__).resolve()
    while directory != directory.parent:
        if directory.joinpath("README.md").exists():
            return directory
        directory = directory.parent
    raise FileNotFoundError("README.md was not found")
