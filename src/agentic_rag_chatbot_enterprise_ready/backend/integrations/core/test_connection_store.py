"""Regression tests for the non-secret integration connection store."""

from datetime import datetime, timedelta, timezone

import pytest

from backend.integration.connection_store import (
    ConnectionStore,
    InMemoryConnectionStore,
)
from backend.integration.integration_exceptions import (
    IntegrationConflictError,
    IntegrationNotFoundError,
    IntegrationValidationError,
)
from backend.integration.integration_models import (
    IntegrationAuthMode,
    IntegrationConnection,
    IntegrationIdentity,
    IntegrationProvider,
    IntegrationScope,
    IntegrationStatus,
)


def make_connection(
    connection_id: str = "jira-1",
    *,
    provider: IntegrationProvider = IntegrationProvider.JIRA,
    subject_id: str = "user-1",
    tenant_id: str | None = None,
    scope: IntegrationScope = IntegrationScope.USER,
    status: IntegrationStatus = IntegrationStatus.CONNECTED,
    metadata=None,
):
    return IntegrationConnection(
        connection_id=connection_id,
        provider=provider,
        identity=IntegrationIdentity(
            subject_id=subject_id,
            scope=scope,
            tenant_id=tenant_id,
            display_name="Example User",
            provider_account_id="provider-account-1",
        ),
        status=status,
        auth_mode=IntegrationAuthMode.OAUTH2,
        endpoint="https://example.test",
        provider_resource_id="resource-1",
        provider_resource_name="Example Resource",
        metadata=metadata or {},
    )


def test_store_implements_protocol():
    assert isinstance(InMemoryConnectionStore(), ConnectionStore)


def test_create_and_get():
    store = InMemoryConnectionStore()
    connection = make_connection()

    assert store.create(connection) == connection
    assert store.get("jira-1") == connection


def test_create_duplicate_is_rejected():
    store = InMemoryConnectionStore()
    connection = make_connection()

    store.create(connection)

    with pytest.raises(IntegrationConflictError):
        store.create(connection)


def test_get_missing_connection_raises():
    store = InMemoryConnectionStore()

    with pytest.raises(IntegrationNotFoundError):
        store.get("missing")


def test_update_existing_connection():
    store = InMemoryConnectionStore()
    original = make_connection(status=IntegrationStatus.CONNECTING)
    updated = make_connection(status=IntegrationStatus.CONNECTED)

    store.create(original)
    result = store.update(updated)

    assert result.status is IntegrationStatus.CONNECTED
    assert store.get("jira-1").status is IntegrationStatus.CONNECTED


def test_update_missing_connection_raises():
    store = InMemoryConnectionStore()

    with pytest.raises(IntegrationNotFoundError):
        store.update(make_connection())


def test_upsert_creates_new_connection():
    store = InMemoryConnectionStore()
    connection = make_connection()

    assert store.upsert(connection) == connection
    assert store.exists("jira-1")


def test_upsert_replaces_existing_connection():
    store = InMemoryConnectionStore()
    first = make_connection(status=IntegrationStatus.CONNECTING)
    second = make_connection(status=IntegrationStatus.CONNECTED)

    store.upsert(first)
    store.upsert(second)

    assert store.get("jira-1").status is IntegrationStatus.CONNECTED


def test_delete_returns_deleted_connection():
    store = InMemoryConnectionStore()
    connection = make_connection()

    store.create(connection)
    deleted = store.delete("jira-1")

    assert deleted == connection
    assert store.exists("jira-1") is False


def test_delete_missing_connection_raises():
    store = InMemoryConnectionStore()

    with pytest.raises(IntegrationNotFoundError):
        store.delete("missing")


def test_exists_for_blank_id_is_rejected():
    store = InMemoryConnectionStore()

    with pytest.raises(IntegrationValidationError):
        store.exists(" ")


def test_create_rejects_non_connection():
    store = InMemoryConnectionStore()

    with pytest.raises(IntegrationValidationError):
        store.create(object())


@pytest.mark.parametrize(
    "field",
    [
        "access_token",
        "refresh_token",
        "client_secret",
        "password",
        "api_key",
        "authorization",
        "secret",
        "token",
    ],
)
def test_connection_metadata_rejects_secret_fields(field):
    store = InMemoryConnectionStore()

    connection = make_connection(
        metadata={field: "must-not-be-stored"},
    )

    with pytest.raises(IntegrationValidationError):
        store.create(connection)


