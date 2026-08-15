"""Credential/secret-store boundary for enterprise integrations.

This module deliberately separates secret material from IntegrationManager,
IntegrationConnection, IntegrationRegistry, logs, and API models.

The production application should implement ``SecretStore`` with an approved
enterprise secret manager (for example Azure Key Vault, AWS Secrets Manager,
HashiCorp Vault, or an equivalent platform service). The included
``InMemorySecretStore`` exists only for local development and deterministic
tests; it is NOT a production secret store.

Security rules:
- callers receive an opaque secret reference rather than embedding secrets in
  integration connection metadata;
- secret values are never included in ``SecretReference``;
- secret identifiers are validated;
- the in-memory implementation copies mutable byte values;
- deletion is explicit;
- implementations should avoid logging values and should apply provider-side
  encryption, access control, rotation, and audit policies.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from secrets import token_urlsafe
from threading import RLock
from typing import Dict, Mapping, Optional, Protocol, runtime_checkable


_FORBIDDEN_REFERENCE_FIELDS = {
    "access_token",
    "refresh_token",
    "client_secret",
    "password",
    "api_key",
    "authorization",
    "secret",
    "token",
}


@dataclass(frozen=True)
class SecretReference:
    """Opaque reference to secret material stored outside application models."""

    reference_id: str
    owner_id: str
    created_at: datetime
    expires_at: Optional[datetime] = None
    metadata: Mapping[str, str] = None

    def __post_init__(self) -> None:
        if not self.reference_id.strip():
            raise ValueError("reference_id is required.")
        if not self.owner_id.strip():
            raise ValueError("owner_id is required.")

        if self.created_at.tzinfo is None:
            raise ValueError("created_at must be timezone-aware.")

        if self.expires_at is not None:
            if self.expires_at.tzinfo is None:
                raise ValueError("expires_at must be timezone-aware.")
            if self.expires_at <= self.created_at:
                raise ValueError("expires_at must be after created_at.")

        metadata = dict(self.metadata or {})
        if _FORBIDDEN_REFERENCE_FIELDS.intersection(metadata):
            raise ValueError(
                "SecretReference metadata must not contain secret values."
            )

        object.__setattr__(self, "metadata", metadata)

    @property
    def expired(self) -> bool:
        return (
            self.expires_at is not None
            and datetime.now(timezone.utc) >= self.expires_at
        )


@runtime_checkable
class SecretStore(Protocol):
    """Provider-neutral secret storage contract."""

    def put_secret(
        self,
        *,
        owner_id: str,
        secret: str | bytes,
        metadata: Optional[Mapping[str, str]] = None,
        expires_at: Optional[datetime] = None,
    ) -> SecretReference:
        ...

    def get_secret(
        self,
        reference: SecretReference,
        *,
        owner_id: str,
    ) -> str | bytes:
        ...

    def delete_secret(
        self,
        reference: SecretReference,
        *,
        owner_id: str,
    ) -> None:
        ...

    def exists(
        self,
        reference: SecretReference,
        *,
        owner_id: str,
    ) -> bool:
        ...


class InMemorySecretStore:
    """Development/test-only implementation of ``SecretStore``.

    Do not use this class for production credentials. Process memory is not an
    enterprise secret boundary: values disappear on restart and remain
    potentially observable through process memory/debugging.
    """

    def __init__(self) -> None:
        self._secrets: Dict[str, tuple[str, str | bytes, SecretReference]] = {}
        self._lock = RLock()

    def put_secret(
        self,
        *,
        owner_id: str,
        secret: str | bytes,
        metadata: Optional[Mapping[str, str]] = None,
        expires_at: Optional[datetime] = None,
    ) -> SecretReference:
        owner_id = self._validate_owner(owner_id)
        if not isinstance(secret, (str, bytes)):
            raise TypeError("secret must be str or bytes.")
        if isinstance(secret, str) and not secret:
            raise ValueError("secret cannot be empty.")
        if isinstance(secret, bytes) and not secret:
            raise ValueError("secret cannot be empty.")

        created_at = datetime.now(timezone.utc)
        reference = SecretReference(
            reference_id=token_urlsafe(32),
            owner_id=owner_id,
            created_at=created_at,
            expires_at=expires_at,
            metadata=metadata or {},
        )

        # Store a defensive copy for bytes so the caller's mutable bytearray
        # conversions cannot mutate our stored value.
        stored_secret = bytes(secret) if isinstance(secret, bytes) else secret

        with self._lock:
            self._secrets[reference.reference_id] = (
                owner_id,
                stored_secret,
                reference,
            )

        return reference

    def get_secret(
        self,
        reference: SecretReference,
        *,
        owner_id: str,
    ) -> str | bytes:
        self._validate_reference(reference)
        owner_id = self._validate_owner(owner_id)
        self._authorize(reference, owner_id)

        with self._lock:
            record = self._secrets.get(reference.reference_id)

        if record is None:
            raise KeyError("Secret reference does not exist.")

        _, secret, stored_reference = record

        if stored_reference.expired:
            self._delete_without_authorization(reference.reference_id)
            raise KeyError("Secret reference has expired.")

        return bytes(secret) if isinstance(secret, bytes) else secret

    def delete_secret(
        self,
        reference: SecretReference,
        *,
        owner_id: str,
    ) -> None:
        self._validate_reference(reference)
        owner_id = self._validate_owner(owner_id)
        self._authorize(reference, owner_id)

        with self._lock:
            if reference.reference_id not in self._secrets:
                raise KeyError("Secret reference does not exist.")
            del self._secrets[reference.reference_id]

    def exists(
        self,
        reference: SecretReference,
        *,
        owner_id: str,
    ) -> bool:
        self._validate_reference(reference)
        owner_id = self._validate_owner(owner_id)
        self._authorize(reference, owner_id)

        with self._lock:
            record = self._secrets.get(reference.reference_id)

        if record is None:
            return False

        if record[2].expired:
            self._delete_without_authorization(reference.reference_id)
            return False

        return True

    def clear(self) -> None:
        """Remove all in-memory secrets. Intended for test teardown only."""
        with self._lock:
            self._secrets.clear()

    @staticmethod
    def _validate_owner(owner_id: str) -> str:
        if not isinstance(owner_id, str) or not owner_id.strip():
            raise ValueError("owner_id is required.")
        return owner_id.strip()

    @staticmethod
    def _validate_reference(reference: SecretReference) -> None:
        if not isinstance(reference, SecretReference):
            raise TypeError("reference must be a SecretReference.")

    @staticmethod
    def _authorize(reference: SecretReference, owner_id: str) -> None:
        if reference.owner_id != owner_id:
            raise PermissionError("Secret reference is not owned by this subject.")

    def _delete_without_authorization(self, reference_id: str) -> None:
        with self._lock:
            self._secrets.pop(reference_id, None)
