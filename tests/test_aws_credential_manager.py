from unittest.mock import Mock

import pytest

from agentic_rag_chatbot_enterprise_ready.backend.credentials import aws_credential_manager as module


class FakeCredentials:
    pass


class FakeSecretsClient:
    def __init__(self):
        self.responses = {}
        self.errors = {}

    def get_secret_value(self, SecretId):
        if SecretId in self.errors:
            raise self.errors[SecretId]
        return self.responses[SecretId]


class FakeBotoSession:
    def get_credentials(self):
        return FakeCredentials()

    def client(self, service_name, region_name, config):
        return FakeSecretsClient()


class FakeConfig:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


class FakeClientError(Exception):
    def __init__(self, code, message="error"):
        self.response = {"Error": {"Code": code, "Message": message}}
        super().__init__(message)


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    monkeypatch.delenv("MY_APP_SECRET", raising=False)
    monkeypatch.delenv("OTHER_SECRET", raising=False)


def make_manager(monkeypatch, secret_name="MY_APP_SECRET", **kwargs):
    monkeypatch.setattr(module.boto3.session, "Session", FakeBotoSession)
    monkeypatch.setattr(module, "Config", FakeConfig)
    return module.AWSCredentialManager(secret_name=secret_name, **kwargs)


def test_default_region_is_preserved(monkeypatch):
    assert make_manager(monkeypatch).region_name == "us-east-1"


def test_invalid_configuration_is_rejected(monkeypatch):
    with pytest.raises(ValueError):
        make_manager(monkeypatch, secret_name="")
    with pytest.raises(ValueError):
        make_manager(monkeypatch, region_name="")
    with pytest.raises(ValueError):
        make_manager(monkeypatch, cache_ttl_seconds=-1)
    with pytest.raises(ValueError):
        make_manager(monkeypatch, max_attempts=0)


def test_environment_secret_has_precedence(monkeypatch):
    monkeypatch.setenv("MY_APP_SECRET", "from-environment")
    manager = make_manager(monkeypatch)
    manager.client = Mock()

    assert manager.get_secret() == "from-environment"
    manager.client.get_secret_value.assert_not_called()


def test_environment_only_manager_supports_explicit_secret(monkeypatch):
    monkeypatch.setenv("OTHER_SECRET", "other-value")
    manager = module.AWSCredentialManager()

    assert manager.get_secret("OTHER_SECRET") == "other-value"
    assert manager.client is None


def test_secret_string_and_binary_are_supported(monkeypatch):
    manager = make_manager(monkeypatch)
    manager.client = Mock()
    manager.client.get_secret_value.side_effect = [
        {"SecretString": "text"},
        {"SecretBinary": b"binary"},
    ]

    assert manager.get_secret() == "text"
    manager.clear_cache()
    assert manager.get_secret() == "binary"


def test_invalid_secret_payload_is_rejected(monkeypatch):
    manager = make_manager(monkeypatch)
    manager.client = Mock()
    manager.client.get_secret_value.return_value = {}

    with pytest.raises(module.AWSSecretError, match="neither"):
        manager.get_secret()


def test_resource_not_found_and_access_denied_are_normalized(monkeypatch):
    manager = make_manager(monkeypatch)
    manager.client = Mock()
    manager.client.get_secret_value.side_effect = FakeClientError(
        "ResourceNotFoundException"
    )

    with pytest.raises(module.AWSSecretError, match="not found"):
        manager.get_secret()

    manager.client.get_secret_value.side_effect = FakeClientError(
        "AccessDeniedException", "SECRET_VALUE_SHOULD_NOT_APPEAR"
    )
    with pytest.raises(module.AWSSecretError) as exc_info:
        manager.get_secret()
    assert "SECRET_VALUE_SHOULD_NOT_APPEAR" not in str(exc_info.value)


def test_get_session_requires_resolved_credentials(monkeypatch):
    class NoCredentialsSession(FakeBotoSession):
        def get_credentials(self):
            return None

    monkeypatch.setattr(module.boto3.session, "Session", NoCredentialsSession)
    with pytest.raises(module.AWSCredentialError, match="No valid AWS credentials"):
        module.AWSCredentialManager.get_session()


def test_client_configuration_is_explicit(monkeypatch):
    captured = {}

    class RecordingSession(FakeBotoSession):
        def client(self, service_name, region_name, config):
            captured.update(
                service_name=service_name,
                region_name=region_name,
                config=config,
            )
            return FakeSecretsClient()

    monkeypatch.setattr(module.boto3.session, "Session", RecordingSession)
    monkeypatch.setattr(module, "Config", FakeConfig)

    make_manager(
        monkeypatch,
        region_name="ap-south-1",
        max_attempts=7,
        connect_timeout=11,
        read_timeout=44,
    )

    assert captured["service_name"] == "secretsmanager"
    assert captured["region_name"] == "ap-south-1"
    assert captured["config"].kwargs["retries"] == {
        "mode": "standard",
        "max_attempts": 7,
    }
    assert captured["config"].kwargs["connect_timeout"] == 11
    assert captured["config"].kwargs["read_timeout"] == 44


def test_cache_is_opt_in_and_can_be_cleared(monkeypatch):
    manager = make_manager(monkeypatch, cache_ttl_seconds=60)
    manager.client = Mock()
    manager.client.get_secret_value.return_value = {"SecretString": "cached"}

    assert manager.get_secret() == "cached"
    assert manager.get_secret() == "cached"
    manager.client.get_secret_value.assert_called_once_with(
        SecretId="MY_APP_SECRET"
    )

    manager.clear_cache("MY_APP_SECRET")
    assert manager._secret_cache == {}


def test_cache_is_not_shared_between_instances(monkeypatch):
    first = make_manager(monkeypatch, cache_ttl_seconds=60)
    second = make_manager(monkeypatch, cache_ttl_seconds=60)
    first.client = Mock()
    second.client = Mock()
    first.client.get_secret_value.return_value = {"SecretString": "one"}
    second.client.get_secret_value.return_value = {"SecretString": "two"}

    assert first.get_secret() == "one"
    assert second.get_secret() == "two"


def test_explicit_secret_name_overrides_constructor_name(monkeypatch):
    manager = make_manager(monkeypatch)
    manager.client = Mock()
    manager.client.get_secret_value.return_value = {"SecretString": "override"}

    assert manager.get_secret("OTHER_SECRET") == "override"
    manager.client.get_secret_value.assert_called_once_with(
        SecretId="OTHER_SECRET"
    )
