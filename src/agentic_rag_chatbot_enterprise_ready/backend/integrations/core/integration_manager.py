"""Application-level integration lifecycle manager.

The manager is the orchestration boundary between the application and the
provider registry/connectors.

Responsibilities:
- register/use provider connectors through the registry
- create and track non-secret connection state
- enforce provider/scope/auth capability rules before connecting
- run provider health checks and normalize health state
- disconnect/remove application-owned connections
- expose safe integration summaries/capabilities

Non-responsibilities:
- storing credentials/tokens
- implementing OAuth flows
- calling arbitrary provider URLs
- provider-specific business logic
- deciding whether an LLM is allowed to perform a write

Credential/token persistence belongs to a future secure connection store.
Policy enforcement for agent operations belongs above this manager.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Mapping, Optional, Protocol

from .integration_exceptions import (
    IntegrationAuthenticationError,
    IntegrationAuthorizationError,
    IntegrationCapabilityError,
    IntegrationConfigurationError,
    IntegrationConflictError,
    IntegrationConnectionError,
    IntegrationError,
    IntegrationNotFoundError,
    IntegrationPolicyError,
    IntegrationStateError,
    IntegrationValidationError,
)
from .integration_models import (
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
    utc_now,
)
from .integration_registry import IntegrationRegistry


class ConnectorProtocol(Protocol):
    """Minimum provider connector lifecycle contract."""

    async def health_check(self) -> Any:
        ...

    def disconnect(self) -> None:
        ...


@dataclass(frozen=True)
class ConnectionRequest:
    """Validated non-secret request to establish an integration connection."""

    provider: IntegrationProvider
    connection_id: str
    identity: IntegrationIdentity
    auth_mode: IntegrationAuthMode
    endpoint: Optional[str] = None
    provider_resource_id: Optional[str] = None
    provider_resource_name: Optional[str] = None
    metadata: Mapping[str, Any] = None

    def __post_init__(self) -> None:
        if not self.connection_id.strip():
            raise ValueError("connection_id is required.")

        if self.endpoint is not None:
            endpoint = self.endpoint.strip()
            if endpoint and not endpoint.startswith("https://"):
                raise ValueError("endpoint must use HTTPS.")
            object.__setattr__(self, "endpoint", endpoint or None)

        object.__setattr__(self, "metadata", dict(self.metadata or {}))

        forbidden = {
            "access_token",
            "refresh_token",
            "client_secret",
            "password",
            "api_key",
            "authorization",
        }
        if forbidden.intersection(self.metadata):
            raise ValueError(
                "Connection metadata must not contain credentials."
            )


@dataclass
class ManagedConnection:
    """Internal runtime state for one application-managed connection."""

    state: IntegrationConnection
    connector: ConnectorProtocol


class IntegrationManager:
    """Manage integration connections while keeping provider details isolated."""

    def __init__(
        self,
        registry: IntegrationRegistry,
        *,
        connector_factory_kwargs: Optional[
            Mapping[IntegrationProvider, Mapping[str, Any]]
        ] = None,
    ) -> None:
        if not isinstance(registry, IntegrationRegistry):
            raise IntegrationConfigurationError(
                "registry must be an IntegrationRegistry.",
                operation="initialize",
            )

        self.registry = registry
        self._connections: Dict[str, ManagedConnection] = {}
        self._factory_kwargs = {
            provider: dict(kwargs)
            for provider, kwargs in (connector_factory_kwargs or {}).items()
        }

    async def connect(
        self,
        request: ConnectionRequest,
        *,
        connector_kwargs: Optional[Mapping[str, Any]] = None,
    ) -> IntegrationConnection:
        """Create a provider connector and validate its health.

        The manager accepts only non-secret connection metadata. Secrets should
        already have been resolved by the application's credential/token layer
        and passed through a provider-specific factory adapter, never stored in
        IntegrationConnection.
        """
        self._validate_request(request)

        if request.connection_id in self._connections:
            raise IntegrationConflictError(
                "Connection ID is already managed.",
                provider=request.provider.value,
                connection_id=request.connection_id,
                operation="connect",
            )

        descriptor = self.registry.descriptor(request.provider)

        self._validate_auth_mode(descriptor, request.auth_mode)
        self._validate_scope(descriptor, request.identity.scope)

        kwargs = dict(self._factory_kwargs.get(request.provider, {}))
        if connector_kwargs:
            kwargs.update(connector_kwargs)

        try:
            connector = self.registry.create_connector(
                request.provider,
                **kwargs,
            )
        except IntegrationError:
            raise
        except Exception as exc:
            raise IntegrationConnectionError(
                "Provider connector could not be created.",
                provider=request.provider.value,
                connection_id=request.connection_id,
                operation="connect",
                details={"exception_type": type(exc).__name__},
            ) from exc

        if not hasattr(connector, "health_check"):
            self._safe_disconnect(connector)
            raise IntegrationConfigurationError(
                "Registered connector does not implement health_check().",
                provider=request.provider.value,
                connection_id=request.connection_id,
                operation="connect",
            )

        state = IntegrationConnection(
            connection_id=request.connection_id,
            provider=request.provider,
            identity=request.identity,
            status=IntegrationStatus.CONNECTING,
            auth_mode=request.auth_mode,
            endpoint=request.endpoint,
            provider_resource_id=request.provider_resource_id,
            provider_resource_name=request.provider_resource_name,
            metadata=request.metadata,
        )

        self._connections[request.connection_id] = ManagedConnection(
            state=state,
            connector=connector,
        )

        try:
            health = await self._health(connector)
        except IntegrationError:
            self._connections.pop(request.connection_id, None)
            self._safe_disconnect(connector)
            raise
        except Exception as exc:
            self._connections.pop(request.connection_id, None)
            self._safe_disconnect(connector)
            raise IntegrationConnectionError(
                "Provider health check failed.",
                provider=request.provider.value,
                connection_id=request.connection_id,
                operation="connect",
                details={"exception_type": type(exc).__name__},
            ) from exc

        updated = state.with_health(health)
        self._connections[request.connection_id] = ManagedConnection(
            state=updated,
            connector=connector,
        )

        if updated.status in {
            IntegrationStatus.ERROR,
            IntegrationStatus.DISCONNECTED,
            IntegrationStatus.REVOKED,
        }:
            self._connections.pop(request.connection_id, None)
            self._safe_disconnect(connector)
            raise IntegrationConnectionError(
                health.message or "Integration failed its health check.",
                provider=request.provider.value,
                connection_id=request.connection_id,
                operation="connect",
                details={"status": health.status.value},
            )

        return updated

    async def refresh_health(
        self,
        connection_id: str,
    ) -> IntegrationConnection:
        managed = self._get_managed(connection_id)

        try:
            health = await self._health(managed.connector)
        except IntegrationError:
            raise
        except Exception as exc:
            health = IntegrationHealth.now(
                IntegrationStatus.ERROR,
                message="Provider health check failed.",
                provider_details={"exception_type": type(exc).__name__},
            )

        updated = managed.state.with_health(health)
        self._connections[connection_id] = ManagedConnection(
            state=updated,
            connector=managed.connector,
        )
        return updated

    async def disconnect(self, connection_id: str) -> None:
        managed = self._get_managed(connection_id)

        try:
            managed.connector.disconnect()
        except Exception as exc:
            raise IntegrationConnectionError(
                "Provider connector could not be disconnected cleanly.",
                provider=managed.state.provider.value,
                connection_id=connection_id,
                operation="disconnect",
                details={"exception_type": type(exc).__name__},
            ) from exc
        finally:
            self._connections.pop(connection_id, None)

    def get_connection(self, connection_id: str) -> IntegrationConnection:
        return self._get_managed(connection_id).state

    def list_connections(
        self,
        *,
        provider: Optional[IntegrationProvider | str] = None,
        identity_subject_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> tuple[IntegrationConnection, ...]:
        normalized_provider = (
            self._normalize_provider(provider)
            if provider is not None
            else None
        )

        results = []
        for managed in self._connections.values():
            state = managed.state

            if normalized_provider and state.provider != normalized_provider:
                continue

            if (
                identity_subject_id is not None
                and state.identity.subject_id != identity_subject_id
            ):
                continue

            if tenant_id is not None and state.identity.tenant_id != tenant_id:
                continue

            results.append(state)

        return tuple(
            sorted(
                results,
                key=lambda connection: connection.connection_id,
            )
        )

    def list_summaries(
        self,
        *,
        provider: Optional[IntegrationProvider | str] = None,
        identity_subject_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> tuple[IntegrationSummary, ...]:
        connections = self.list_connections(
            provider=provider,
            identity_subject_id=identity_subject_id,
            tenant_id=tenant_id,
        )

        return tuple(
            IntegrationSummary.from_connection(
                connection,
                self.registry.descriptor(connection.provider),
            )
            for connection in connections
        )

    def capabilities(
        self,
        provider: IntegrationProvider | str,
        *,
        operation: Optional[str] = None,
        enabled_only: bool = True,
    ) -> tuple[IntegrationCapability, ...]:
        descriptor = self.registry.descriptor(provider)
        capabilities = tuple(descriptor.capabilities)

        if enabled_only:
            capabilities = tuple(
                capability
                for capability in capabilities
                if capability.enabled
            )

        if operation is not None:
            normalized_operation = operation.strip().lower()
            capabilities = tuple(
                capability
                for capability in capabilities
                if capability.operation.value == normalized_operation
            )

        return capabilities

    def has_capability(
        self,
        provider: IntegrationProvider | str,
        capability_name: str,
    ) -> bool:
        if not capability_name or not capability_name.strip():
            raise IntegrationValidationError(
                "capability_name is required.",
                operation="has_capability",
            )

        return any(
            capability.name == capability_name
            and capability.enabled
            for capability in self.capabilities(provider)
        )

    def require_capability(
        self,
        provider: IntegrationProvider | str,
        capability_name: str,
        *,
        connection_id: Optional[str] = None,
    ) -> IntegrationCapability:
        if not capability_name or not capability_name.strip():
            raise IntegrationValidationError(
                "capability_name is required.",
                operation="require_capability",
            )

        for capability in self.capabilities(provider):
            if capability.name == capability_name:
                if not capability.enabled:
                    raise IntegrationCapabilityError(
                        f"Capability '{capability_name}' is disabled.",
                        provider=self._normalize_provider(provider).value,
                        connection_id=connection_id,
                        operation="require_capability",
                    )
                return capability

        normalized = self._normalize_provider(provider)
        raise IntegrationCapabilityError(
            f"Capability '{capability_name}' is not registered.",
            provider=normalized.value,
            connection_id=connection_id,
            operation="require_capability",
        )

    def enforce_read_only(
        self,
        provider: IntegrationProvider | str,
        capability_name: str,
        *,
        connection_id: Optional[str] = None,
    ) -> IntegrationCapability:
        """Temporary guard for the current read-only integration phase."""
        capability = self.require_capability(
            provider,
            capability_name,
            connection_id=connection_id,
        )

        if capability.operation.value not in {"read", "search"}:
            raise IntegrationPolicyError(
                "The current integration phase permits only read/search capabilities.",
                provider=self._normalize_provider(provider).value,
                connection_id=connection_id,
                operation=capability_name,
            )

        return capability

    def connection_exists(self, connection_id: str) -> bool:
        return connection_id in self._connections

    async def shutdown(self) -> None:
        """Disconnect all managed connectors.

        Best-effort cleanup is performed for every connection. The first
        disconnect failure is raised after all connectors have been attempted.
        """
        connection_ids = tuple(self._connections)
        first_error: Optional[Exception] = None

        for connection_id in connection_ids:
            try:
                await self.disconnect(connection_id)
            except Exception as exc:
                if first_error is None:
                    first_error = exc

        if first_error is not None:
            raise first_error

    def _validate_request(self, request: ConnectionRequest) -> None:
        if not isinstance(request, ConnectionRequest):
            raise IntegrationValidationError(
                "request must be a ConnectionRequest.",
                operation="connect",
            )
        if request.identity.scope == IntegrationScope.TENANT:
            if not request.identity.tenant_id:
                raise IntegrationValidationError(
                    "Tenant-scoped connections require tenant_id.",
                    provider=request.provider.value,
                    connection_id=request.connection_id,
                    operation="connect",
                )

    @staticmethod
    def _validate_auth_mode(
        descriptor: IntegrationDescriptor,
        auth_mode: IntegrationAuthMode,
    ) -> None:
        if auth_mode not in descriptor.auth_modes:
            raise IntegrationAuthorizationError(
                f"Authentication mode '{auth_mode.value}' is not supported by "
                f"'{descriptor.provider.value}'.",
                provider=descriptor.provider.value,
                operation="connect",
            )

    @staticmethod
    def _validate_scope(
        descriptor: IntegrationDescriptor,
        scope: IntegrationScope,
    ) -> None:
        if scope not in descriptor.supported_scopes:
            raise IntegrationAuthorizationError(
                f"Scope '{scope.value}' is not supported by "
                f"'{descriptor.provider.value}'.",
                provider=descriptor.provider.value,
                operation="connect",
            )

    async def _health(self, connector: ConnectorProtocol) -> IntegrationHealth:
        result = await connector.health_check()

        if isinstance(result, IntegrationHealth):
            return result

        # Provider connectors currently expose provider-specific status objects.
        # Normalize their common shape without importing provider classes.
        status_value = getattr(result, "status", None)
        connected = getattr(result, "connected", None)
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
                operation="health_check",
                details={"result_type": type(result).__name__},
            )

        provider_details: Dict[str, Any] = {}
        for key in ("base_url", "auth_mode", "api_version"):
            value = getattr(result, key, None)
            if value is not None:
                provider_details[key] = (
                    value.value if hasattr(value, "value") else value
                )

        return IntegrationHealth(
            status=status,
            checked_at=utc_now(),
            message=message,
            provider_details=provider_details,
        )

    def _get_managed(self, connection_id: str) -> ManagedConnection:
        if not isinstance(connection_id, str) or not connection_id.strip():
            raise IntegrationValidationError(
                "connection_id is required.",
                operation="resolve_connection",
            )

        managed = self._connections.get(connection_id)
        if managed is None:
            raise IntegrationNotFoundError(
                f"Connection '{connection_id}' is not managed.",
                connection_id=connection_id,
                operation="resolve_connection",
            )

        return managed

    @staticmethod
    def _safe_disconnect(connector: Any) -> None:
        disconnect = getattr(connector, "disconnect", None)
        if callable(disconnect):
            try:
                disconnect()
            except Exception:
                # Cleanup must not mask the original connection failure.
                pass

    @staticmethod
    def _normalize_provider(
        provider: IntegrationProvider | str,
    ) -> IntegrationProvider:
        if isinstance(provider, IntegrationProvider):
            return provider

        if isinstance(provider, str):
            try:
                return IntegrationProvider.from_value(provider)
            except ValueError as exc:
                raise IntegrationNotFoundError(
                    f"Unsupported integration provider: {provider!r}.",
                    provider=provider,
                    operation="resolve_provider",
                ) from exc

        raise IntegrationNotFoundError(
            f"Unsupported integration provider type: {type(provider).__name__}.",
            operation="resolve_provider",
        )

