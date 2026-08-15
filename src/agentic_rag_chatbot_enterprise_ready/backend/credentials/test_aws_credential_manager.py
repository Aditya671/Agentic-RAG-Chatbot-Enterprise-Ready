import importlib.util
import os
import sys
import types
from pathlib import Path
from unittest.mock import Mock

import pytest


MODULE_PATH = Path("/mnt/data/aws_credential_manager_upgraded.py")


# Dependency-isolated AWS stubs.
boto3_module = types.ModuleType("boto3")
botocore_module = types.ModuleType("botocore")
botocore_config_module = types.ModuleType("botocore.config")
botocore_exceptions_module = types.ModuleType("botocore.exceptions")
botocore_session_module = types.ModuleType("botocore.session")


class FakeCredentials:
    pass


class FakeBotoSession:
    credentials = FakeCredentials()

    def __init__(self):
        self.client_calls = []

    def get_credentials(self):
        return self.credentials

    def client(self, service_name, region_name, config):
        self.client_calls.append(
            {
                "service_name": service_name,
                "region_name": region_name,
                "config": config,
            }
        )
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


class FakeBotocoreSession:
    pass


def fake_session_factory():
    return FakeBotoSession()


boto3_module.session = types.SimpleNamespace(
    Session=fake_session_factory,
)

botocore_config_module.Config = FakeConfig
botocore_exceptions_module.ClientError = FakeClientError
botocore_exceptions_module.NoCredentialsError = type(
    "NoCredentialsError",
    (Exception,),
    {},
)
botocore_exceptions_module.PartialCredentialsError = type(
    "PartialCredentialsError",
    (Exception,),
    {},
)
botocore_session_module.Session = FakeBotocoreSession

sys.modules["boto3"] = boto3_module
sys.modules["botocore"] = botocore_module
sys.modules["botocore.config"] = botocore_config_module
sys.modules["botocore.exceptions"] = botocore_exceptions_module
sys.modules["botocore.session"] = botocore_session_module

spec = importlib.util.spec_from_file_location(
    "aws_credential_manager_under_test",
    MODULE_PATH,
)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    monkeypatch.delenv("MY_APP_SECRET", raising=False)
    monkeypatch.delenv("OTHER_SECRET", raising=False)
    yield


def make_manager(secret_name="MY_APP_SECRET", **kwargs):
    return module.AWSCredentialManager(
        secret_name=secret_name,
        **kwargs,
    )


def test_default_region_is_preserved():
    manager = make_manager()
    assert manager.region_name == "us-east-1"


def test_custom_region_is_preserved():
    manager = make_manager(region_name="ap-south-1")
    assert manager.region_name == "ap-south-1"


def test_empty_secret_name_is_rejected():
    with pytest.raises(ValueError):
        make_manager(secret_name="")


def test_whitespace_secret_name_is_rejected():
    with pytest.raises(ValueError):
        make_manager(secret_name="   ")


def test_empty_region_is_rejected():
    with pytest.raises(ValueError):
        make_manager(region_name="")


def test_environment_secret_has_precedence(monkeypatch):
    monkeypatch.setenv("MY_APP_SECRET", "from-environment")

    manager = make_manager()
    manager.client = Mock()

    assert manager.get_secret() == "from-environment"
    manager.client.get_secret_value.assert_not_called()


def test_explicit_secret_name_overrides_constructor_secret_name():
    manager = make_manager(secret_name="MY_APP_SECRET")

    manager.client = Mock()
    manager.client.get_secret_value.return_value = {
        "SecretString": "from-aws"
    }

    assert manager.get_secret("OTHER_SECRET") == "from-aws"
    manager.client.get_secret_value.assert_called_once_with(
        SecretId="OTHER_SECRET"
    )


def test_explicit_environment_secret_is_supported(monkeypatch):
    monkeypatch.setenv("OTHER_SECRET", "other-value")

    manager = make_manager()
    assert manager.get_secret("OTHER_SECRET") == "other-value"


def test_no_secret_name_is_rejected():
    manager = module.AWSCredentialManager(secret_name=None)
    with pytest.raises(ValueError, match="No secret name"):
        manager.get_secret()


