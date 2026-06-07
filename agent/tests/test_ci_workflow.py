from pathlib import Path


def test_ci_runs_offline_demo_smoke():
    workflow = _repo_root().joinpath(".github", "workflows", "ci.yml").read_text(encoding="utf-8")

    assert "ppt_agent_studio.runtime.demo" in workflow
    assert "--artifact-dir artifacts\\ci-demo" in workflow
    assert "ppt-agent-studio-demo" in workflow
    assert "artifacts/ci-demo/**" in workflow
    assert "if-no-files-found: error" in workflow


def _repo_root() -> Path:
    directory = Path(__file__).resolve()
    while directory != directory.parent:
        if directory.joinpath(".github", "workflows", "ci.yml").exists():
            return directory
        directory = directory.parent
    raise FileNotFoundError("ci.yml was not found")
