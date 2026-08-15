"""Regression tests for provider-independent integration models."""

from datetime import datetime, timezone

import pytest

from backend.integration.integration_models import (
    CapabilityOperation,
    IntegrationAuthMode,
    IntegrationCapability,
    IntegrationConnection,
    IntegrationDescriptor,
    IntegrationHealth,
    IntegrationIdentity,
    IntegrationProvider,
    IntegrationScope,
    IntegrationStatus,
    IntegrationSummary,
)


def make_descriptor():
    return IntegrationDescriptor(
        provider=IntegrationProvider.JIRA,
        display_name="Jira",
        description="Jira Cloud enterprise integration.",
        auth_modes=(IntegrationAuthMode.OAUTH2,),
        supported_scopes=(
            IntegrationScope.USER,
            IntegrationScope.TENANT,
        ),
        capabilities=(
            IntegrationCapability(
                name="search_jira_issues",
                operation=CapabilityOperation.SEARCH,
                description="Search Jira issues.",
            ),
            IntegrationCapability(
                name="get_jira_issue",
                operation=CapabilityOperation.READ,
                description="Read a Jira issue.",
            ),
        ),
    )


def make_identity(scope=IntegrationScope.USER):
    return IntegrationIdentity(
        subject_id="user-123",
        scope=scope,
        tenant_id="tenant-123" if scope == IntegrationScope.TENANT else None,
        display_name="Test User",
    )


def make_connection():
    return IntegrationConnection(
        connection_id="conn-123",
        provider=IntegrationProvider.JIRA,
        identity=make_identity(),
        status=IntegrationStatus.CONNECTED,
        auth_mode=IntegrationAuthMode.OAUTH2,
        endpoint="https://api.atlassian.com",
        provider_resource_id="cloud-123",
        provider_resource_name="Example Jira",
    )


def test_provider_is_normalized_from_string():
    assert IntegrationProvider.from_value(" JIRA ") is IntegrationProvider.JIRA


def test_unknown_provider_is_rejected():
    with pytest.raises(ValueError):
        IntegrationProvider.from_value("unknown-provider")


def test_capability_requires_name_and_description():
    with pytest.raises(ValueError):
        IntegrationCapability(
            name="",
            operation=CapabilityOperation.READ,
            description="Read something.",
        )

    with pytest.raises(ValueError):
        IntegrationCapability(
            name="read_issue",
            operation=CapabilityOperation.READ,
            description="",
        )


def test_capability_name_cannot_contain_whitespace():
    with pytest.raises(ValueError):
        IntegrationCapability(
            name="read issue",
            operation=CapabilityOperation.READ,
            description="Read an issue.",
        )


def test_descriptor_requires_auth_mode():
    with pytest.raises(ValueError):
        IntegrationDescriptor(
            provider=IntegrationProvider.SAP,
            display_name="SAP",
            description="SAP integration.",
            auth_modes=(),
        )


def test_descriptor_rejects_duplicate_capabilities():
    capability = IntegrationCapability(
        name="read_issue",
        operation=CapabilityOperation.READ,
        description="Read an issue.",
    )

    with pytest.raises(ValueError):
        IntegrationDescriptor(
            provider=IntegrationProvider.JIRA,
            display_name="Jira",
            description="Jira integration.",
            auth_modes=(IntegrationAuthMode.OAUTH2,),
            capabilities=(capability, capability),
        )


def test_tenant_identity_requires_tenant_id():
    with pytest.raises(ValueError):
        IntegrationIdentity(
            subject_id="user-123",
            scope=IntegrationScope.TENANT,
        )


def test_user_identity_does_not_require_tenant_id():
    identity = make_identity()
    assert identity.tenant_id is None


def test_health_requires_timezone_aware_timestamp():
    with pytest.raises(ValueError):
        IntegrationHealth(
            status=IntegrationStatus.CONNECTED,
            checked_at=datetime(2026, 8, 8, 12, 0, 0),
        )


def test_health_now_is_utc():
    health = IntegrationHealth.now(IntegrationStatus.CONNECTED)

    assert health.checked_at.tzinfo is not None
    assert health.checked_at.utcoffset() == timezone.utc.utcoffset(
        health.checked_at
    )


def test_connection_requires_id():
    with pytest.raises(ValueError):
        IntegrationConnection(
            connection_id="",
            provider=IntegrationProvider.SAP,
            identity=make_identity(),
        )


def test_connection_endpoint_must_be_https():
    with pytest.raises(ValueError):
        IntegrationConnection(
            connection_id="conn-1",
            provider=IntegrationProvider.SAP,
            identity=make_identity(),
            endpoint="http://sap.example.com",
        )


def test_connection_can_have_no_endpoint():
    connection = IntegrationConnection(
        connection_id="conn-1",
        provider=IntegrationProvider.SAP,
        identity=make_identity(),
    )
    assert connection.endpoint is None


def test_connection_with_health_is_immutable_snapshot():
    connection = make_connection()
    health = IntegrationHealth.now(
        IntegrationStatus.DEGRADED,
        message="Provider is reachable but degraded.",
    )

    updated = connection.with_health(health)

    assert connection.status is IntegrationStatus.CONNECTED
    assert updated.status is IntegrationStatus.DEGRADED
    assert updated.last_health == health
    assert updated.connection_id == connection.connection_id
    assert updated.created_at == connection.created_at
    assert updated.updated_at >= connection.updated_at


def test_summary_excludes_secrets_and_is_derived_from_connection():
    connection = make_connection()
    summary = IntegrationSummary.from_connection(
        connection,
        make_descriptor(),
    )

    assert summary.connection_id == "conn-123"
    assert summary.provider is IntegrationProvider.JIRA
    assert summary.display_name == "Jira"
    assert summary.endpoint == "https://api.atlassian.com"
    assert not hasattr(summary, "access_token")
    assert not hasattr(summary, "client_secret")
    assert not hasattr(summary, "password")


def test_enum_values_are_stable_strings():
    assert IntegrationProvider.SAP.value == "sap"
    assert IntegrationStatus.CONNECTED.value == "connected"
    assert IntegrationScope.USER.value == "user"
    assert CapabilityOperation.SEARCH.value == "search"


def test_descriptor_deduplicates_auth_modes_and_scopes():
    descriptor = IntegrationDescriptor(
        provider=IntegrationProvider.SAP,
        display_name="SAP",
        description="SAP integration.",
        auth_modes=(
            IntegrationAuthMode.OAUTH2,
            IntegrationAuthMode.OAUTH2,
        ),
        supported_scopes=(
            IntegrationScope.USER,
            IntegrationScope.USER,
        ),
    )

    assert descriptor.auth_modes == (IntegrationAuthMode.OAUTH2,)
    assert descriptor.supported_scopes == (IntegrationScope.USER,)


def test_capability_metadata_is_copied():
    metadata = {"dangerous": False}
    capability = IntegrationCapability(
        name="read_data",
        operation=CapabilityOperation.READ,
        description="Read data.",
        metadata=metadata,
    )

    metadata["dangerous"] = True

    assert capability.metadata["dangerous"] is False