def test_no_secret_configuration_does_not_create_client():
    manager = module.AWSCredentialManager()
    assert manager.client is None


def test_aws_secret_string_is_returned():
    manager = make_manager()
    manager.client = Mock()
    manager.client.get_secret_value.return_value = {
        "SecretString": "from-secrets-manager"
    }

    assert manager.get_secret() == "from-secrets-manager"


def test_empty_secret_string_is_preserved():
    manager = make_manager()
    manager.client = Mock()
    manager.client.get_secret_value.return_value = {
        "SecretString": ""
    }

    assert manager.get_secret() == ""


def test_secret_binary_utf8_is_decoded():
    manager = make_manager()
    manager.client = Mock()
    manager.client.get_secret_value.return_value = {
        "SecretBinary": b"binary-secret"
    }

    assert manager.get_secret() == "binary-secret"


def test_secret_binary_bytearray_utf8_is_decoded():
    manager = make_manager()
    manager.client = Mock()
    manager.client.get_secret_value.return_value = {
        "SecretBinary": bytearray(b"binary-secret")
    }

    assert manager.get_secret() == "binary-secret"


def test_secret_binary_string_is_supported():
    manager = make_manager()
    manager.client = Mock()
    manager.client.get_secret_value.return_value = {
        "SecretBinary": "binary-secret"
    }

    assert manager.get_secret() == "binary-secret"


def test_invalid_secret_binary_utf8_is_rejected():
    manager = make_manager()
    manager.client = Mock()
    manager.client.get_secret_value.return_value = {
        "SecretBinary": b"\xff\xfe"
    }

    with pytest.raises(module.AWSSecretError, match="UTF-8"):
        manager.get_secret()


def test_missing_secret_payload_is_rejected():
    manager = make_manager()
    manager.client = Mock()
    manager.client.get_secret_value.return_value = {}

    with pytest.raises(module.AWSSecretError, match="neither"):
        manager.get_secret()


def test_resource_not_found_is_normalized():
    manager = make_manager()
    manager.client = Mock()
    manager.client.get_secret_value.side_effect = FakeClientError(
        "ResourceNotFoundException"
    )

    with pytest.raises(module.AWSSecretError, match="not found"):
        manager.get_secret()


def test_access_denied_is_normalized_without_exposing_error_payload():
    manager = make_manager()
    manager.client = Mock()
    manager.client.get_secret_value.side_effect = FakeClientError(
        "AccessDeniedException",
        message="SECRET_VALUE_SHOULD_NOT_APPEAR",
    )

    with pytest.raises(module.AWSSecretError) as exc_info:
        manager.get_secret()

    assert "SECRET_VALUE_SHOULD_NOT_APPEAR" not in str(exc_info.value)


def test_other_client_error_is_normalized():
    manager = make_manager()
    manager.client = Mock()
    manager.client.get_secret_value.side_effect = FakeClientError(
        "ThrottlingException"
    )

    with pytest.raises(module.AWSSecretError, match="ThrottlingException"):
        manager.get_secret()


def test_original_client_error_is_preserved_as_cause():
    manager = make_manager()
    manager.client = Mock()
    original = FakeClientError("InternalServiceError")
    manager.client.get_secret_value.side_effect = original

    with pytest.raises(module.AWSSecretError) as exc_info:
        manager.get_secret()

    assert exc_info.value.__cause__ is original


def test_get_session_requires_credentials(monkeypatch):
    class NoCredentialsSession(FakeBotoSession):
        def get_credentials(self):
            return None

    monkeypatch.setattr(
        module.boto3.session,
        "Session",
        NoCredentialsSession,
    )

    with pytest.raises(module.AWSCredentialError, match="No valid AWS credentials"):
        module.AWSCredentialManager.get_session()


def test_get_session_wraps_no_credentials_exception(monkeypatch):
    no_credentials = module.NoCredentialsError("missing")

    class FailingSession:
        def __init__(self):
            raise no_credentials

    monkeypatch.setattr(module.boto3.session, "Session", FailingSession)

    with pytest.raises(module.AWSCredentialError) as exc_info:
        module.AWSCredentialManager.get_session()

    assert exc_info.value.__cause__ is no_credentials


