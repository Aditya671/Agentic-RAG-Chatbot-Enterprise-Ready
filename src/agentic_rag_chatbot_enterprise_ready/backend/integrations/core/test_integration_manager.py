"""Regression tests for the application integration manager."""

from dataclasses import dataclass

import pytest

from backend.integration.integration_exceptions import (
    IntegrationCapabilityError,
    IntegrationConfigurationError,
    IntegrationConflictError,
    IntegrationConnectionError,
    IntegrationNotFoundError,
    IntegrationPolicyError,
)
from backend.integration.integration_manager import (
    ConnectionRequest,
    IntegrationManager,
)
from backend.integration.integration_models import (
    CapabilityOperation,
    IntegrationAuthMode,
    IntegrationCapability,
    IntegrationDescriptor,
    IntegrationIdentity,
    IntegrationProvider,
    IntegrationScope,
    IntegrationStatus,
)
from backend.integration.integration_registry import IntegrationRegistry


@dataclass
class FakeHealth:
    connected: bool = True
    error: str | None = None
    base_url: str = "https://example.test"
    auth_mode: str = "oauth2"
    api_version: str = "v1"


class FakeConnector:
    def __init__(self, *, health=None, disconnect_error=None):
        self.health = health or FakeHealth()
        self.disconnect_error = disconnect_error
        self.disconnected = False
        self.health_calls = 0

    async def health_check(self):
        self.health_calls += 1
        return self.health

    def disconnect(self):
        if self.disconnect_error:
            raise self.disconnect_error
        self.disconnected = True


def make_descriptor(
    provider=IntegrationProvider.JIRA,
    *,
    enabled=True,
    capabilities=None,
    auth_modes=(IntegrationAuthMode.OAUTH2,),
    scopes=(IntegrationScope.USER,),
):
    if capabilities is None:
        capabilities = (
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
            IntegrationCapability(
                name="delete_jira_issue",
                operation=CapabilityOperation.DELETE,
                description="Delete a Jira issue.",
                requires_confirmation=True,
            ),
        )

    return IntegrationDescriptor(
        provider=provider,
        display_name=provider.value.title(),
        description=f"{provider.value} enterprise integration.",
        auth_modes=auth_modes,
        supported_scopes=scopes,
        capabilities=capabilities,
        enabled=enabled,
    )


def make_registry(connector):
    registry = IntegrationRegistry()
    registry.register(
        make_descriptor(),
        lambda **kwargs: connector,
    )
    return registry


def request(
    *,
    connection_id="jira-connection-1",
    provider=IntegrationProvider.JIRA,
    auth_mode=IntegrationAuthMode.OAUTH2,
    scope=IntegrationScope.USER,
    tenant_id=None,
    metadata=None,
):
    return ConnectionRequest(
        provider=provider,
        connection_id=connection_id,
        identity=IntegrationIdentity(
            subject_id="user-1",
            scope=scope,
            tenant_id=tenant_id,
        ),
        auth_mode=auth_mode,
        endpoint="https://jira.example.com",
        provider_resource_id="cloud-1",
        provider_resource_name="Example Jira",
        metadata=metadata or {},
    )


@pytest.mark.asyncio
async def test_connect_creates_managed_connection_and_health():
    connector = FakeConnector()
    manager = IntegrationManager(make_registry(connector))

    state = await manager.connect(request())

    assert state.connection_id == "jira-connection-1"
    assert state.provider is IntegrationProvider.JIRA
    assert state.status is IntegrationStatus.CONNECTED
    assert connector.health_calls == 1
    assert manager.connection_exists(state.connection_id)


@pytest.mark.asyncio
async def test_connect_normalizes_provider_health_shape():
    connector = FakeConnector(
        health=FakeHealth(
            connected=False,
            error="Provider unavailable.",
        )
    )
    manager = IntegrationManager(make_registry(connector))

    with pytest.raises(IntegrationConnectionError) as exc_info:
        await manager.connect(request())

    assert exc_info.value.details["status"] == "error"
    assert manager.connection_exists("jira-connection-1") is False
    assert connector.disconnected is True


