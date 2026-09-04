import sys
import types
from unittest.mock import Mock

import pytest

boto3_module = types.ModuleType("boto3")
botocore_module = types.ModuleType("botocore")
botocore_config_module = types.ModuleType("botocore.config")
botocore_exceptions_module = types.ModuleType("botocore.exceptions")


class FakeCredentials:
    pass


class FakeBotoSession:
    def get_credentials(self):
        return FakeCredentials()

    def client(self, service_name, region_name, config):
        return FakeSecretsClient()


class FakeSecretsClient:
    def __init__(self):
        self.responses = {}
        self.errors = {}

    def get_secret_value(self, SecretId):
        if SecretId in self.errors:
            raise self.errors[SecretId]
        return self.responses[SecretId]


class FakeConfig:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


class FakeClientError(Exception):
    def __init__(self, code, message="error"):
        self.response = {"Error": {"Code": code, "Message": message}}
        super().__init__(message)


boto3_module.session = types.SimpleNamespace(Session=FakeBotoSession)
botocore_config_module.Config = FakeConfig
botocore_exceptions_module.ClientError = FakeClientError
botocore_exceptions_module.NoCredentialsError = type("NoCredentialsError", (Exception,), {})
botocore_exceptions_module.PartialCredentialsError = type(
    "PartialCredentialsError", (Exception,), {}
)

sys.modules.setdefault("boto3", boto3_module)
sys.modules.setdefault("botocore", botocore_module)
sys.modules.setdefault("botocore.config", botocore_config_module)
sys.modules.setdefault("botocore.exceptions", botocore_exceptions_module)

from agentic_rag_chatbot_enterprise_ready.backend.credentials.aws_credential_manager import (  # noqa: E402
    AWSCredentialError,
    AWSCredentialManager,
    AWSSecretError,
)


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    monkeypatch.delenv("MY_APP_SECRET", raising=False)
    monkeypatch.delenv("OTHER_SECRET", raising=False)


def make_manager(secret_name="MY_APP_SECRET", **kwargs):
    return AWSCredentialManager(secret_name=secret_name, **kwargs)


def test_default_region_is_preserved():
    assert make_manager().region_name == "us-east-1"


def test_invalid_configuration_is_rejected():
    with pytest.raises(ValueError):
        make_manager(secret_name="")
    with pytest.raises(ValueError):
        make_manager(region_name="")
    with pytest.raises(ValueError):
        make_manager(cache_ttl_seconds=-1)
    with pytest.raises(ValueError):
        make_manager(max_attempts=0)


def test_environment_secret_has_precedence(monkeypatch):
    monkeypatch.setenv("MY_APP_SECRET", "from-environment")
    manager = make_manager()
    manager.client = Mock()

    assert manager.get_secret() == "from-environment"
    manager.client.get_secret_value.assert_not_called()


def test_environment_only_manager_supports_explicit_secret(monkeypatch):
    monkeypatch.setenv("OTHER_SECRET", "other-value")
    manager = AWSCredentialManager()

    assert manager.get_secret("OTHER_SECRET") == "other-value"
    assert manager.client is None


def test_secret_string_and_binary_are_supported():
    manager = make_manager()
    manager.client = Mock()
    manager.client.get_secret_value.side_effect = [
        {"SecretString": "text"},
        {"SecretBinary": b"binary"},
    ]

    assert manager.get_secret() == "text"
    manager.clear_cache()
    assert manager.get_secret() == "binary"


def test_invalid_secret_payload_is_rejected():
    manager = make_manager()
    manager.client = Mock()
    manager.client.get_secret_value.return_value = {}

    with pytest.raises(AWSSecretError, match="neither"):
        manager.get_secret()


def test_resource_not_found_and_access_denied_are_normalized():
    manager = make_manager()
    manager.client = Mock()
    manager.client.get_secret_value.side_effect = FakeClientError(
        "ResourceNotFoundException"
    )

    with pytest.raises(AWSSecretError, match="not found"):
        manager.get_secret()

    manager.client.get_secret_value.side_effect = FakeClientError(
        "AccessDeniedException", "SECRET_VALUE_SHOULD_NOT_APPEAR"
    )
    with pytest.raises(AWSSecretError) as exc_info:
        manager.get_secret()
    assert "SECRET_VALUE_SHOULD_NOT_APPEAR" not in str(exc_info.value)


def test_get_session_requires_resolved_credentials(monkeypatch):
    class NoCredentialsSession(FakeBotoSession):
        def get_credentials(self):
            return None

    monkeypatch.setattr(boto3_module.session, "Session", NoCredentialsSession)
    with pytest.raises(AWSCredentialError, match="No valid AWS credentials"):
        AWSCredentialManager.get_session()


def test_client_configuration_is_explicit():
    captured = {}

    class RecordingSession(FakeBotoSession):
        def client(self, service_name, region_name, config):
            captured.update(
                service_name=service_name,
                region_name=region_name,
                config=config,
            )
            return FakeSecretsClient()

    original = boto3_module.session.Session
    boto3_module.session.Session = RecordingSession
    try:
        make_manager(
            region_name="ap-south-1",
            max_attempts=7,
            connect_timeout=11,
            read_timeout=44,
        )
    finally:
        boto3_module.session.Session = original

    assert captured["service_name"] == "secretsmanager"
    assert captured["region_name"] == "ap-south-1"
    assert captured["config"].kwargs["retries"] == {
        "mode": "standard",
        "max_attempts": 7,
    }
    assert captured["config"].kwargs["connect_timeout"] == 11
    assert captured["config"].kwargs["read_timeout"] == 44


def test_cache_is_opt_in_and_can_be_cleared():
    manager = make_manager(cache_ttl_seconds=60)
    manager.client = Mock()
    manager.client.get_secret_value.return_value = {"SecretString": "cached"}

    assert manager.get_secret() == "cached"
    assert manager.get_secret() == "cached"
    manager.client.get_secret_value.assert_called_once_with(
        SecretId="MY_APP_SECRET"
    )

    manager.clear_cache("MY_APP_SECRET")
    assert manager._secret_cache == {}


def test_cache_is_not_shared_between_instances():
    first = make_manager(cache_ttl_seconds=60)
    second = make_manager(cache_ttl_seconds=60)
    first.client = Mock()
    second.client = Mock()
    first.client.get_secret_value.return_value = {"SecretString": "one"}
    second.client.get_secret_value.return_value = {"SecretString": "two"}

    assert first.get_secret() == "one"
    assert second.get_secret() == "two"


def test_explicit_secret_name_overrides_constructor_name():
    manager = make_manager()
    manager.client = Mock()
    manager.client.get_secret_value.return_value = {"SecretString": "override"}

    assert manager.get_secret("OTHER_SECRET") == "override"
    manager.client.get_secret_value.assert_called_once_with(
        SecretId="OTHER_SECRET"
    )
