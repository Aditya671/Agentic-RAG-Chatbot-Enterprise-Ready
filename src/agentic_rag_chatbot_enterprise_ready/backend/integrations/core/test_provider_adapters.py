"""Regression tests for provider adapter security and construction."""

import json

import pytest

from backend.integration.credential_store import InMemorySecretStore
from backend.integration.integration_exceptions import (
    IntegrationAuthenticationError,
    IntegrationConfigurationError,
    IntegrationValidationError,
)
from backend.integration.integration_models import (
    IntegrationAuthMode,
    IntegrationProvider,
)
from backend.integration.provider_adapters import (
    AdapterRequest,
    ProviderAdapter,
    make_constructor,
)


class FakeAuthConfig:
    def __init__(self, **kwargs):
        self.values = kwargs


class FakeConnector:
    def __init__(self, config, **kwargs):
        self.config = config
        self.kwargs = kwargs


def make_adapter(
    provider=IntegrationProvider.JIRA,
    *,
    secret_fields=None,
    auth_modes=None,
    config_fields=None,
):
    constructor = make_constructor(
        provider,
        config_factory=FakeAuthConfig,
        connector_factory=FakeConnector,
        secret_fields=secret_fields
        or {"access_token", "client_secret", "cloud_id", "instance_url"},
        auth_modes=auth_modes or {IntegrationAuthMode.OAUTH2},
        config_fields=config_fields or {"client_id", "client_secret"},
    )
    store = InMemorySecretStore()
    return ProviderAdapter(constructor, store), store


def test_adapter_constructs_connector_without_secret_in_request_config():
    adapter, store = make_adapter()

    reference = store.put_secret(
        owner_id="user-1",
        secret=json.dumps(
            {
                "access_token": "secret-token",
                "cloud_id": "cloud-123",
            }
        ),
    )

    connector = adapter.create(
        AdapterRequest(
            provider=IntegrationProvider.JIRA,
            config={"client_id": "client-123"},
            secret_reference=reference,
            auth_mode=IntegrationAuthMode.OAUTH2,
        )
    )

    assert connector.config.values["client_id"] == "client-123"
    assert "access_token" not in connector.config.values
    assert connector.kwargs["access_token"] == "secret-token"
    assert connector.kwargs["cloud_id"] == "cloud-123"


def test_raw_secret_in_config_is_rejected():
    adapter, _ = make_adapter()

    with pytest.raises(ValueError):
        AdapterRequest(
            provider=IntegrationProvider.JIRA,
            config={"client_secret": "should-not-be-here"},
        )


def test_provider_mismatch_is_rejected():
    adapter, _ = make_adapter(IntegrationProvider.JIRA)

    with pytest.raises(IntegrationConfigurationError):
        adapter.create(
            AdapterRequest(
                provider=IntegrationProvider.SAP,
                config={},
            )
        )


def test_unsupported_auth_mode_is_rejected():
    adapter, _ = make_adapter(
        auth_modes={IntegrationAuthMode.OAUTH2},
    )

    with pytest.raises(IntegrationConfigurationError):
        adapter.create(
            AdapterRequest(
                provider=IntegrationProvider.JIRA,
                config={},
                auth_mode=IntegrationAuthMode.BASIC,
            )
        )


def test_missing_secret_reference_is_allowed_for_public_config():
    adapter, _ = make_adapter()

    connector = adapter.create(
        AdapterRequest(
            provider=IntegrationProvider.JIRA,
            config={"client_id": "client-123"},
        )
    )

    assert connector.config.values["client_id"] == "client-123"
    assert connector.kwargs == {}


def test_missing_secret_reference_is_normalized_to_authentication_error():
    store = InMemorySecretStore()
    adapter = make_adapter()[0]
    adapter = ProviderAdapter(adapter.constructor, store)

    from datetime import datetime, timedelta, timezone
    from backend.integration.credential_store import SecretReference

    reference = SecretReference(
        reference_id="missing-reference",
        owner_id="user-1",
        created_at=datetime.now(timezone.utc) - timedelta(hours=2),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )

    with pytest.raises(IntegrationAuthenticationError):
        adapter.create(
            AdapterRequest(
                provider=IntegrationProvider.JIRA,
                config={},
                secret_reference=reference,
            )
        )


def test_invalid_json_secret_is_rejected():
    adapter, store = make_adapter()

    reference = store.put_secret(
        owner_id="user-1",
        secret="not-json",
    )

    with pytest.raises(IntegrationValidationError):
        adapter.create(
            AdapterRequest(
                provider=IntegrationProvider.JIRA,
                config={},
                secret_reference=reference,
            )
        )


def test_non_object_json_secret_is_rejected():
    adapter, store = make_adapter()

    reference = store.put_secret(
        owner_id="user-1",
        secret=json.dumps(["not", "an", "object"]),
    )

    with pytest.raises(IntegrationValidationError):
        adapter.create(
            AdapterRequest(
                provider=IntegrationProvider.JIRA,
                config={},
                secret_reference=reference,
            )
        )