@pytest.mark.asyncio
async def test_duplicate_connection_id_is_rejected():
    connector = FakeConnector()
    manager = IntegrationManager(make_registry(connector))

    await manager.connect(request())

    with pytest.raises(IntegrationConflictError):
        await manager.connect(request())


@pytest.mark.asyncio
async def test_unsupported_auth_mode_is_rejected_before_factory_call():
    connector = FakeConnector()
    manager = IntegrationManager(make_registry(connector))

    with pytest.raises(Exception) as exc_info:
        await manager.connect(
            request(auth_mode=IntegrationAuthMode.BASIC)
        )

    assert exc_info.value.code == "integration_authorization_error"


@pytest.mark.asyncio
async def test_unsupported_scope_is_rejected():
    connector = FakeConnector()
    manager = IntegrationManager(make_registry(connector))

    with pytest.raises(Exception) as exc_info:
        await manager.connect(
            request(
                scope=IntegrationScope.TENANT,
                tenant_id="tenant-1",
            )
        )

    assert exc_info.value.code == "integration_authorization_error"


@pytest.mark.asyncio
async def test_tenant_scope_can_be_supported_by_descriptor():
    connector = FakeConnector()
    registry = IntegrationRegistry()
    registry.register(
        make_descriptor(
            scopes=(
                IntegrationScope.USER,
                IntegrationScope.TENANT,
            )
        ),
        lambda **kwargs: connector,
    )
    manager = IntegrationManager(registry)

    state = await manager.connect(
        request(
            scope=IntegrationScope.TENANT,
            tenant_id="tenant-1",
        )
    )

    assert state.identity.scope is IntegrationScope.TENANT
    assert state.identity.tenant_id == "tenant-1"


@pytest.mark.asyncio
async def test_disabled_provider_cannot_connect():
    connector = FakeConnector()
    registry = IntegrationRegistry()
    registry.register(
        make_descriptor(enabled=False),
        lambda **kwargs: connector,
    )
    manager = IntegrationManager(registry)

    with pytest.raises(Exception) as exc_info:
        await manager.connect(request())

    assert exc_info.value.code == "integration_configuration_error"


@pytest.mark.asyncio
async def test_get_and_list_connections():
    connector = FakeConnector()
    manager = IntegrationManager(make_registry(connector))

    await manager.connect(request())

    state = manager.get_connection("jira-connection-1")
    states = manager.list_connections()
    filtered = manager.list_connections(
        provider="jira",
        identity_subject_id="user-1",
    )

    assert state.status is IntegrationStatus.CONNECTED
    assert len(states) == 1
    assert len(filtered) == 1


def test_missing_connection_raises():
    manager = IntegrationManager(IntegrationRegistry())

    with pytest.raises(IntegrationNotFoundError):
        manager.get_connection("missing")


@pytest.mark.asyncio
async def test_refresh_health_updates_state():
    connector = FakeConnector()
    manager = IntegrationManager(make_registry(connector))

    await manager.connect(request())

    connector.health = FakeHealth(
        connected=False,
        error="degraded",
    )

    state = await manager.refresh_health("jira-connection-1")

    assert state.status is IntegrationStatus.ERROR
    assert state.last_health is not None
    assert state.last_health.message == "degraded"


@pytest.mark.asyncio
async def test_disconnect_removes_connection():
    connector = FakeConnector()
    manager = IntegrationManager(make_registry(connector))

    await manager.connect(request())
    await manager.disconnect("jira-connection-1")

    assert connector.disconnected is True
    assert manager.connection_exists("jira-connection-1") is False

    with pytest.raises(IntegrationNotFoundError):
        manager.get_connection("jira-connection-1")


@pytest.mark.asyncio
async def test_disconnect_failure_still_removes_managed_connection():
    connector = FakeConnector(
        disconnect_error=RuntimeError("disconnect failed")
    )
    manager = IntegrationManager(make_registry(connector))

    await manager.connect(request())

    with pytest.raises(IntegrationConnectionError):
        await manager.disconnect("jira-connection-1")

    assert manager.connection_exists("jira-connection-1") is False


def test_capability_discovery():
    manager = IntegrationManager(
        make_registry(FakeConnector())
    )

    capabilities = manager.capabilities("jira")

    assert [item.name for item in capabilities] == [
        "search_jira_issues",
        "get_jira_issue",
        "delete_jira_issue",
    ]


