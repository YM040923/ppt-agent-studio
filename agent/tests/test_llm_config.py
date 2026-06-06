from ppt_agent_studio.llm.config import OpenAICompatibleConfig


def test_openai_compatible_config_reads_third_party_endpoint(monkeypatch):
    monkeypatch.setenv("OPENAI_BASE_URL", "https://provider.example/v1/")
    monkeypatch.setenv("OPENAI_API_KEY", "secret-value")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-compatible-model")

    config = OpenAICompatibleConfig.from_env()

    assert config.base_url == "https://provider.example/v1"
    assert config.model == "gpt-compatible-model"
    assert config.has_api_key is True


def test_openai_compatible_config_redacts_key():
    config = OpenAICompatibleConfig(
        base_url="https://provider.example/v1",
        api_key="secret-value",
        model="gpt-compatible-model",
    )

    assert "secret-value" not in repr(config)
    assert config.safe_summary()["has_api_key"] is True
