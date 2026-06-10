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


def test_msix_package_smoke_checks_bundled_runtime_contents():
    script_path = _repo_root().joinpath("scripts", "test-msix-package.ps1")

    assert script_path.exists()

    script = script_path.read_text(encoding="utf-8")

    assert "System.IO.Compression.ZipFile" in script
    assert "AgentRuntime/python/python.exe" in script
    assert "AgentRuntime/python/Lib/site-packages/httpx/" in script
    assert "AgentRuntime/python/Lib/site-packages/pptx/" in script
    assert "AgentRuntime/python/Lib/site-packages/websockets/" in script
    assert "AgentRuntime/agent/src/ppt_agent_studio/runtime/websocket_server.py" in script
    assert "__pycache__" in script
    assert "*.pyc" in script
    assert "*.dist-info" in script
    assert "cp313" in script
    assert "cpython" in script
    assert "msix-package-smoke: bundled runtime contents ok" in script


def test_sign_msix_package_creates_matching_test_certificate_and_verifies_signature():
    script_path = _repo_root().joinpath("scripts", "sign-msix-package.ps1")

    assert script_path.exists()

    script = script_path.read_text(encoding="utf-8")

    assert "Package.appxmanifest" in script
    assert "Publisher" in script
    assert "New-SelfSignedCertificate" in script
    assert "Export-Certificate" in script
    assert "TrustCertificate" in script
    assert "Import-Certificate" in script
    assert "Cert:\\CurrentUser\\Root" in script
    assert "signtool.exe" in script
    assert "sign /fd SHA256" in script
    assert "/a" not in script
    assert "verify /pa" in script
    assert "msix-signing: signed package ok" in script
    assert "PFX" not in script


def _repo_root() -> Path:
    directory = Path(__file__).resolve()
    while directory != directory.parent:
        if directory.joinpath("README.md").exists():
            return directory
        directory = directory.parent
    raise FileNotFoundError("README.md was not found")
