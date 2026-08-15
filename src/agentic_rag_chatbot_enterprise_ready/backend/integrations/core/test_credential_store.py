"""Regression tests for the enterprise secret-store boundary."""

from datetime import datetime, timedelta, timezone

import pytest

from backend.integration.credential_store import (
    InMemorySecretStore,
    SecretReference,
    SecretStore,
)


def test_in_memory_store_implements_secret_store_protocol():
    store = InMemorySecretStore()

    assert isinstance(store, SecretStore)


def test_put_and_get_secret():
    store = InMemorySecretStore()

    reference = store.put_secret(
        owner_id="user-1",
        secret="oauth-secret",
    )

    assert reference.reference_id
    assert reference.owner_id == "user-1"
    assert store.get_secret(reference, owner_id="user-1") == "oauth-secret"


def test_bytes_are_supported_and_copied():
    store = InMemorySecretStore()
    original = b"binary-secret"

    reference = store.put_secret(
        owner_id="user-1",
        secret=original,
    )

    result = store.get_secret(reference, owner_id="user-1")

    assert result == original
    assert isinstance(result, bytes)


def test_empty_secret_is_rejected():
    store = InMemorySecretStore()

    with pytest.raises(ValueError):
        store.put_secret(owner_id="user-1", secret="")


def test_invalid_secret_type_is_rejected():
    store = InMemorySecretStore()

    with pytest.raises(TypeError):
        store.put_secret(owner_id="user-1", secret=123)


def test_empty_owner_is_rejected():
    store = InMemorySecretStore()

    with pytest.raises(ValueError):
        store.put_secret(owner_id="", secret="secret")


def test_secret_reference_requires_timezone_aware_created_at():
    with pytest.raises(ValueError):
        SecretReference(
            reference_id="ref-1",
            owner_id="user-1",
            created_at=datetime(2026, 8, 8, 12, 0, 0),
        )


def test_secret_reference_expiry_must_be_after_creation():
    created = datetime.now(timezone.utc)

    with pytest.raises(ValueError):
        SecretReference(
            reference_id="ref-1",
            owner_id="user-1",
            created_at=created,
            expires_at=created,
        )


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
def test_reference_metadata_cannot_contain_secret_fields(field):
    with pytest.raises(ValueError):
        SecretReference(
            reference_id="ref-1",
            owner_id="user-1",
            created_at=datetime.now(timezone.utc),
            metadata={field: "do-not-store-here"},
        )


def test_owner_isolation_blocks_cross_user_read():
    store = InMemorySecretStore()
    reference = store.put_secret(
        owner_id="user-1",
        secret="private",
    )

    with pytest.raises(PermissionError):
        store.get_secret(reference, owner_id="user-2")


def test_owner_isolation_blocks_cross_user_delete():
    store = InMemorySecretStore()
    reference = store.put_secret(
        owner_id="user-1",
        secret="private",
    )

    with pytest.raises(PermissionError):
        store.delete_secret(reference, owner_id="user-2")


def test_owner_isolation_blocks_cross_user_exists():
    store = InMemorySecretStore()
    reference = store.put_secret(
        owner_id="user-1",
        secret="private",
    )

    with pytest.raises(PermissionError):
        store.exists(reference, owner_id="user-2")


def test_delete_removes_secret():
    store = InMemorySecretStore()
    reference = store.put_secret(
        owner_id="user-1",
        secret="private",
    )

    store.delete_secret(reference, owner_id="user-1")

    assert store.exists(reference, owner_id="user-1") is False

    with pytest.raises(KeyError):
        store.get_secret(reference, owner_id="user-1")


def test_missing_reference_raises_on_get():
    store = InMemorySecretStore()
    reference = SecretReference(
        reference_id="missing",
        owner_id="user-1",
        created_at=datetime.now(timezone.utc),
    )

    with pytest.raises(KeyError):
        store.get_secret(reference, owner_id="user-1")


def test_missing_reference_raises_on_delete():
    store = InMemorySecretStore()
    reference = SecretReference(
        reference_id="missing",
        owner_id="user-1",
        created_at=datetime.now(timezone.utc),
    )

    with pytest.raises(KeyError):
        store.delete_secret(reference, owner_id="user-1")


def test_expired_secret_is_unavailable():
    store = InMemorySecretStore()
    reference = store.put_secret(
        owner_id="user-1",
        secret="temporary",
        expires_at=datetime.now(timezone.utc) + timedelta(milliseconds=1),
    )

    import time
    time.sleep(0.01)

    assert reference.expired is True
    assert store.exists(reference, owner_id="user-1") is False

    with pytest.raises(KeyError):
        store.get_secret(reference, owner_id="user-1")


def test_non_expired_secret_is_available():
    store = InMemorySecretStore()
    reference = store.put_secret(
        owner_id="user-1",
        secret="temporary",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )

    assert reference.expired is False
    assert store.exists(reference, owner_id="user-1") is True


def test_metadata_is_copied():
    store = InMemorySecretStore()
    metadata = {"purpose": "jira-oauth"}

    reference = store.put_secret(
        owner_id="user-1",
        secret="secret",
        metadata=metadata,
    )

    metadata["purpose"] = "changed"

    assert reference.metadata["purpose"] == "jira-oauth"


def test_reference_contains_no_secret_value():
    store = InMemorySecretStore()
    reference = store.put_secret(
        owner_id="user-1",
        secret="super-secret-value",
    )

    representation = repr(reference)

    assert "super-secret-value" not in representation
    assert "super-secret-value" not in str(reference)


def test_clear_removes_all_test_secrets():
    store = InMemorySecretStore()

    reference = store.put_secret(
        owner_id="user-1",
        secret="secret",
    )

    store.clear()

    assert store.exists(reference, owner_id="user-1") is False


def test_reference_expired_property_without_expiry():
    reference = SecretReference(
        reference_id="ref-1",
        owner_id="user-1",
        created_at=datetime.now(timezone.utc),
    )

    assert reference.expired is False
