import sys
import types

# The regression suite is dependency-isolated: the production package is not
# required just to exercise the manager's control flow.
azure = types.ModuleType("azure")
azure_core = types.ModuleType("azure.core")
azure_exceptions = types.ModuleType("azure.core.exceptions")

class AzureError(Exception):
    pass

class ResourceNotFoundError(AzureError):
    pass

azure_exceptions.AzureError = AzureError
azure_exceptions.ResourceNotFoundError = ResourceNotFoundError
azure_core.exceptions = azure_exceptions

azure_identity = types.ModuleType("azure.identity")

class AzureCliCredential:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
    def close(self):
        pass

class DefaultAzureCredential:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
    def close(self):
        pass

azure_identity.AzureCliCredential = AzureCliCredential
azure_identity.DefaultAzureCredential = DefaultAzureCredential

azure_kv = types.ModuleType("azure.keyvault")
azure_kv_secrets = types.ModuleType("azure.keyvault.secrets")

class SecretClient:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

azure_kv_secrets.SecretClient = SecretClient
azure_kv.secrets = azure_kv_secrets
azure.keyvault = azure_kv

sys.modules.update({
    "azure": azure,
    "azure.core": azure_core,
    "azure.core.exceptions": azure_exceptions,
    "azure.identity": azure_identity,
    "azure.keyvault": azure_kv,
    "azure.keyvault.secrets": azure_kv_secrets,
})

import importlib.util
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest


MODULE_PATH = Path("/mnt/data/azure_credential_manager_upgraded.py")
spec = importlib.util.spec_from_file_location("azure_credential_manager_under_test", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

AzureCredentialManager = module.AzureCredentialManager
SecretNotFoundError = module.SecretNotFoundError


class FakeSecretClient:
    def __init__(self, value="secret-value", error=None):
        self.value = value
        self.error = error
        self.calls = []

    def get_secret(self, name):
        self.calls.append(name)
        if self.error:
            raise self.error
        return SimpleNamespace(value=self.value)

    def close(self):
        self.closed = True


def manager(client=None, **kwargs):
    return AzureCredentialManager(
        key_vault_url="https://example.vault.azure.net",
        credential=Mock(),
        secret_client=client or FakeSecretClient(),
        **kwargs,
    )


def test_environment_secret_takes_precedence(monkeypatch):
    monkeypatch.setenv("MY_SECRET", "from-env")
    client = FakeSecretClient("from-key-vault")
    m = manager(client)

    assert m.get_secret("MY_SECRET") == "from-env"
    assert client.calls == []


def test_environment_override_can_be_disabled(monkeypatch):
    monkeypatch.setenv("MY_SECRET", "from-env")
    client = FakeSecretClient("from-key-vault")
    m = manager(client, allow_environment_override=False)

    assert m.get_secret("MY-SECRET") == "from-key-vault"
    assert client.calls == ["MY-SECRET"]


def test_key_vault_secret_is_retrieved():
    client = FakeSecretClient("vault-secret")
    m = manager(client)

    assert m.get_secret("MY-SECRET") == "vault-secret"
    assert client.calls == ["MY-SECRET"]


def test_secret_cache_avoids_repeated_key_vault_calls():
    client = FakeSecretClient("vault-secret")
    m = manager(client, cache_ttl_seconds=300)

    assert m.get_secret("MY-SECRET") == "vault-secret"
    assert m.get_secret("MY-SECRET") == "vault-secret"
    assert client.calls == ["MY-SECRET"]


def test_clear_cache_forces_next_key_vault_request():
    client = FakeSecretClient("vault-secret")
    m = manager(client, cache_ttl_seconds=300)

    m.get_secret("MY-SECRET")
    m.clear_secret_cache("MY-SECRET")
    m.get_secret("MY-SECRET")

    assert client.calls == ["MY-SECRET", "MY-SECRET"]


def test_expired_cache_is_refreshed(monkeypatch):
    client = FakeSecretClient("vault-secret")
    m = manager(client, cache_ttl_seconds=1)

    m.get_secret("MY-SECRET")

    # Make monotonic time jump past expiry.
    with patch.object(module.time, "monotonic", side_effect=[100.0, 102.0, 102.0]):
        m._cache["MY-SECRET"] = module._CachedSecret("old", 99.0)
        assert m.get_secret("MY-SECRET") == "vault-secret"

    assert client.calls == ["MY-SECRET", "MY-SECRET"]


def test_optional_missing_secret_returns_none():
    client = FakeSecretClient(error=module.ResourceNotFoundError("missing"))
    m = manager(client)

    assert m.get_secret("MY-SECRET", required=False) is None


def test_required_missing_secret_raises_domain_error():
    client = FakeSecretClient(error=module.ResourceNotFoundError("missing"))
    m = manager(client)

    with pytest.raises(SecretNotFoundError, match="MY-SECRET"):
        m.get_secret("MY-SECRET")


def test_invalid_secret_name_is_rejected_before_network():
    client = FakeSecretClient()
    m = manager(client)

    with pytest.raises(ValueError):
        m.get_secret("bad/name")

    assert client.calls == []


@pytest.mark.parametrize("url", [None, "", "   "])
def test_empty_key_vault_url_means_no_client(url):
    with patch.object(module.AzureCredentialManager, "get_credential", return_value=Mock()):
        m = AzureCredentialManager(
            key_vault_url=url,
            credential=Mock(),
        )
    assert m.client is None


def test_invalid_key_vault_url_is_rejected():
    with pytest.raises(ValueError):
        AzureCredentialManager(
            key_vault_url="http://example.vault.azure.net",
            credential=Mock(),
        )


def test_local_default_compatibility_uses_cli_credential():
    with patch("azure_credential_manager_under_test.AzureCliCredential") as cli:
        credential = AzureCredentialManager.get_credential(
            environment="local",
            use_cli_for_local=True,
        )
        cli.assert_called_once_with(additionally_allowed_tenants=["*"])


def test_local_can_use_default_azure_credential():
    with patch("azure_credential_manager_under_test.DefaultAzureCredential") as default:
        AzureCredentialManager.get_credential(
            environment="local",
            use_cli_for_local=False,
        )
        default.assert_called_once_with()


def test_cloud_uses_default_azure_credential():
    with patch("azure_credential_manager_under_test.DefaultAzureCredential") as default:
        AzureCredentialManager.get_credential(environment="production")
        default.assert_called_once_with()


def test_custom_credential_is_not_replaced():
    credential = Mock()
    client = FakeSecretClient()
    m = AzureCredentialManager(
        key_vault_url="https://example.vault.azure.net",
        credential=credential,
        secret_client=client,
    )

    assert m.credential is credential


def test_close_closes_supported_resources():
    credential = Mock()
    client = FakeSecretClient()
    m = AzureCredentialManager(
        key_vault_url="https://example.vault.azure.net",
        credential=credential,
        secret_client=client,
    )

    m.close()

    client.close.assert_not_called() if isinstance(client.close, Mock) else None
    assert getattr(client, "closed", False) is True
    credential.close.assert_called_once()


def test_missing_key_vault_without_environment_secret():
    m = AzureCredentialManager(
        key_vault_url=None,
        credential=Mock(),
    )

    with pytest.raises(SecretNotFoundError):
        m.get_secret("MY-SECRET")


def test_optional_missing_key_vault_secret_returns_none():
    m = AzureCredentialManager(
        key_vault_url=None,
        credential=Mock(),
    )

    assert m.get_secret("MY-SECRET", required=False) is None


def test_cache_can_be_disabled_per_call():
    client = FakeSecretClient("vault-secret")
    m = manager(client, cache_ttl_seconds=300)

    assert m.get_secret("MY-SECRET", cache=False) == "vault-secret"
    assert m.get_secret("MY-SECRET", cache=False) == "vault-secret"
    assert client.calls == ["MY-SECRET", "MY-SECRET"]


def test_cache_ttl_must_be_non_negative():
    with pytest.raises(ValueError):
        manager(cache_ttl_seconds=-1)
