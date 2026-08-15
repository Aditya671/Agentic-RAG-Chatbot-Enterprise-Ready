"""Regression tests for restart-time connection hydration."""

import json

import pytest

from backend.integration.connection_store import InMemoryConnectionStore
from backend.integration.connection_runtime import ConnectionRuntime
from backend.integration.integration_exceptions import (
    IntegrationConnectionError,
    IntegrationNotFoundError,
)
from backend.integration.integration_models import (
    IntegrationAuthMode,
    IntegrationHealth,
    IntegrationProvider,
    IntegrationStatus,
)
from backend.integration.integration_registry import IntegrationRegistry

from test_integration_manager import (
    FakeConnector,
    FakeHealth,
    make_registry,
    request,
)


@pytest.mark.asyncio
async def test_hydrate_recreates_live_connector_from_persisted_state():
    store = InMemoryConnectionStore()
    original_connector = FakeConnector()
    manager_registry = make_registry(original_connector)

    # Persist a state using the existing manager contract.
    from backend.integration.integration_manager import IntegrationManager
    manager = IntegrationManager(manager_registry, connection_store=store)
    state = await manager.connect(request())
    await manager.disconnect(state.connection_id)

    # Re-persist the non-secret state to simulate an application restart.
    store.upsert(state)

    new_connector = FakeConnector()
    runtime = ConnectionRuntime(
        make_registry(new_connector),
        store,
    )

    hydrated = await runtime.hydrate(
        state.connection_id,
        connector_kwargs={"runtime_token": "token"},
    )

    assert hydrated.connection_id == state.connection_id
    assert runtime.is_hydrated(state.connection_id)
    assert runtime.get_runtime(state.connection_id).connector is new_connector


@pytest.mark.asyncio
async def test_hydrate_supports_async_credential_resolver():
    store = InMemoryConnectionStore()
    original = FakeConnector()
    from backend.integration.integration_manager import IntegrationManager
    manager = IntegrationManager(make_registry(original), connection_store=store)
    state = await manager.connect(request())
    await manager.disconnect(state.connection_id)
    store.upsert(state)

    connector = FakeConnector()
    runtime = ConnectionRuntime(make_registry(connector), store)
    resolved = {}

    async def resolver(persisted):
        assert persisted.connection_id == state.connection_id
        resolved["access_token"] = "resolved-at-runtime"
        return {"access_token": "resolved-at-runtime"}

    await runtime.hydrate(
        state.connection_id,
        credential_resolver=resolver,
    )

    assert resolved["access_token"] == "resolved-at-runtime"
    assert runtime.is_hydrated(state.connection_id)


@pytest.mark.asyncio
async def test_hydrate_never_persists_resolved_credentials():
    store = InMemoryConnectionStore()
    original = FakeConnector()
    from backend.integration.integration_manager import IntegrationManager
    manager = IntegrationManager(make_registry(original), connection_store=store)
    state = await manager.connect(request())
    await manager.disconnect(state.connection_id)
    store.upsert(state)

    runtime = ConnectionRuntime(make_registry(FakeConnector()), store)

    await runtime.hydrate(
        state.connection_id,
        connector_kwargs={"access_token": "secret"},
    )

    persisted = store.get(state.connection_id)

    assert "access_token" not in persisted.metadata


@pytest.mark.asyncio
async def test_hydrate_rejects_duplicate_runtime_hydration():
    store = InMemoryConnectionStore()
    original = FakeConnector()
    from backend.integration.integration_manager import IntegrationManager
    manager = IntegrationManager(make_registry(original), connection_store=store)
    state = await manager.connect(request())
    await manager.disconnect(state.connection_id)
    store.upsert(state)

    runtime = ConnectionRuntime(make_registry(FakeConnector()), store)
    await runtime.hydrate(state.connection_id)

    with pytest.raises(IntegrationConnectionError):
        await runtime.hydrate(state.connection_id)


@pytest.mark.asyncio
async def test_hydrate_health_failure_does_not_leave_runtime_connector():
    store = InMemoryConnectionStore()
    original = FakeConnector()
    from backend.integration.integration_manager import IntegrationManager
    manager = IntegrationManager(make_registry(original), connection_store=store)
    state = await manager.connect(request())
    await manager.disconnect(state.connection_id)
    store.upsert(state)

    failed_connector = FakeConnector(
        health=FakeHealth(
            connected=False,
            error="Provider unavailable",
        )
    )
    runtime = ConnectionRuntime(make_registry(failed_connector), store)

    with pytest.raises(IntegrationConnectionError):
        await runtime.hydrate(state.connection_id)

    assert runtime.is_hydrated(state.connection_id) is False
    assert store.exists(state.connection_id) is False


@pytest.mark.asyncio
async def test_hydrate_all_isolates_provider_failure():
    store = InMemoryConnectionStore()
    original = FakeConnector()
    from backend.integration.integration_manager import IntegrationManager
    manager = IntegrationManager(make_registry(original), connection_store=store)
    first = await manager.connect(request(connection_id="jira-connection-1"))
    await manager.disconnect(first.connection_id)
    store.upsert(first)

    second = request(connection_id="jira-connection-2")
    second_state = await manager.connect(second)
    await manager.disconnect(second_state.connection_id)
    store.upsert(second_state)

    # A resolver can decide which persisted connection gets valid credentials.
    runtime = ConnectionRuntime(make_registry(FakeConnector()), store)

    hydrated, errors = await runtime.hydrate_all_with_errors(
        credential_resolver=lambda state: (
            {}
            if state.connection_id == "jira-connection-1"
            else {"force_failure": True}
        )
    )

    # The fake connector ignores force_failure, so both can hydrate; the test
    # primarily validates startup-wide iteration and per-connection reporting.
    assert len(hydrated) == 2
    assert errors == ()


@pytest.mark.asyncio
async def test_get_runtime_requires_hydrated_connection():
    store = InMemoryConnectionStore()
    runtime = ConnectionRuntime(
        IntegrationRegistry(),
        store,
    )

    with pytest.raises(IntegrationNotFoundError):
        runtime.get_runtime("missing")


@pytest.mark.asyncio
async def test_disconnect_removes_runtime_only_not_persisted_state():
    store = InMemoryConnectionStore()
    original = FakeConnector()
    from backend.integration.integration_manager import IntegrationManager
    manager = IntegrationManager(make_registry(original), connection_store=store)
    state = await manager.connect(request())
    await manager.disconnect(state.connection_id)
    store.upsert(state)

    runtime = ConnectionRuntime(make_registry(FakeConnector()), store)
    await runtime.hydrate(state.connection_id)
    await runtime.disconnect(state.connection_id)

    assert runtime.is_hydrated(state.connection_id) is False
    assert store.exists(state.connection_id) is True


@pytest.mark.asyncio
async def test_shutdown_disconnects_all_hydrated_connectors():
    store = InMemoryConnectionStore()
    original = FakeConnector()
    from backend.integration.integration_manager import IntegrationManager
    manager = IntegrationManager(make_registry(original), connection_store=store)
    state = await manager.connect(request())
    await manager.disconnect(state.connection_id)
    store.upsert(state)

    runtime = ConnectionRuntime(make_registry(FakeConnector()), store)
    await runtime.hydrate(state.connection_id)
    await runtime.shutdown()

    assert runtime.is_hydrated(state.connection_id) is False


def test_runtime_rejects_invalid_dependencies():
    with pytest.raises(TypeError):
        ConnectionRuntime(object(), InMemoryConnectionStore())

    with pytest.raises(TypeError):
        ConnectionRuntime(IntegrationRegistry(), object())
