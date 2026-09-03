from pathlib import Path

from agentic_rag_chatbot_enterprise_ready.backend.config.config import Config


MINIMAL_CONFIG = """
indexes:
  aiim:
    embed:
      model: test-embedding
      size: 1536
    key_vault:
      url: https://example.vault.azure.net
    llms:
      aoai:
        endpoint-east-us-2: https://example.openai.azure.com
        api-version-east-us-2: 2025-01-01
"""


def test_config_loads_index_profile(tmp_path: Path):
    config_path = tmp_path / "config.yml"
    config_path.write_text(MINIMAL_CONFIG, encoding="utf-8")

    loaded = Config(config_path=str(config_path))
    index = loaded.indexes["aiim"]

    assert index.embed["model"] == "test-embedding"
    assert index.embed["size"] == 1536
    assert index.key_vault["url"].endswith(".vault.azure.net")


def test_missing_config_is_empty_but_deterministic(tmp_path: Path):
    loaded = Config(config_path=str(tmp_path / "missing.yml"))

    assert loaded.indexes == {}
    assert loaded.llms == {}
