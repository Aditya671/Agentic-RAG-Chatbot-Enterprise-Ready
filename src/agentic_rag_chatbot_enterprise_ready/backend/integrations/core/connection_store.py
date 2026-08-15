"""Persistence boundary for non-secret integration connection state.

This module intentionally stores only ``IntegrationConnection`` snapshots.
Credentials and tokens belong to ``credential_store.py``.

Production implementations can back this protocol with PostgreSQL, Cosmos DB,
DynamoDB, SQLite, or another durable store without changing the manager's
contract. ``InMemoryConnectionStore`` is provided for local development and
regression tests.

Security invariants:
- no credential/token fields are accepted in connection metadata;
- callers can scope reads by subject and tenant;
- writes are atomic at the store boundary;
- returned objects are immutable ``IntegrationConnection`` snapshots;
- deleting connection state does not imply deleting/revoking credentials.
"""

from __future__ import annotations

from threading import RLock
from typing import Mapping, Optional, Protocol, runtime_checkable

from .integration_exceptions import (
    IntegrationConflictError,
    IntegrationNotFoundError,
    IntegrationValidationError,
)
from .integration_models import (
    IntegrationConnection,
    IntegrationProvider,
    IntegrationScope,
)


_FORBIDDEN_METADATA_KEYS = frozenset(
    {
        "access_token",
        "refresh_token",
        "client_secret",
        "password",
        "api_key",
        "authorization",
        "secret",
        "token",
    }
)


@runtime_checkable
class ConnectionStore(Protocol):
    """Provider-neutral persistence contract for non-secret connection state."""

    def create(self, connection: IntegrationConnection) -> IntegrationConnection:
        ...

    def get(self, connection_id: str) -> IntegrationConnection:
        ...

    def update(self, connection: IntegrationConnection) -> IntegrationConnection:
        ...

    def delete(self, connection_id: str) -> IntegrationConnection:
        ...

    def exists(self, connection_id: str) -> bool:
        ...

    def list(
        self,
        *,
        provider: Optional[IntegrationProvider | str] = None,
        subject_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        scope: Optional[IntegrationScope] = None,
    ) -> tuple[IntegrationConnection, ...]:
        ...


class InMemoryConnectionStore:
    """Thread-safe development/test implementation of ``ConnectionStore``."""

    def __init__(self) -> None:
        self._connections: dict[str, IntegrationConnection] = {}
        self._lock = RLock()

    def create(
        self,
        connection: IntegrationConnection,
    ) -> IntegrationConnection:
        self._validate_connection(connection)

        with self._lock:
            if connection.connection_id in self._connections:
                raise IntegrationConflictError(
                    "Connection already exists.",
                    provider=connection.provider.value,
                    connection_id=connection.connection_id,
                    operation="create_connection",
                )

            self._connections[connection.connection_id] = connection

        return connection

    def get(self, connection_id: str) -> IntegrationConnection:
        connection_id = self._validate_id(connection_id)

        with self._lock:
            connection = self._connections.get(connection_id)

        if connection is None:
            raise IntegrationNotFoundError(
                f"Connection '{connection_id}' was not found.",
                connection_id=connection_id,
                operation="get_connection",
            )

        return connection

    def update(
        self,
        connection: IntegrationConnection,
    ) -> IntegrationConnection:
        self._validate_connection(connection)

        with self._lock:
            if connection.connection_id not in self._connections:
                raise IntegrationNotFoundError(
                    f"Connection '{connection.connection_id}' was not found.",
                    provider=connection.provider.value,
                    connection_id=connection.connection_id,
                    operation="update_connection",
                )

            self._connections[connection.connection_id] = connection

        return connection

    def upsert(
        self,
        connection: IntegrationConnection,
    ) -> IntegrationConnection:
        """Create or replace a connection atomically."""
        self._validate_connection(connection)

        with self._lock:
            self._connections[connection.connection_id] = connection

        return connection

    def delete(self, connection_id: str) -> IntegrationConnection:
        connection_id = self._validate_id(connection_id)

        with self._lock:
            connection = self._connections.pop(connection_id, None)

        if connection is None:
            raise IntegrationNotFoundError(
                f"Connection '{connection_id}' was not found.",
                provider=None,
                connection_id=connection_id,
                operation="delete_connection",
            )

        return connection

    def exists(self, connection_id: str) -> bool:
        connection_id = self._validate_id(connection_id)

        with self._lock:
            return connection_id in self._connections

    def list(
        self,
        *,
        provider: Optional[IntegrationProvider | str] = None,
        subject_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        scope: Optional[IntegrationScope] = None,
    ) -> tuple[IntegrationConnection, ...]:
        normalized_provider = self._normalize_provider(provider)

        if subject_id is not None and not subject_id.strip():
            raise IntegrationValidationError(
                "subject_id cannot be blank.",
                operation="list_connections",
            )

        if tenant_id is not None and not tenant_id.strip():
            raise IntegrationValidationError(
                "tenant_id cannot be blank.",
                operation="list_connections",
            )

        with self._lock:
            connections = tuple(self._connections.values())

        result = []
        for connection in connections:
            if normalized_provider is not None:
                if connection.provider != normalized_provider:
                    continue

            if subject_id is not None:
                if connection.identity.subject_id != subject_id:
                    continue

            if tenant_id is not None:
                if connection.identity.tenant_id != tenant_id:
                    continue

            if scope is not None and connection.identity.scope != scope:
                continue

            result.append(connection)

        return tuple(
            sorted(
                result,
                key=lambda item: item.connection_id,
            )
        )

    def clear(self) -> None:
        """Clear all state. Intended for test teardown/local development."""
        with self._lock:
            self._connections.clear()

    @staticmethod
    def _validate_id(connection_id: str) -> str:
        if not isinstance(connection_id, str) or not connection_id.strip():
            raise IntegrationValidationError(
                "connection_id is required.",
                operation="connection_store",
            )
        return connection_id.strip()

    @classmethod
    def _validate_connection(
        cls,
        connection: IntegrationConnection,
    ) -> None:
        if not isinstance(connection, IntegrationConnection):
            raise IntegrationValidationError(
                "connection must be an IntegrationConnection.",
                operation="connection_store",
            )

        forbidden = _FORBIDDEN_METADATA_KEYS.intersection(
            connection.metadata.keys()
        )
        if forbidden:
            raise IntegrationValidationError(
                "Connection metadata must not contain credential fields.",
                provider=connection.provider.value,
                connection_id=connection.connection_id,
                operation="validate_connection",
                details={"fields": sorted(forbidden)},
            )

    @staticmethod
    def _normalize_provider(
        provider: Optional[IntegrationProvider | str],
    ) -> Optional[IntegrationProvider]:
        if provider is None:
            return None

        if isinstance(provider, IntegrationProvider):
            return provider

        if isinstance(provider, str):
            try:
                return IntegrationProvider.from_value(provider)
            except ValueError as exc:
                raise IntegrationValidationError(
                    f"Unsupported integration provider: {provider!r}.",
                    operation="list_connections",
                ) from exc

        raise IntegrationValidationError(
            "provider must be an IntegrationProvider or string.",
            operation="list_connections",
        )
