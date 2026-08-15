"""Provider-independent models for the enterprise integration layer.

This module deliberately contains *metadata and state only*. It must not hold
OAuth access tokens, client secrets, passwords, or provider-specific API
payloads.

Provider connectors (SharePoint, Salesforce, ServiceNow, Jira, SAP, etc.)
remain responsible for provider-specific authentication and API behavior.
The integration manager/registry can consume these models without importing
provider implementation details.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping, Optional, Sequence


class IntegrationProvider(str, Enum):
    """Stable provider identifiers used by the application."""

    SHAREPOINT = "sharepoint"
    SALESFORCE = "salesforce"
    SERVICENOW = "servicenow"
    JIRA = "jira"
    SAP = "sap"

    @classmethod
    def from_value(cls, value: str) -> "IntegrationProvider":
        try:
            return cls(value.strip().lower())
        except (AttributeError, ValueError) as exc:
            raise ValueError(f"Unsupported integration provider: {value!r}") from exc


class IntegrationStatus(str, Enum):
    """Lifecycle/health state of a user integration."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DEGRADED = "degraded"
    ERROR = "error"
    REVOKED = "revoked"


class IntegrationAuthMode(str, Enum):
    """Provider-independent authentication categories."""

    OAUTH2 = "oauth2"
    BASIC = "basic"
    BEARER = "bearer"
    API_KEY = "api_key"
    SERVICE_ACCOUNT = "service_account"
    CUSTOM = "custom"


class IntegrationScope(str, Enum):
    """Ownership boundary for an integration connection."""

    USER = "user"
    TENANT = "tenant"
    SYSTEM = "system"


class CapabilityOperation(str, Enum):
    """High-level operation classes exposed by an integration."""

    READ = "read"
    SEARCH = "search"
    WRITE = "write"
    DELETE = "delete"
    ADMIN = "admin"
    ACTION = "action"


@dataclass(frozen=True)
class IntegrationCapability:
    """A single capability exposed by a provider connector.

    ``name`` is the stable application/tool identifier. ``operation`` allows
    the manager and policy layer to make coarse authorization decisions
    without understanding provider-specific APIs.
    """

    name: str
    operation: CapabilityOperation
    description: str
    enabled: bool = True
    requires_confirmation: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        name = self.name.strip() if isinstance(self.name, str) else ""
        description = (
            self.description.strip()
            if isinstance(self.description, str)
            else ""
        )
        if not name:
            raise ValueError("Capability name is required.")
        if not description:
            raise ValueError("Capability description is required.")
        if any(char.isspace() for char in name):
            raise ValueError("Capability name must not contain whitespace.")

        object.__setattr__(self, "name", name)
        object.__setattr__(self, "description", description)
        object.__setattr__(self, "metadata", dict(self.metadata))


@dataclass(frozen=True)
class IntegrationDescriptor:
    """Static metadata describing a registered integration provider."""

    provider: IntegrationProvider
    display_name: str
    description: str
    auth_modes: Sequence[IntegrationAuthMode]
    supported_scopes: Sequence[IntegrationScope] = (
        IntegrationScope.USER,
        IntegrationScope.TENANT,
    )
    capabilities: Sequence[IntegrationCapability] = ()
    enabled: bool = True
    version: str = "1.0"

    def __post_init__(self) -> None:
        if not self.display_name.strip():
            raise ValueError("display_name is required.")
        if not self.description.strip():
            raise ValueError("description is required.")
        if not self.version.strip():
            raise ValueError("version is required.")

        auth_modes = tuple(dict.fromkeys(self.auth_modes))
        scopes = tuple(dict.fromkeys(self.supported_scopes))
        capabilities = tuple(self.capabilities)

        if not auth_modes:
            raise ValueError("At least one auth mode is required.")

        names = [cap.name for cap in capabilities]
        if len(names) != len(set(names)):
            raise ValueError("Capability names must be unique per provider.")

        object.__setattr__(self, "auth_modes", auth_modes)
        object.__setattr__(self, "supported_scopes", scopes)
        object.__setattr__(self, "capabilities", capabilities)


