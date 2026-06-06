from ppt_agent_studio.llm.config import OpenAICompatibleConfig


def test_openai_compatible_config_reads_third_party_endpoint(monkeypatch):
    monkeypatch.setenv("OPENAI_BASE_URL", "https://provider.example/v1/")
    monkeypatch.setenv("OPENAI_API_KEY", "secret-value")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-compatible-model")

    config = OpenAICompatibleConfig.from_env()

    assert config.base_url == "https://provider.example/v1"
    assert config.model == "gpt-compatible-model"
    assert config.has_api_key is True


def test_openai_compatible_config_reads_env_file_when_env_is_missing(monkeypatch, tmp_path):
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    env_file = tmp_path / ".env.local"
    env_file.write_text(
        "\n".join(
            [
                "OPENAI_BASE_URL=https://file-provider.example/v1/",
                "OPENAI_API_KEY=file-secret-value",
                "OPENAI_MODEL=file-compatible-model",
            ]
        ),
        encoding="utf-8",
    )

    config = OpenAICompatibleConfig.from_env(env_file=env_file)

    assert config.base_url == "https://file-provider.example/v1"
    assert config.model == "file-compatible-model"
    assert config.has_api_key is True


def test_openai_compatible_config_prefers_env_over_env_file(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_BASE_URL", "https://env-provider.example/v1")
    monkeypatch.setenv("OPENAI_API_KEY", "env-secret-value")
    monkeypatch.setenv("OPENAI_MODEL", "env-compatible-model")
    env_file = tmp_path / ".env.local"
    env_file.write_text(
        "\n".join(
            [
                "OPENAI_BASE_URL=https://file-provider.example/v1",
                "OPENAI_API_KEY=file-secret-value",
                "OPENAI_MODEL=file-compatible-model",
            ]
        ),
        encoding="utf-8",
    )

    config = OpenAICompatibleConfig.from_env(env_file=env_file)

    assert config.base_url == "https://env-provider.example/v1"
    assert config.model == "env-compatible-model"
    assert config.has_api_key is True


def test_openai_compatible_config_redacts_key():
    config = OpenAICompatibleConfig(
        base_url="https://provider.example/v1",
        api_key="secret-value",
        model="gpt-compatible-model",
    )

    assert "secret-value" not in repr(config)
    assert config.safe_summary()["has_api_key"] is True
