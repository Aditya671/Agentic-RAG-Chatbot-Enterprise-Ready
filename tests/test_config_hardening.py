from pathlib import Path

import pytest

from agentic_rag_chatbot_enterprise_ready.backend.config.config import (
    CloudProvider,
    Config,
    ConfigurationError,
)


def _config(tmp_path: Path, payload: str, monkeypatch) -> Config:
    path = tmp_path / "config.yml"
    path.write_text(payload, encoding="utf-8")
    monkeypatch.delenv("AZURE_KEY_VAULT_URL", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "production")
    config = Config(path)
    assert config.cloud_provider is CloudProvider.AZURE
    return config


def test_production_requires_key_vault_url(tmp_path, monkeypatch):
    config = _config(
        tmp_path,
        "indexes: {aiim: {}}\nllms: {aoai: {}}\ncloud: {provider: azure}\n",
        monkeypatch,
    )
    with pytest.raises(ConfigurationError, match="key_vault.url"):
        config.validate_runtime_config()


def test_production_requires_nonempty_index_mapping(tmp_path, monkeypatch):
    config = _config(
        tmp_path,
        "indexes: {}\nllms: {aoai: {}}\ncloud: {provider: azure}\nazure: {key_vault: {url: 'https://vault.example'}}\n",
        monkeypatch,
    )
    with pytest.raises(ConfigurationError, match="indexes"):
        config.validate_runtime_config()


def test_production_rejects_malformed_index_entries(tmp_path, monkeypatch):
    config = _config(
        tmp_path,
        "indexes:\n  aiim: []\nllms:\n  aoai: {deployment-name: 'chat'}\ncloud: {provider: azure}\nazure:\n  key_vault:\n    url: 'https://vault.example'\n",
        monkeypatch,
    )
    with pytest.raises(ConfigurationError, match="index 'aiim'"):
        config.validate_runtime_config()


def test_production_rejects_missing_llm_mapping(tmp_path, monkeypatch):
    config = _config(
        tmp_path,
        "indexes:\n  aiim: {storage_account: {container_name: uploads}}\nllms: {}\ncloud: {provider: azure}\nazure:\n  key_vault:\n    url: 'https://vault.example'\n",
        monkeypatch,
    )
    with pytest.raises(ConfigurationError, match="llms"):
        config.validate_runtime_config()
