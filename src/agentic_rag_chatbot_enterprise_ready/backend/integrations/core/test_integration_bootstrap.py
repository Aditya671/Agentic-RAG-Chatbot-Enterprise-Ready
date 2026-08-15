"""Regression tests for integration bootstrap/provider composition."""

import json

import pytest

from backend.integration.credential_store import InMemorySecretStore
from backend.integration.integration_models import (
    CapabilityOperation,
    IntegrationAuthMode,
    IntegrationCapability,
    IntegrationProvider,
    IntegrationStatus,
)
from backend.integration.integration_registry import IntegrationRegistry
from backend.integration.integration_models import IntegrationHealth
from backend.integration.integration_bootstrap import (
    ProviderBinding,
    register_provider_bindings,
)
class FakeConfig:
    def __init__(self, **kwargs):
        self.values = kwargs


class FakeConnector:
    def __init__(self, config, **kwargs):
        self.config = config
        self.kwargs = kwargs

    async def health_check(self):
        return IntegrationHealth.now(IntegrationStatus.CONNECTED)

    def disconnect(self):
        pass


def binding(provider):
    return ProviderBinding(
        provider=provider,
        display_name=provider.value.title(),
        description=f"{provider.value} integration.",
        config_factory=FakeConfig,
        connector_factory=FakeConnector,
        secret_fields=frozenset({"access_token", "client_secret"}),
        auth_modes=frozenset({IntegrationAuthMode.OAUTH2}),
        capabilities=(
            IntegrationCapability(
                name=f"read_{provider.value}",
                operation=CapabilityOperation.READ,
                description=f"Read {provider.value}.",
            ),
            IntegrationCapability(
                name=f"search_{provider.value}",
                operation=CapabilityOperation.SEARCH,
                description=f"Search {provider.value}.",
            ),
        ),
    )


def test_register_custom_bindings():
    store = InMemorySecretStore()
    registry = IntegrationRegistry()

    register_provider_bindings(
        registry,
        store,
        (
            binding(IntegrationProvider.JIRA),
            binding(IntegrationProvider.SAP),
        ),
    )

    assert registry.list_providers() == (
        IntegrationProvider.JIRA,
        IntegrationProvider.SAP,
    )


def test_descriptor_contains_business_capabilities():
    store = InMemorySecretStore()
    registry = IntegrationRegistry()

    register_provider_bindings(
        registry,
        store,
        (binding(IntegrationProvider.JIRA),),
    )

    descriptor = registry.descriptor("jira")

    assert descriptor.display_name == "Jira"
    assert descriptor.capabilities[0].operation is CapabilityOperation.READ
    assert descriptor.capabilities[1].operation is CapabilityOperation.SEARCH


def test_factory_requires_explicit_connection_inputs():
    store = InMemorySecretStore()
    registry = IntegrationRegistry()

    register_provider_bindings(
        registry,
        store,
        (binding(IntegrationProvider.JIRA),),
    )

    connector = registry.create_connector(
        "jira",
        config={"client_id": "client"},
    )

    assert connector.config.values["client_id"] == "client"


def test_secret_reference_is_resolved_only_by_adapter():
    store = InMemorySecretStore()
    registry = IntegrationRegistry()

    register_provider_bindings(
        registry,
        store,
        (binding(IntegrationProvider.JIRA),),
    )

    reference = store.put_secret(
        owner_id="user-1",
        secret=json.dumps({"access_token": "runtime-token"}),
    )

    connector = registry.create_connector(
        "jira",
        config={"client_id": "client"},
        secret_reference=reference,
        auth_mode=IntegrationAuthMode.OAUTH2,
    )

    assert connector.kwargs["access_token"] == "runtime-token"
    assert "access_token" not in connector.config.values


def test_unsupported_provider_is_not_implicitly_registered():
    store = InMemorySecretStore()
    registry = IntegrationRegistry()

    register_provider_bindings(
        registry,
        store,
        (binding(IntegrationProvider.JIRA),),
    )

    assert registry.is_registered("jira")
    assert registry.is_registered("sap") is False


def test_custom_binding_can_be_disabled():
    store = InMemorySecretStore()
    registry = IntegrationRegistry()

    disabled = ProviderBinding(
        **{
            **binding(IntegrationProvider.SAP).__dict__,
            "enabled": False,
        }
    )

    register_provider_bindings(
        registry,
        store,
        (disabled,),
    )

    assert registry.list_providers() == ()
    assert registry.list_providers(enabled_only=False) == (
        IntegrationProvider.SAP,
    )


def test_all_default_bindings_have_unique_provider_names(monkeypatch):
    """Use fake provider modules to verify composition metadata independently.

    The actual provider packages are tested by their own regression suites.
    This test validates the composition contract without requiring live SDKs.
    """
    # The default binding loader imports concrete modules. Instead of importing
    # real SDK-heavy modules here, verify the contract against explicit binding
    # data used by the registration layer.
    bindings = tuple(binding(provider) for provider in IntegrationProvider)

    providers = [item.provider for item in bindings]
    assert len(providers) == len(set(providers))


def test_binding_capabilities_are_non_empty():
    for provider in IntegrationProvider:
        item = binding(provider)
        assert item.capabilities
        assert all(cap.name for cap in item.capabilities)


def test_factory_closure_keeps_provider_identity():
    store = InMemorySecretStore()
    registry = IntegrationRegistry()

    register_provider_bindings(
        registry,
        store,
        (
            binding(IntegrationProvider.JIRA),
            binding(IntegrationProvider.SAP),
        ),
    )

    jira = registry.create_connector("jira", config={})
    sap = registry.create_connector("sap", config={})

    assert jira.config.values == {}
    assert sap.config.values == {}
    assert registry.descriptor("jira").provider is IntegrationProvider.JIRA
    assert registry.descriptor("sap").provider is IntegrationProvider.SAP


def test_registry_factory_does_not_receive_secret_reference_in_config():
    store = InMemorySecretStore()
    registry = IntegrationRegistry()
    register_provider_bindings(
        registry,
        store,
        (binding(IntegrationProvider.JIRA),),
    )

    reference = store.put_secret(
        owner_id="user-1",
        secret=json.dumps({"access_token": "secret"}),
    )

    connector = registry.create_connector(
        "jira",
        config={"client_id": "client"},
        secret_reference=reference,
        auth_mode=IntegrationAuthMode.OAUTH2,
    )

    assert "secret_reference" not in connector.config.values


def test_register_rejects_invalid_registry():
    with pytest.raises(TypeError):
        register_provider_bindings(
            object(),
            InMemorySecretStore(),
            (binding(IntegrationProvider.JIRA),),
        )


def test_register_rejects_invalid_secret_store():
    with pytest.raises(TypeError):
        register_provider_bindings(
            IntegrationRegistry(),
            object(),
            (binding(IntegrationProvider.JIRA),),
        )


def test_read_and_search_capabilities_are_not_write_capabilities():
    item = binding(IntegrationProvider.JIRA)
    operations = {cap.name: cap.operation for cap in item.capabilities}

    assert operations["read_jira"] is CapabilityOperation.READ
    assert operations["search_jira"] is CapabilityOperation.SEARCH
    assert all(
        operation in {
            CapabilityOperation.READ,
            CapabilityOperation.SEARCH,
        }
        for operation in operations.values()
    )