def test_get_session_wraps_partial_credentials_exception(monkeypatch):
    partial = module.PartialCredentialsError("partial")

    class FailingSession:
        def __init__(self):
            raise partial

    monkeypatch.setattr(module.boto3.session, "Session", FailingSession)

    with pytest.raises(module.AWSCredentialError) as exc_info:
        module.AWSCredentialManager.get_session()

    assert exc_info.value.__cause__ is partial


def test_client_is_created_with_secrets_manager_and_region(monkeypatch):
    captured = {}

    class RecordingSession(FakeBotoSession):
        def client(self, service_name, region_name, config):
            captured.update(
                service_name=service_name,
                region_name=region_name,
                config=config,
            )
            return FakeSecretsClient()

    monkeypatch.setattr(
        module.boto3.session,
        "Session",
        RecordingSession,
    )

    manager = make_manager(region_name="eu-west-1")

    assert manager.client is not None
    assert captured["service_name"] == "secretsmanager"
    assert captured["region_name"] == "eu-west-1"


def test_client_uses_standard_retries():
    captured = {}

    class RecordingSession(FakeBotoSession):
        def client(self, service_name, region_name, config):
            captured["config"] = config
            return FakeSecretsClient()

    original = module.boto3.session.Session
    module.boto3.session.Session = RecordingSession
    try:
        make_manager(max_attempts=7)
    finally:
        module.boto3.session.Session = original

    assert captured["config"].kwargs["retries"] == {
        "mode": "standard",
        "max_attempts": 7,
    }


def test_client_uses_configured_timeouts():
    captured = {}

    class RecordingSession(FakeBotoSession):
        def client(self, service_name, region_name, config):
            captured["config"] = config
            return FakeSecretsClient()

    original = module.boto3.session.Session
    module.boto3.session.Session = RecordingSession
    try:
        make_manager(
            connect_timeout=11,
            read_timeout=44,
        )
    finally:
        module.boto3.session.Session = original

    assert captured["config"].kwargs["connect_timeout"] == 11
    assert captured["config"].kwargs["read_timeout"] == 44


@pytest.mark.parametrize(
    "field,value",
    [
        ("cache_ttl_seconds", -1),
        ("cache_ttl_seconds", True),
        ("max_attempts", 0),
        ("max_attempts", False),
        ("connect_timeout", 0),
        ("read_timeout", 0),
    ],
)
def test_configuration_numeric_validation(field, value):
    kwargs = {field: value}
    with pytest.raises(ValueError):
        make_manager(**kwargs)


def test_secret_is_not_logged():
    # Source-level guard: the implementation does not log secret values.
    source = MODULE_PATH.read_text()

    assert "logger" not in source
    assert "print(" not in source


def test_secret_value_is_not_in_exception_for_access_denied():
    source = MODULE_PATH.read_text()

    assert "error.get(\"Message\"" not in source


def test_cache_is_disabled_by_default():
    manager = make_manager()
    assert manager.cache_ttl_seconds == 0
    assert manager._secret_cache == {}


def test_cache_returns_cached_value_without_second_api_call():
    manager = make_manager(cache_ttl_seconds=60)
    manager.client = Mock()
    manager.client.get_secret_value.return_value = {
        "SecretString": "cached-value"
    }

    assert manager.get_secret() == "cached-value"
    assert manager.get_secret() == "cached-value"

    manager.client.get_secret_value.assert_called_once_with(
        SecretId="MY_APP_SECRET"
    )


def test_cache_can_be_cleared_for_one_secret():
    manager = make_manager(cache_ttl_seconds=60)
    manager.client = Mock()
    manager.client.get_secret_value.return_value = {
        "SecretString": "cached-value"
    }

    assert manager.get_secret() == "cached-value"
    manager.clear_cache("MY_APP_SECRET")
    assert manager._secret_cache == {}


