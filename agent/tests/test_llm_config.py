import pytest
from pathlib import Path

from ppt_agent_studio.llm.config import OpenAICompatibleConfig


def test_openai_compatible_config_reads_third_party_endpoint(monkeypatch):
    monkeypatch.setenv("OPENAI_BASE_URL", "https://provider.example/v1/")
    monkeypatch.setenv("OPENAI_API_KEY", "secret-value")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-compatible-model")
    monkeypatch.setenv("OPENAI_EXTRA_HEADERS", '{"X-Provider": "tenant-001", "X-Trace": "deck"}')

    config = OpenAICompatibleConfig.from_env()

    assert config.base_url == "https://provider.example/v1"
    assert config.model == "gpt-compatible-model"
    assert config.has_api_key is True
    assert config.extra_headers == {"X-Provider": "tenant-001", "X-Trace": "deck"}
    assert config.safe_summary()["endpoint_kind"] == "cloud"
    assert config.safe_summary()["requires_api_key"] is True


@pytest.mark.parametrize(
    "base_url",
    [
        "http://localhost:1234/v1",
        "http://127.0.0.1:11434/v1",
        "http://[::1]:8000/v1",
    ],
)
def test_openai_compatible_config_marks_loopback_endpoints_as_local(monkeypatch, base_url):
    monkeypatch.setenv("OPENAI_BASE_URL", base_url)

    config = OpenAICompatibleConfig.from_env()

    assert config.safe_summary()["endpoint_kind"] == "local"
    assert config.safe_summary()["requires_api_key"] is False


@pytest.mark.parametrize(
    "base_url",
    [
        "http://192.168.1.25:11434/v1",
        "http://10.0.0.12:1234/v1",
        "http://169.254.10.20:8000/v1",
        "http://[fd00::1]:8000/v1",
        "http://modelbox.local:8000/v1",
    ],
)
def test_openai_compatible_config_marks_local_network_endpoints_as_local(monkeypatch, base_url):
    monkeypatch.setenv("OPENAI_BASE_URL", base_url)

    config = OpenAICompatibleConfig.from_env()

    assert config.safe_summary()["endpoint_kind"] == "local"


def test_openai_compatible_config_reads_env_file_when_env_is_missing(monkeypatch, tmp_path):
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_EXTRA_HEADERS", raising=False)
    env_file = tmp_path / ".env.local"
    env_file.write_text(
        "\n".join(
            [
                "OPENAI_BASE_URL=https://file-provider.example/v1/",
                "OPENAI_API_KEY=file-secret-value",
                "OPENAI_MODEL=file-compatible-model",
                "OPENAI_EXTRA_HEADERS={\"X-Provider\":\"file-tenant\"}",
            ]
        ),
        encoding="utf-8",
    )

    config = OpenAICompatibleConfig.from_env(env_file=env_file)

    assert config.base_url == "https://file-provider.example/v1"
    assert config.model == "file-compatible-model"
    assert config.has_api_key is True
    assert config.extra_headers == {"X-Provider": "file-tenant"}
    assert config.safe_summary()["source"] == {
        "base_url": "env_file",
        "api_key": "env_file",
        "model": "env_file",
        "extra_headers": "env_file",
    }


def test_openai_compatible_config_reads_export_prefixed_env_file_values(monkeypatch, tmp_path):
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    env_file = tmp_path / ".env.local"
    env_file.write_text(
        "\n".join(
            [
                "export OPENAI_BASE_URL=https://export-provider.example/v1",
                "export OPENAI_API_KEY=export-secret-value",
                "export OPENAI_MODEL=export-compatible-model",
            ]
        ),
        encoding="utf-8",
    )

    config = OpenAICompatibleConfig.from_env(env_file=env_file)

    assert config.base_url == "https://export-provider.example/v1"
    assert config.model == "export-compatible-model"
    assert config.has_api_key is True
    assert config.safe_summary()["source"] == {
        "base_url": "env_file",
        "api_key": "env_file",
        "model": "env_file",
        "extra_headers": "default",
    }
    assert "export-secret-value" not in str(config.safe_summary())