def test_unsupported_secret_field_is_rejected():
    adapter, store = make_adapter(
        secret_fields={"access_token"},
    )

    reference = store.put_secret(
        owner_id="user-1",
        secret=json.dumps(
            {
                "access_token": "token",
                "unexpected_secret": "value",
            }
        ),
    )

    with pytest.raises(IntegrationValidationError):
        adapter.create(
            AdapterRequest(
                provider=IntegrationProvider.JIRA,
                config={},
                secret_reference=reference,
            )
        )


def test_cross_provider_constructor_is_never_used():
    adapter, store = make_adapter(
        provider=IntegrationProvider.SAP,
        secret_fields={"access_token"},
    )

    reference = store.put_secret(
        owner_id="user-1",
        secret=json.dumps({"access_token": "token"}),
    )

    with pytest.raises(IntegrationConfigurationError):
        adapter.create(
            AdapterRequest(
                provider=IntegrationProvider.JIRA,
                config={},
                secret_reference=reference,
            )
        )


def test_secret_payload_never_becomes_part_of_adapter_state():
    adapter, store = make_adapter()

    reference = store.put_secret(
        owner_id="user-1",
        secret=json.dumps({"access_token": "token"}),
    )

    adapter.create(
        AdapterRequest(
            provider=IntegrationProvider.JIRA,
            config={},
            secret_reference=reference,
        )
    )

    assert not hasattr(adapter, "access_token")
    assert not hasattr(adapter, "secret")
    assert adapter.constructor.provider is IntegrationProvider.JIRA


def test_factory_exception_is_normalized():
    def failing_config(**kwargs):
        raise RuntimeError("configuration failure")

    constructor = make_constructor(
        IntegrationProvider.SAP,
        config_factory=failing_config,
        connector_factory=FakeConnector,
        secret_fields={"access_token"},
        auth_modes={IntegrationAuthMode.OAUTH2},
        config_fields={"client_id", "client_secret"},
    )
    store = InMemorySecretStore()
    adapter = ProviderAdapter(constructor, store)

    with pytest.raises(IntegrationConfigurationError) as exc:
        adapter.create(
            AdapterRequest(
                provider=IntegrationProvider.SAP,
                config={},
            )
        )

    assert exc.value.details["exception_type"] == "RuntimeError"


def test_factory_constructor_validation():
    with pytest.raises(TypeError):
        make_constructor(
            IntegrationProvider.JIRA,
            config_factory=object(),
            connector_factory=FakeConnector,
            secret_fields={"access_token"},
            auth_modes={IntegrationAuthMode.OAUTH2},
        )

    with pytest.raises(TypeError):
        make_constructor(
            IntegrationProvider.JIRA,
            config_factory=FakeAuthConfig,
            connector_factory=object(),
            secret_fields={"access_token"},
            auth_modes={IntegrationAuthMode.OAUTH2},
        )


@pytest.mark.parametrize(
    "provider,secret,expected",
    [
        (
            IntegrationProvider.SHAREPOINT,
            {"access_token": "token"},
            {"access_token": "token"},
        ),
        (
            IntegrationProvider.SALESFORCE,
            {"access_token": "token", "instance_url": "https://sf.example"},
            {"access_token": "token", "instance_url": "https://sf.example"},
        ),
        (
            IntegrationProvider.SERVICENOW,
            {"access_token": "token"},
            {"access_token": "token"},
        ),
        (
            IntegrationProvider.JIRA,
            {
                "access_token": "token",
                "cloud_id": "cloud",
                "site_url": "https://jira.example",
                "site_name": "Example",
            },
            {
                "access_token": "token",
                "cloud_id": "cloud",
                "site_url": "https://jira.example",
                "site_name": "Example",
            },
        ),
        (
            IntegrationProvider.SAP,
            {"access_token": "token"},
            {"access_token": "token"},
        ),
    ],
)
def test_provider_connector_kwargs_are_explicitly_allowlisted(
    provider,
    secret,
    expected,
):
    adapter, _ = make_adapter(provider)

    assert adapter._connector_kwargs(provider, secret) == expected


def test_sap_without_access_token_passes_none():
    adapter, _ = make_adapter(IntegrationProvider.SAP)

    assert adapter._connector_kwargs(
        IntegrationProvider.SAP,
        {},
    ) == {"access_token": None}


def test_secret_fields_are_split_between_auth_config_and_connector():
    adapter, store = make_adapter(
        secret_fields={"client_secret", "access_token"},
    )

    reference = store.put_secret(
        owner_id="user-1",
        secret=json.dumps(
            {
                "client_secret": "client-secret",
                "access_token": "runtime-token",
            }
        ),
    )

    connector = adapter.create(
        AdapterRequest(
            provider=IntegrationProvider.JIRA,
            config={"client_id": "client-id"},
            secret_reference=reference,
            auth_mode=IntegrationAuthMode.OAUTH2,
        )
    )

    assert connector.config.values["client_secret"] == "client-secret"
    assert "access_token" not in connector.config.values
    assert connector.kwargs["access_token"] == "runtime-token"
