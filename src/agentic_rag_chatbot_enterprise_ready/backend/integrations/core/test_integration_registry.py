"""Regression tests for the provider integration registry."""

import threading

import pytest

from backend.integration.integration_exceptions import (
    IntegrationConfigurationError,
    IntegrationConflictError,
    IntegrationNotFoundError,
)
from backend.integration.integration_models import (
    CapabilityOperation,
    IntegrationAuthMode,
    IntegrationCapability,
    IntegrationDescriptor,
    IntegrationProvider,
    IntegrationScope,
)
from backend.integration.integration_registry import (
    IntegrationRegistry,
    RegisteredIntegration,
    build_registry,
)


def descriptor(
    provider=IntegrationProvider.JIRA,
    *,
    enabled=True,
    capability_name="search",
):
    return IntegrationDescriptor(
        provider=provider,
        display_name=provider.value.title(),
        description=f"{provider.value} enterprise integration.",
        auth_modes=(IntegrationAuthMode.OAUTH2,),
        supported_scopes=(IntegrationScope.USER,),
        capabilities=(
            IntegrationCapability(
                name=capability_name,
                operation=CapabilityOperation.SEARCH,
                description=f"Search {provider.value}.",
            ),
        ),
        enabled=enabled,
    )


def factory(*args, **kwargs):
    return {
        "args": args,
        "kwargs": kwargs,
    }


def test_register_and_lookup_by_enum():
    registry = IntegrationRegistry()
    registry.register(descriptor(), factory)

    registration = registry.get(IntegrationProvider.JIRA)

    assert isinstance(registration, RegisteredIntegration)
    assert registration.descriptor.provider is IntegrationProvider.JIRA
    assert registration.factory is factory


def test_lookup_by_string_is_normalized():
    registry = IntegrationRegistry()
    registry.register(descriptor(), factory)

    assert registry.is_registered(" JIRA ")
    assert registry.descriptor("jira").display_name == "Jira"


def test_duplicate_registration_requires_explicit_replace():
    registry = IntegrationRegistry()
    registry.register(descriptor(), factory)

    with pytest.raises(IntegrationConflictError):
        registry.register(
            descriptor(capability_name="different"),
            lambda: "replacement",
        )


def test_explicit_replace_is_supported():
    registry = IntegrationRegistry()
    registry.register(descriptor(), factory)

    replacement = lambda: "replacement"
    registry.register(
        descriptor(capability_name="different"),
        replacement,
        replace=True,
    )

    assert registry.factory("jira") is replacement
    assert registry.capabilities("jira")[0].name == "different"


def test_invalid_factory_is_rejected():
    registry = IntegrationRegistry()

    with pytest.raises(IntegrationConfigurationError):
        registry.register(descriptor(), object())


def test_invalid_descriptor_is_rejected():
    registry = IntegrationRegistry()

    with pytest.raises(IntegrationConfigurationError):
        registry.register(object(), factory)


def test_unregistered_provider_raises():
    registry = IntegrationRegistry()

    with pytest.raises(IntegrationNotFoundError):
        registry.get("jira")


def test_unsupported_provider_raises():
    registry = IntegrationRegistry()

    with pytest.raises(IntegrationNotFoundError):
        registry.get("not-a-provider")


def test_unregister_removes_provider():
    registry = IntegrationRegistry()
    registry.register(descriptor(), factory)

    registry.unregister("jira")

    assert registry.is_registered("jira") is False

    with pytest.raises(IntegrationNotFoundError):
        registry.get("jira")


def test_unregister_missing_provider_raises():
    registry = IntegrationRegistry()

    with pytest.raises(IntegrationNotFoundError):
        registry.unregister("jira")


def test_disabled_provider_is_hidden_by_default():
    registry = IntegrationRegistry()
    registry.register(
        descriptor(enabled=False),
        factory,
    )

    assert registry.list_descriptors() == ()
    assert registry.list_providers() == ()
    assert registry.list_descriptors(enabled_only=False)[0].enabled is False