def test_openai_compatible_config_expands_user_env_file_path(monkeypatch, tmp_path):
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    env_file = home / ".ppt-agent.env"
    env_file.parent.mkdir(parents=True, exist_ok=True)
    env_file.write_text(
        "\n".join(
            [
                "OPENAI_BASE_URL=https://home-provider.example/v1",
                "OPENAI_API_KEY=home-secret-value",
                "OPENAI_MODEL=home-compatible-model",
            ]
        ),
        encoding="utf-8",
    )

    config = OpenAICompatibleConfig.from_env(env_file=Path("~") / ".ppt-agent.env")

    assert config.base_url == "https://home-provider.example/v1"
    assert config.model == "home-compatible-model"
    assert config.has_api_key is True
    assert config.safe_summary()["source"]["base_url"] == "env_file"
    assert "home-secret-value" not in str(config.safe_summary())


def test_openai_compatible_config_ignores_blank_env_file_path(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PPT_AGENT_ENV_FILE", "")
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)

    config = OpenAICompatibleConfig.from_env()

    assert config.base_url == "https://api.openai.com/v1"
    assert config.model == "gpt-4.1-mini"
    assert config.safe_summary()["source"]["base_url"] == "default"


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
    assert config.safe_summary()["source"] == {
        "base_url": "environment",
        "api_key": "environment",
        "model": "environment",
        "extra_headers": "default",
    }


def test_openai_compatible_config_ignores_blank_env_values(monkeypatch):
    monkeypatch.setenv("OPENAI_BASE_URL", "   ")
    monkeypatch.setenv("OPENAI_MODEL", "")

    config = OpenAICompatibleConfig.from_env()

    assert config.base_url == "https://api.openai.com/v1"
    assert config.model == "gpt-4.1-mini"
    assert config.safe_summary()["source"]["base_url"] == "default"
    assert config.safe_summary()["source"]["model"] == "default"


def test_openai_compatible_config_ignores_blank_env_file_values(monkeypatch, tmp_path):
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    env_file = tmp_path / ".env.local"
    env_file.write_text(
        "\n".join(
            [
                "OPENAI_BASE_URL=   ",
                "OPENAI_MODEL=",
            ]
        ),
        encoding="utf-8",
    )

    config = OpenAICompatibleConfig.from_env(env_file=env_file)

    assert config.base_url == "https://api.openai.com/v1"
    assert config.model == "gpt-4.1-mini"
    assert config.safe_summary()["source"]["base_url"] == "default"
    assert config.safe_summary()["source"]["model"] == "default"


def test_openai_compatible_config_redacts_key():
    config = OpenAICompatibleConfig(
        base_url="https://provider.example/v1",
        api_key="secret-value",
        model="gpt-compatible-model",
        extra_headers={"X-Provider": "secret-tenant"},
    )

    assert "secret-value" not in repr(config)
    assert "secret-tenant" not in repr(config)
    assert config.safe_summary()["has_api_key"] is True
    assert config.safe_summary()["has_extra_headers"] is True
    assert "secret-tenant" not in str(config.safe_summary())


def test_openai_compatible_config_treats_example_placeholder_key_as_missing(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "replace-with-your-api-key")

    config = OpenAICompatibleConfig.from_env()

    assert config.api_key == ""
    assert config.has_api_key is False
    assert config.safe_summary()["has_api_key"] is False
    assert config.safe_summary()["source"]["api_key"] == "default"


def test_openai_compatible_config_treats_env_file_placeholder_key_as_missing(monkeypatch, tmp_path):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    env_file = tmp_path / ".env.local"
    env_file.write_text("OPENAI_API_KEY=your-secret-key", encoding="utf-8")

    config = OpenAICompatibleConfig.from_env(env_file=env_file)

    assert config.api_key == ""
    assert config.has_api_key is False
    assert config.safe_summary()["has_api_key"] is False
    assert config.safe_summary()["source"]["api_key"] == "default"


def test_openai_compatible_config_rejects_invalid_extra_headers_without_value(monkeypatch):
    monkeypatch.setenv("OPENAI_EXTRA_HEADERS", "secret-tenant")

    with pytest.raises(ValueError, match="OPENAI_EXTRA_HEADERS must be a JSON object") as error:
        OpenAICompatibleConfig.from_env()

    assert "secret-tenant" not in str(error.value)
