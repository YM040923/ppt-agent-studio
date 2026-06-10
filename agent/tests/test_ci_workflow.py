from pathlib import Path


def test_ci_runs_offline_demo_smoke():
    workflow = _repo_root().joinpath(".github", "workflows", "ci.yml").read_text(encoding="utf-8")

    assert "ppt_agent_studio.runtime.demo" in workflow
    assert "--artifact-dir artifacts\\ci-demo" in workflow
    assert "--follow-up" in workflow
    assert "Create an executive summary slide at the beginning" in workflow
    assert "ppt-agent-studio-demo" in workflow
    assert "artifacts/ci-demo/**" in workflow
    assert "if-no-files-found: error" in workflow


def test_ci_avoids_duplicate_pr_branch_push_runs():
    workflow = _repo_root().joinpath(".github", "workflows", "ci.yml").read_text(encoding="utf-8")

    assert "pull_request:" in workflow
    assert "push:\n    branches: [main]" in workflow


def test_ci_packages_and_uploads_unsigned_msix():
    workflow = _repo_root().joinpath(".github", "workflows", "ci.yml").read_text(encoding="utf-8")

    assert "Stage bundled runtime" in workflow
    assert ".\\scripts\\stage-agent-runtime.ps1" in workflow
    assert "Package unsigned MSIX" in workflow
    assert "-p:GenerateAppxPackageOnBuild=true" in workflow
    assert "-p:AppxPackageSigningEnabled=false" in workflow
    assert "-p:UapAppxPackageBuildMode=SideloadOnly" in workflow
    assert "Archive unsigned MSIX package" in workflow
    assert "Compress-Archive" in workflow
    assert "artifacts/msix/ppt-agent-studio-msix.zip" in workflow
    assert "ppt-agent-studio-msix" in workflow
    assert "artifacts/msix/ppt-agent-studio-msix.zip" in workflow


def _repo_root() -> Path:
    directory = Path(__file__).resolve()
    while directory != directory.parent:
        if directory.joinpath(".github", "workflows", "ci.yml").exists():
            return directory
        directory = directory.parent
    raise FileNotFoundError("ci.yml was not found")
