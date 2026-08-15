"""Runtime hydration for persisted enterprise integration connections.

``ConnectionStore`` persists non-secret connection state, while provider
connectors are process-local runtime objects. After an application restart,
the persisted state therefore needs to be rehydrated into live connectors.

This module owns that boundary without putting credentials into
``IntegrationConnection``. A caller supplies a credential/connector-argument
resolver for each persisted connection. The resolver may retrieve an opaque
secret reference from an external mapping and use ``ProviderAdapter`` to
produce the connector arguments.

The runtime keeps live connector instances in memory only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Mapping, Optional

from .connection_store import ConnectionStore
from .integration_exceptions import (
    IntegrationConnectionError,
    IntegrationError,
    IntegrationNotFoundError,
)
from .integration_models import (
    IntegrationConnection,
    IntegrationHealth,
    IntegrationStatus,
    utc_now,
)
from .integration_registry import IntegrationRegistry


class ConnectorRuntimeProtocol:
    """Minimal connector lifecycle contract."""

    async def health_check(self) -> Any:
        ...

    def disconnect(self) -> None:
        ...


CredentialResolver = Callable[
    [IntegrationConnection],
    Mapping[str, Any] | Awaitable[Mapping[str, Any]],
]


@dataclass
class HydratedConnection:
    """Runtime connector paired with its persisted non-secret state."""

    state: IntegrationConnection
    connector: ConnectorRuntimeProtocol


class ConnectionRuntime:
    """Rehydrate persisted connections into live provider connectors."""

    def __init__(
        self,
        registry: IntegrationRegistry,
        connection_store: ConnectionStore,
    ) -> None:
        if not isinstance(registry, IntegrationRegistry):
            raise TypeError("registry must be an IntegrationRegistry.")

        if not isinstance(connection_store, ConnectionStore):
            raise TypeError("connection_store must implement ConnectionStore.")

        self.registry = registry
        self.connection_store = connection_store
        self._runtime: dict[str, HydratedConnection] = {}

    async def hydrate(
        self,
        connection_id: str,
        *,
        credential_resolver: Optional[CredentialResolver] = None,
        connector_kwargs: Optional[Mapping[str, Any]] = None,
    ) -> IntegrationConnection:
        """Recreate and health-check one persisted connection.

        ``credential_resolver`` is preferred for production because it keeps
        secret retrieval outside persisted connection state. Direct
        ``connector_kwargs`` is supported for already-resolved runtime inputs
        and deterministic tests.

        The hydrated connector is not considered usable until its health
        check succeeds.
        """
        persisted = self.connection_store.get(connection_id)

        if connection_id in self._runtime:
            raise IntegrationConnectionError(
                "Connection is already hydrated in this process.",
                provider=persisted.provider.value,
                connection_id=connection_id,
                operation="hydrate",
            )

        kwargs = dict(connector_kwargs or {})

        if credential_resolver is not None:
            resolved = credential_resolver(persisted)
            if hasattr(resolved, "__await__"):
                resolved = await resolved
            if not isinstance(resolved, Mapping):
                raise IntegrationConnectionError(
                    "Credential resolver must return a mapping.",
                    provider=persisted.provider.value,
                    connection_id=connection_id,
                    operation="hydrate",
                )
            kwargs.update(resolved)

        try:
            connector = self.registry.create_connector(
                persisted.provider,
                **kwargs,
            )
        except IntegrationError:
            raise
        except Exception as exc:
            raise IntegrationConnectionError(
                "Persisted integration could not be rehydrated.",
                provider=persisted.provider.value,
                connection_id=connection_id,
                operation="hydrate",
                details={"exception_type": type(exc).__name__},
            ) from exc

        disconnect = getattr(connector, "disconnect", None)
        health_check = getattr(connector, "health_check", None)

        if not callable(health_check) or not callable(disconnect):
            self._safe_disconnect(connector)
            raise IntegrationConnectionError(
                "Registered connector does not implement the runtime lifecycle contract.",
                provider=persisted.provider.value,
                connection_id=connection_id,
                operation="hydrate",
            )

        try:
            health = await self._health(connector)
        except IntegrationError:
            self._safe_disconnect(connector)
            raise
        except Exception as exc:
            self._safe_disconnect(connector)
            raise IntegrationConnectionError(
                "Rehydrated connector health check failed.",
                provider=persisted.provider.value,
                connection_id=connection_id,
                operation="hydrate",
                details={"exception_type": type(exc).__name__},
            ) from exc

        updated = persisted.with_health(health)

        if updated.status in {
            IntegrationStatus.ERROR,
            IntegrationStatus.DISCONNECTED,
            IntegrationStatus.REVOKED,
        }:
            self._safe_disconnect(connector)
            self._delete_persisted_state(connection_id)
            raise IntegrationConnectionError(
                health.message or "Persisted integration is no longer healthy.",
                provider=persisted.provider.value,
                connection_id=connection_id,
                operation="hydrate",
                details={"status": health.status.value},
            )

        try:
            self.connection_store.update(updated)
        except Exception as exc:
            self._safe_disconnect(connector)
            raise IntegrationConnectionError(
                "Rehydrated connection state could not be persisted.",
                provider=persisted.provider.value,
                connection_id=connection_id,
                operation="hydrate",
                details={"exception_type": type(exc).__name__},
            ) from exc

        self._runtime[connection_id] = HydratedConnection(
            state=updated,
            connector=connector,
        )
        return updated

    async def hydrate_all(
        self,
        *,
        credential_resolver: Optional[CredentialResolver] = None,
    ) -> tuple[IntegrationConnection, ...]:
        """Best-effort hydrate every persisted connection.

        A failed connection is skipped and its failure is returned to the
        caller through ``errors`` in ``hydrate_all_with_errors``. This method
        is intentionally convenient for startup where one unavailable
        enterprise system must not prevent unrelated integrations from loading.
        """
        states = self.connection_store.list()
        hydrated: list[IntegrationConnection] = []

        for state in states:
            try:
                hydrated.append(
                    await self.hydrate(
                        state.connection_id,
                        credential_resolver=credential_resolver,
                    )
                )
            except IntegrationError:
                continue

        return tuple(hydrated)

    async def hydrate_all_with_errors(
        self,
        *,
        credential_resolver: Optional[CredentialResolver] = None,
    ) -> tuple[tuple[IntegrationConnection, ...], tuple[IntegrationError, ...]]:
        """Hydrate all persisted connections while preserving per-connection errors."""
        states = self.connection_store.list()
        hydrated: list[IntegrationConnection] = []
        errors: list[IntegrationError] = []

        for state in states:
            try:
                hydrated.append(
                    await self.hydrate(
                        state.connection_id,
                        credential_resolver=credential_resolver,
                    )
                )
            except IntegrationError as exc:
                errors.append(exc)

        return tuple(hydrated), tuple(errors)

    def get_runtime(self, connection_id: str) -> HydratedConnection:
        runtime = self._runtime.get(connection_id)
        if runtime is None:
            raise IntegrationNotFoundError(
                f"Connection '{connection_id}' is not hydrated in this process.",
                connection_id=connection_id,
                operation="get_runtime",
            )
        return runtime

    def is_hydrated(self, connection_id: str) -> bool:
        return connection_id in self._runtime

    async def disconnect(self, connection_id: str) -> None:
        runtime = self.get_runtime(connection_id)

        try:
            runtime.connector.disconnect()
        except Exception as exc:
            raise IntegrationConnectionError(
                "Hydrated connector could not be disconnected cleanly.",
                provider=runtime.state.provider.value,
                connection_id=connection_id,
                operation="disconnect_runtime",
                details={"exception_type": type(exc).__name__},
            ) from exc
        finally:
            self._runtime.pop(connection_id, None)

    async def shutdown(self) -> None:
        connection_ids = tuple(self._runtime)
        first_error: Optional[Exception] = None

        for connection_id in connection_ids:
            try:
                await self.disconnect(connection_id)
            except Exception as exc:
                if first_error is None:
                    first_error = exc

        if first_error is not None:
            raise first_error

    async def _health(self, connector: ConnectorRuntimeProtocol) -> IntegrationHealth:
        result = await connector.health_check()

        if isinstance(result, IntegrationHealth):
            return result

        connected = getattr(result, "connected", None)
        status_value = getattr(result, "status", None)
        message = getattr(result, "error", None) or getattr(result, "message", None)

        if isinstance(status_value, IntegrationStatus):
            status = status_value
        elif connected is True:
            status = IntegrationStatus.CONNECTED
        elif connected is False:
            status = IntegrationStatus.ERROR
        else:
            raise IntegrationConnectionError(
                "Provider health check returned an unsupported result.",
                operation="hydrate_health_check",
                details={"result_type": type(result).__name__},
            )

        details = {}
        for key in ("base_url", "auth_mode", "api_version"):
            value = getattr(result, key, None)
            if value is not None:
                details[key] = value.value if hasattr(value, "value") else value

        return IntegrationHealth(
            status=status,
            checked_at=utc_now(),
            message=message,
            provider_details=details,
        )

    def _delete_persisted_state(self, connection_id: str) -> None:
        try:
            self.connection_store.delete(connection_id)
        except Exception:
            pass

    @staticmethod
    def _safe_disconnect(connector: Any) -> None:
        disconnect = getattr(connector, "disconnect", None)
        if callable(disconnect):
            try:
                disconnect()
            except Exception:
                pass
