"""Provider-adapter boundary for the enterprise integration layer.

The integration manager is provider-neutral, while the five completed
connectors have provider-specific configuration classes and constructor
contracts. This module bridges those contracts without putting provider logic
inside ``integration_manager.py``.

Security invariant:
    SecretStore -> opaque SecretReference -> adapter -> connector

Raw credential values must never enter IntegrationConnection,
IntegrationSummary, IntegrationRegistry, or manager state.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Optional

from .credential_store import SecretReference, SecretStore
from .integration_exceptions import (
    IntegrationAuthenticationError,
    IntegrationConfigurationError,
    IntegrationValidationError,
)
from .integration_models import IntegrationAuthMode, IntegrationProvider


@dataclass(frozen=True)
class AdapterRequest:
    """Provider-neutral input used to construct a connector."""

    provider: IntegrationProvider
    config: Mapping[str, Any]
    secret_reference: Optional[SecretReference] = None
    auth_mode: Optional[IntegrationAuthMode] = None

    def __post_init__(self) -> None:
        if not isinstance(self.config, Mapping):
            raise TypeError("config must be a mapping.")

        object.__setattr__(self, "config", dict(self.config))

        forbidden = {
            "access_token",
            "refresh_token",
            "client_secret",
            "password",
            "api_key",
            "authorization",
        }
        if forbidden.intersection(self.config):
            raise ValueError(
                "Raw credential fields must be supplied through SecretStore."
            )


@dataclass(frozen=True)
class ProviderConstructor:
    """Provider-specific constructor functions supplied by application wiring.

    Keeping constructors injectable avoids hard-coding repository import paths
    and makes each adapter independently testable.
    """

    provider: IntegrationProvider
    config_factory: Callable[..., Any]
    connector_factory: Callable[..., Any]
    secret_fields: frozenset[str]
    config_fields: frozenset[str]
    auth_modes: frozenset[IntegrationAuthMode]


class ProviderAdapter:
    """Construct one provider connector using secure credential resolution."""

    def __init__(
        self,
        constructor: ProviderConstructor,
        secret_store: SecretStore,
    ) -> None:
        self.constructor = constructor
        self.secret_store = secret_store

    def create(self, request: AdapterRequest) -> Any:
        if request.provider != self.constructor.provider:
            raise IntegrationConfigurationError(
                "Adapter provider does not match constructor provider.",
                provider=request.provider.value,
                operation="create_connector",
            )

        if (
            request.auth_mode is not None
            and request.auth_mode not in self.constructor.auth_modes
        ):
            raise IntegrationConfigurationError(
                f"Authentication mode '{request.auth_mode.value}' is not supported "
                f"by the {request.provider.value} adapter.",
                provider=request.provider.value,
                operation="create_connector",
            )

        secret_values = self._resolve_secret(request.secret_reference)

        unexpected = set(secret_values) - self.constructor.secret_fields
        if unexpected:
            raise IntegrationValidationError(
                "Secret payload contains unsupported fields.",
                provider=request.provider.value,
                operation="resolve_credentials",
                details={"fields": sorted(unexpected)},
            )

        config = dict(request.config)

        # Authentication models need some credential fields (for example
        # client_secret/password), while access tokens and provider resource
        # identifiers belong to the connector constructor. Keep the two
        # contracts explicit instead of blindly passing every secret field to
        # the configuration model.
        config.update(
            {
                key: value
                for key, value in secret_values.items()
                if key in self.constructor.config_fields
            }
        )

        try:
            auth_config = self.constructor.config_factory(**config)
        except IntegrationConfigurationError:
            raise
        except Exception as exc:
            raise IntegrationConfigurationError(
                "Provider authentication configuration could not be built.",
                provider=request.provider.value,
                operation="create_connector",
                details={"exception_type": type(exc).__name__},
            ) from exc

        try:
            connector_kwargs = self._connector_kwargs(
                request.provider,
                secret_values,
            )
            return self.constructor.connector_factory(
                auth_config,
                **connector_kwargs,
            )
        except IntegrationAuthenticationError:
            raise
        except Exception as exc:
            raise IntegrationConfigurationError(
                "Provider connector could not be constructed.",
                provider=request.provider.value,
                operation="create_connector",
                details={"exception_type": type(exc).__name__},
            ) from exc

    def _resolve_secret(
        self,
        reference: Optional[SecretReference],
    ) -> dict[str, Any]:
        if reference is None:
            return {}

        try:
            raw = self.secret_store.get_secret(
                reference,
                owner_id=reference.owner_id,
            )
        except PermissionError as exc:
            raise IntegrationAuthenticationError(
                "Credential ownership validation failed.",
                provider=self.constructor.provider.value,
                operation="resolve_credentials",
            ) from exc
        except KeyError as exc:
            raise IntegrationAuthenticationError(
                "Credential reference is unavailable or expired.",
                provider=self.constructor.provider.value,
                operation="resolve_credentials",
            ) from exc

        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")

        if not isinstance(raw, str):
            raise IntegrationValidationError(
                "Credential payload must be a JSON object.",
                provider=self.constructor.provider.value,
                operation="resolve_credentials",
            )

        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise IntegrationValidationError(
                "Credential payload is not valid JSON.",
                provider=self.constructor.provider.value,
                operation="resolve_credentials",
            ) from exc

        if not isinstance(payload, dict):
            raise IntegrationValidationError(
                "Credential payload must be a JSON object.",
                provider=self.constructor.provider.value,
                operation="resolve_credentials",
            )

        return payload

    @staticmethod
    def _connector_kwargs(
        provider: IntegrationProvider,
        secret_values: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Return transient connector-only credential kwargs.

        These values exist only during connector construction. They are not
        persisted by this adapter.
        """
        if provider is IntegrationProvider.SHAREPOINT:
            return {
                key: secret_values[key]
                for key in ("access_token",)
                if key in secret_values
            }

        if provider is IntegrationProvider.SALESFORCE:
            return {
                key: secret_values[key]
                for key in ("access_token", "instance_url")
                if key in secret_values
            }

        if provider is IntegrationProvider.SERVICENOW:
            return {
                key: secret_values[key]
                for key in ("access_token",)
                if key in secret_values
            }

        if provider is IntegrationProvider.JIRA:
            return {
                key: secret_values[key]
                for key in ("access_token", "cloud_id", "site_url", "site_name")
                if key in secret_values
            }

        if provider is IntegrationProvider.SAP:
            return {
                "access_token": secret_values["access_token"]
                if "access_token" in secret_values
                else None,
            }

        return {}


def make_constructor(
    provider: IntegrationProvider,
    *,
    config_factory: Callable[..., Any],
    connector_factory: Callable[..., Any],
    secret_fields: set[str] | frozenset[str],
    auth_modes: set[IntegrationAuthMode] | frozenset[IntegrationAuthMode],
    config_fields: set[str] | frozenset[str] = frozenset(),
) -> ProviderConstructor:
    """Build a validated provider constructor descriptor."""
    if not callable(config_factory):
        raise TypeError("config_factory must be callable.")
    if not callable(connector_factory):
        raise TypeError("connector_factory must be callable.")

    return ProviderConstructor(
        provider=provider,
        config_factory=config_factory,
        connector_factory=connector_factory,
        secret_fields=frozenset(secret_fields),
        config_fields=frozenset(config_fields),
        auth_modes=frozenset(auth_modes),
    )