def test_cache_can_be_cleared_completely():
    manager = make_manager(cache_ttl_seconds=60)
    manager.client = Mock()
    manager.client.get_secret_value.return_value = {
        "SecretString": "cached-value"
    }

    manager.get_secret()
    manager.clear_cache()

    assert manager._secret_cache == {}


def test_expired_cache_is_ignored(monkeypatch):
    manager = make_manager(cache_ttl_seconds=60)
    manager.client = Mock()
    manager.client.get_secret_value.side_effect = [
        {"SecretString": "old"},
        {"SecretString": "new"},
    ]

    times = iter([100.0, 200.0, 200.0])
    monkeypatch.setattr(module.time, "monotonic", lambda: next(times))

    assert manager.get_secret() == "old"
    assert manager.get_secret() == "new"


def test_environment_secret_bypasses_cache(monkeypatch):
    manager = make_manager(cache_ttl_seconds=60)
    manager.client = Mock()
    manager.client.get_secret_value.return_value = {
        "SecretString": "aws-value"
    }

    assert manager.get_secret() == "aws-value"

    monkeypatch.setenv("MY_APP_SECRET", "environment-value")

    assert manager.get_secret() == "environment-value"
    manager.client.get_secret_value.assert_called_once()


def test_cache_is_not_shared_between_manager_instances():
    first = make_manager(cache_ttl_seconds=60)
    second = make_manager(cache_ttl_seconds=60)

    first.client = Mock()
    second.client = Mock()

    first.client.get_secret_value.return_value = {"SecretString": "one"}
    second.client.get_secret_value.return_value = {"SecretString": "two"}

    assert first.get_secret() == "one"
    assert second.get_secret() == "two"


def test_get_secret_validates_explicit_name():
    manager = make_manager()
    with pytest.raises(ValueError):
        manager.get_secret("")


def test_constructor_does_not_create_secrets_client_without_secret_name():
    manager = module.AWSCredentialManager()
    assert manager.client is None


def test_environment_only_manager_can_read_explicit_env_secret(monkeypatch):
    monkeypatch.setenv("MY_APP_SECRET", "value")

    manager = module.AWSCredentialManager()
    assert manager.get_secret("MY_APP_SECRET") == "value"


def test_aws_lookup_requires_configured_client():
    manager = module.AWSCredentialManager()
    with pytest.raises(module.AWSSecretError, match="not found"):
        manager.get_secret("MY_APP_SECRET")


def test_source_uses_boto3_session_provider_chain():
    source = MODULE_PATH.read_text()

    assert "boto3.session.Session()" in source
    assert "session.get_credentials()" in source


def test_source_does_not_create_static_access_keys():
    source = MODULE_PATH.read_text()

    assert "aws_access_key_id" not in source
    assert "aws_secret_access_key" not in source
    assert "aws_session_token" not in source


def test_source_does_not_disable_tls_verification():
    source = MODULE_PATH.read_text()

    assert "verify=False" not in source
    assert "verify = False" not in source


def test_source_does_not_use_wildcard_secret_lookup():
    source = MODULE_PATH.read_text()

    assert "list_secrets" not in source


def test_source_uses_get_secret_value():
    source = MODULE_PATH.read_text()

    assert "get_secret_value" in source


def test_source_supports_client_side_cache():
    source = MODULE_PATH.read_text()

    assert "cache_ttl_seconds" in source
    assert "_secret_cache" in source


def test_source_does_not_log_secret_values():
    source = MODULE_PATH.read_text()

    assert "logger" not in source
    assert "print(" not in source
    assert "logger." not in source


def test_error_types_are_value_error_compatible():
    assert issubclass(module.AWSCredentialError, ValueError)
    assert issubclass(module.AWSSecretError, ValueError)


def test_default_retry_attempts_are_positive():
    assert module.DEFAULT_MAX_ATTEMPTS >= 1


def test_default_timeouts_are_positive():
    assert module.DEFAULT_CONNECT_TIMEOUT_SECONDS > 0
    assert module.DEFAULT_READ_TIMEOUT_SECONDS > 0


def test_default_cache_ttl_is_zero():
    assert module.DEFAULT_CACHE_TTL_SECONDS == 0