def test_capability_filter_by_operation():
    manager = IntegrationManager(
        make_registry(FakeConnector())
    )

    capabilities = manager.capabilities(
        "jira",
        operation="search",
    )

    assert len(capabilities) == 1
    assert capabilities[0].name == "search_jira_issues"


def test_has_capability():
    manager = IntegrationManager(
        make_registry(FakeConnector())
    )

    assert manager.has_capability("jira", "search_jira_issues") is True
    assert manager.has_capability("jira", "missing") is False


def test_require_missing_capability():
    manager = IntegrationManager(
        make_registry(FakeConnector())
    )

    with pytest.raises(IntegrationCapabilityError):
        manager.require_capability(
            "jira",
            "missing",
        )


def test_enforce_read_only_allows_read_and_search():
    manager = IntegrationManager(
        make_registry(FakeConnector())
    )

    assert manager.enforce_read_only(
        "jira",
        "search_jira_issues",
    ).operation is CapabilityOperation.SEARCH

    assert manager.enforce_read_only(
        "jira",
        "get_jira_issue",
    ).operation is CapabilityOperation.READ


def test_enforce_read_only_blocks_delete():
    manager = IntegrationManager(
        make_registry(FakeConnector())
    )

    with pytest.raises(IntegrationPolicyError):
        manager.enforce_read_only(
            "jira",
            "delete_jira_issue",
        )


@pytest.mark.asyncio
async def test_connection_request_rejects_secret_metadata():
    with pytest.raises(ValueError):
        request(metadata={"access_token": "secret"})


@pytest.mark.asyncio
async def test_factory_exception_is_normalized():
    registry = IntegrationRegistry()

    def failing_factory(**kwargs):
        raise RuntimeError("provider implementation failure")

    registry.register(make_descriptor(), failing_factory)
    manager = IntegrationManager(registry)

    with pytest.raises(IntegrationConfigurationError) as exc_info:
        await manager.connect(request())

    assert exc_info.value.details == {
        "exception_type": "RuntimeError"
    }


@pytest.mark.asyncio
async def test_shutdown_disconnects_all_connections():
    connector_one = FakeConnector()
    connector_two = FakeConnector()
    registry = IntegrationRegistry()

    registry.register(
        make_descriptor(IntegrationProvider.JIRA),
        lambda **kwargs: connector_one,
    )
    registry.register(
        make_descriptor(IntegrationProvider.SAP),
        lambda **kwargs: connector_two,
    )

    manager = IntegrationManager(registry)

    await manager.connect(
        request(
            connection_id="jira-1",
            provider=IntegrationProvider.JIRA,
        )
    )
    await manager.connect(
        request(
            connection_id="sap-1",
            provider=IntegrationProvider.SAP,
        )
    )

    await manager.shutdown()

    assert connector_one.disconnected is True
    assert connector_two.disconnected is True
    assert manager.list_connections() == ()


def test_summaries_are_safe_and_provider_aware():
    manager = IntegrationManager(
        make_registry(FakeConnector())
    )

    # No managed connections yet.
    assert manager.list_summaries() == ()


@pytest.mark.asyncio
async def test_factory_kwargs_are_scoped_by_provider():
    received = {}

    def provider_factory(**kwargs):
        received.update(kwargs)
        return FakeConnector()

    registry = IntegrationRegistry()
    registry.register(make_descriptor(), provider_factory)

    manager = IntegrationManager(
        registry,
        connector_factory_kwargs={
            IntegrationProvider.JIRA: {
                "configured": True,
            }
        },
    )

    await manager.connect(request())

    assert received == {"configured": True}


@pytest.mark.asyncio
async def test_connector_kwargs_override_configured_defaults():
    received = {}

    def provider_factory(**kwargs):
        received.update(kwargs)
        return FakeConnector()

    registry = IntegrationRegistry()
    registry.register(make_descriptor(), provider_factory)

    manager = IntegrationManager(
        registry,
        connector_factory_kwargs={
            IntegrationProvider.JIRA: {
                "mode": "default",
            }
        },
    )

    await manager.connect(
        request(),
        connector_kwargs={"mode": "override"},
    )

    assert received["mode"] == "override"