def test_list_returns_deterministically_sorted_connections():
    store = InMemoryConnectionStore()

    store.create(make_connection("jira-2"))
    store.create(make_connection("jira-1"))

    assert [item.connection_id for item in store.list()] == [
        "jira-1",
        "jira-2",
    ]


def test_list_filters_by_provider():
    store = InMemoryConnectionStore()

    store.create(make_connection("jira-1"))
    store.create(
        make_connection(
            "sap-1",
            provider=IntegrationProvider.SAP,
        )
    )

    result = store.list(provider="sap")

    assert [item.connection_id for item in result] == ["sap-1"]


def test_list_filters_by_subject():
    store = InMemoryConnectionStore()

    store.create(make_connection("jira-user-1", subject_id="user-1"))
    store.create(make_connection("jira-user-2", subject_id="user-2"))

    result = store.list(subject_id="user-2")

    assert [item.connection_id for item in result] == ["jira-user-2"]


def test_list_filters_by_tenant():
    store = InMemoryConnectionStore()

    store.create(
        make_connection(
            "tenant-a",
            scope=IntegrationScope.TENANT,
            tenant_id="tenant-a",
        )
    )
    store.create(
        make_connection(
            "tenant-b",
            scope=IntegrationScope.TENANT,
            tenant_id="tenant-b",
        )
    )

    result = store.list(tenant_id="tenant-b")

    assert [item.connection_id for item in result] == ["tenant-b"]


def test_list_filters_by_scope():
    store = InMemoryConnectionStore()

    store.create(make_connection("user-connection"))

    store.create(
        make_connection(
            "tenant-connection",
            scope=IntegrationScope.TENANT,
            tenant_id="tenant-1",
        )
    )

    result = store.list(scope=IntegrationScope.TENANT)

    assert [item.connection_id for item in result] == ["tenant-connection"]


def test_list_supports_combined_filters():
    store = InMemoryConnectionStore()

    store.create(
        make_connection(
            "user-jira",
            subject_id="user-1",
        )
    )
    store.create(
        make_connection(
            "user-sap",
            provider=IntegrationProvider.SAP,
            subject_id="user-1",
        )
    )
    store.create(
        make_connection(
            "other-user-jira",
            subject_id="user-2",
        )
    )

    result = store.list(
        provider=IntegrationProvider.JIRA,
        subject_id="user-1",
    )

    assert [item.connection_id for item in result] == ["user-jira"]


def test_invalid_provider_filter_is_rejected():
    store = InMemoryConnectionStore()

    with pytest.raises(IntegrationValidationError):
        store.list(provider="unknown")


def test_blank_subject_filter_is_rejected():
    store = InMemoryConnectionStore()

    with pytest.raises(IntegrationValidationError):
        store.list(subject_id=" ")


def test_blank_tenant_filter_is_rejected():
    store = InMemoryConnectionStore()

    with pytest.raises(IntegrationValidationError):
        store.list(tenant_id=" ")


def test_clear_removes_all_connections():
    store = InMemoryConnectionStore()

    store.create(make_connection("jira-1"))
    store.create(make_connection("jira-2"))

    store.clear()

    assert store.list() == ()


def test_connection_store_does_not_store_credentials():
    store = InMemoryConnectionStore()
    connection = make_connection(
        metadata={"purpose": "enterprise-access"},
    )

    store.create(connection)

    persisted = store.get("jira-1")

    assert persisted.metadata == {"purpose": "enterprise-access"}
    assert "access_token" not in persisted.metadata


def test_connection_snapshot_is_immutable():
    store = InMemoryConnectionStore()
    connection = make_connection()

    store.create(connection)

    with pytest.raises(Exception):
        connection.status = IntegrationStatus.ERROR


def test_connection_timestamps_are_preserved():
    created = datetime.now(timezone.utc) - timedelta(hours=1)
    updated = datetime.now(timezone.utc)

    connection = IntegrationConnection(
        connection_id="jira-time",
        provider=IntegrationProvider.JIRA,
        identity=IntegrationIdentity(
            subject_id="user-1",
            scope=IntegrationScope.USER,
        ),
        created_at=created,
        updated_at=updated,
    )

    store = InMemoryConnectionStore()
    store.create(connection)

    persisted = store.get("jira-time")

    assert persisted.created_at == created
    assert persisted.updated_at == updated