def test_disabled_provider_cannot_create_connector():
    registry = IntegrationRegistry()
    registry.register(
        descriptor(enabled=False),
        factory,
    )

    with pytest.raises(IntegrationConfigurationError):
        registry.create_connector("jira")


def test_enabled_provider_can_create_connector():
    registry = IntegrationRegistry()
    registry.register(descriptor(), factory)

    result = registry.create_connector(
        "jira",
        "connection-id",
        mode="read-only",
    )

    assert result == {
        "args": ("connection-id",),
        "kwargs": {"mode": "read-only"},
    }


def test_factory_failure_is_normalized_without_leaking_exception_text():
    def failing_factory():
        raise RuntimeError("secret-token-should-not-escape")

    registry = IntegrationRegistry()
    registry.register(descriptor(), failing_factory)

    with pytest.raises(IntegrationConfigurationError) as exc_info:
        registry.create_connector("jira")

    error = exc_info.value

    assert "secret-token" not in str(error)
    assert error.details == {"exception_type": "RuntimeError"}


def test_list_providers_is_deterministically_sorted():
    registry = IntegrationRegistry()
    registry.register(descriptor(IntegrationProvider.SAP), factory)
    registry.register(descriptor(IntegrationProvider.JIRA), factory)
    registry.register(descriptor(IntegrationProvider.SALESFORCE), factory)

    assert registry.list_providers() == (
        IntegrationProvider.JIRA,
        IntegrationProvider.SALESFORCE,
        IntegrationProvider.SAP,
    )


def test_capabilities_are_provider_metadata_only():
    registry = IntegrationRegistry()
    registry.register(
        descriptor(capability_name="search_jira_issues"),
        factory,
    )

    capabilities = registry.capabilities("jira")

    assert len(capabilities) == 1
    assert capabilities[0].name == "search_jira_issues"


def test_clear_removes_all_registrations():
    registry = IntegrationRegistry()
    registry.register(descriptor(IntegrationProvider.JIRA), factory)
    registry.register(descriptor(IntegrationProvider.SAP), factory)

    registry.clear()

    assert registry.list_providers(enabled_only=False) == ()


def test_constructor_accepts_initial_registrations():
    registrations = (
        RegisteredIntegration(
            descriptor=descriptor(IntegrationProvider.JIRA),
            factory=factory,
        ),
        RegisteredIntegration(
            descriptor=descriptor(IntegrationProvider.SAP),
            factory=factory,
        ),
    )

    registry = IntegrationRegistry(registrations)

    assert registry.list_providers() == (
        IntegrationProvider.JIRA,
        IntegrationProvider.SAP,
    )


def test_build_registry_accepts_explicit_mapping():
    registry = build_registry(
        {
            IntegrationProvider.JIRA: (
                descriptor(IntegrationProvider.JIRA),
                factory,
            ),
        }
    )

    assert registry.is_registered("jira")


def test_build_registry_rejects_provider_descriptor_mismatch():
    with pytest.raises(IntegrationConfigurationError):
        build_registry(
            {
                IntegrationProvider.JIRA: (
                    descriptor(IntegrationProvider.SAP),
                    factory,
                ),
            }
        )


def test_registry_is_safe_for_concurrent_registration_and_lookup():
    registry = IntegrationRegistry()

    errors = []

    def register_provider(provider):
        try:
            registry.register(
                descriptor(provider),
                factory,
            )
        except Exception as exc:
            errors.append(exc)

    threads = [
        threading.Thread(
            target=register_provider,
            args=(IntegrationProvider.JIRA,),
        ),
        threading.Thread(
            target=register_provider,
            args=(IntegrationProvider.SAP,),
        ),
    ]

    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []
    assert set(registry.list_providers()) == {
        IntegrationProvider.JIRA,
        IntegrationProvider.SAP,
    }


def test_registry_does_not_import_provider_modules_implicitly():
    registry = build_registry()

    assert registry.list_providers() == ()