@dataclass(frozen=True)
class IntegrationIdentity:
    """Non-secret identity for a connected enterprise integration."""

    subject_id: str
    scope: IntegrationScope
    tenant_id: Optional[str] = None
    display_name: Optional[str] = None
    provider_account_id: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.subject_id.strip():
            raise ValueError("subject_id is required.")

        if self.scope == IntegrationScope.TENANT and not self.tenant_id:
            raise ValueError("tenant_id is required for tenant-scoped connections.")

        if self.tenant_id is not None and not self.tenant_id.strip():
            raise ValueError("tenant_id cannot be blank.")


@dataclass(frozen=True)
class IntegrationHealth:
    """Normalized health result returned by a provider connector."""

    status: IntegrationStatus
    checked_at: datetime
    message: Optional[str] = None
    provider_details: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.checked_at.tzinfo is None:
            raise ValueError("checked_at must be timezone-aware.")
        object.__setattr__(
            self,
            "provider_details",
            dict(self.provider_details),
        )

    @classmethod
    def now(
        cls,
        status: IntegrationStatus,
        *,
        message: Optional[str] = None,
        provider_details: Optional[Mapping[str, Any]] = None,
    ) -> "IntegrationHealth":
        return cls(
            status=status,
            checked_at=datetime.now(timezone.utc),
            message=message,
            provider_details=provider_details or {},
        )


@dataclass(frozen=True)
class IntegrationConnection:
    """Non-secret connection state.

    Credential material belongs in the application's secure connection/token
    store. This object may safely be serialized for status pages, audit
    metadata, and manager state.
    """

    connection_id: str
    provider: IntegrationProvider
    identity: IntegrationIdentity
    status: IntegrationStatus = IntegrationStatus.DISCONNECTED
    auth_mode: Optional[IntegrationAuthMode] = None
    endpoint: Optional[str] = None
    provider_resource_id: Optional[str] = None
    provider_resource_name: Optional[str] = None
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    last_health: Optional[IntegrationHealth] = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.connection_id.strip():
            raise ValueError("connection_id is required.")

        for field_name in ("created_at", "updated_at"):
            value = getattr(self, field_name)
            if value.tzinfo is None:
                raise ValueError(f"{field_name} must be timezone-aware.")

        if self.endpoint is not None:
            endpoint = self.endpoint.strip()
            if endpoint and not endpoint.startswith("https://"):
                raise ValueError("Integration endpoint must use HTTPS.")
            object.__setattr__(self, "endpoint", endpoint or None)

        object.__setattr__(self, "metadata", dict(self.metadata))

    def with_health(
        self,
        health: IntegrationHealth,
    ) -> "IntegrationConnection":
        """Return an immutable connection snapshot with updated health."""
        next_status = health.status
        return IntegrationConnection(
            connection_id=self.connection_id,
            provider=self.provider,
            identity=self.identity,
            status=next_status,
            auth_mode=self.auth_mode,
            endpoint=self.endpoint,
            provider_resource_id=self.provider_resource_id,
            provider_resource_name=self.provider_resource_name,
            created_at=self.created_at,
            updated_at=datetime.now(timezone.utc),
            last_health=health,
            metadata=self.metadata,
        )


@dataclass(frozen=True)
class IntegrationSummary:
    """Safe UI/API representation of an integration connection."""

    connection_id: str
    provider: IntegrationProvider
    display_name: str
    status: IntegrationStatus
    scope: IntegrationScope
    auth_mode: Optional[IntegrationAuthMode]
    endpoint: Optional[str]
    provider_resource_name: Optional[str]
    last_checked_at: Optional[datetime]

    @classmethod
    def from_connection(
        cls,
        connection: IntegrationConnection,
        descriptor: IntegrationDescriptor,
    ) -> "IntegrationSummary":
        return cls(
            connection_id=connection.connection_id,
            provider=connection.provider,
            display_name=descriptor.display_name,
            status=connection.status,
            scope=connection.identity.scope,
            auth_mode=connection.auth_mode,
            endpoint=connection.endpoint,
            provider_resource_name=connection.provider_resource_name,
            last_checked_at=(
                connection.last_health.checked_at
                if connection.last_health
                else None
            ),
        )


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp for integration state."""
    return datetime.now(timezone.utc)
