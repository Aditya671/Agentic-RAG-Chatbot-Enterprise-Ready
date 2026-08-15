"""Provider registry for the enterprise integration layer.

The registry owns *provider metadata and factories*. It does not own user
connections, credentials, tokens, or provider runtime state.

Design goals:
- deterministic provider discovery
- duplicate-registration protection
- explicit enable/disable support
- capability metadata available without connecting
- dependency-light provider factories
- safe lookup errors through the integration exception hierarchy
"""

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from typing import Any, Callable, Dict, Iterable, Mapping, Optional, Protocol

from .integration_exceptions import (
    IntegrationConfigurationError,
    IntegrationConflictError,
    IntegrationNotFoundError,
)
from .integration_models import (
    IntegrationDescriptor,
    IntegrationProvider,
)


class ConnectorFactory(Protocol):
    """Callable contract used to construct a provider connector."""

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        ...


@dataclass(frozen=True)
class RegisteredIntegration:
    """Immutable registry entry."""

    descriptor: IntegrationDescriptor
    factory: ConnectorFactory


class IntegrationRegistry:
    """Thread-safe registry of application integration providers."""

    def __init__(
        self,
        registrations: Optional[Iterable[RegisteredIntegration]] = None,
    ) -> None:
        self._entries: Dict[IntegrationProvider, RegisteredIntegration] = {}
        self._lock = RLock()

        if registrations:
            for registration in registrations:
                self.register(
                    registration.descriptor,
                    registration.factory,
                )

    def register(
        self,
        descriptor: IntegrationDescriptor,
        factory: ConnectorFactory,
        *,
        replace: bool = False,
    ) -> None:
        """Register a provider and its connector factory.

        Replacement is explicit. Silent replacement is prohibited because
        provider registrations may carry security-sensitive capability
        definitions.
        """
        if not isinstance(descriptor, IntegrationDescriptor):
            raise IntegrationConfigurationError(
                "descriptor must be an IntegrationDescriptor.",
                operation="register",
            )

        if not callable(factory):
            raise IntegrationConfigurationError(
                "factory must be callable.",
                provider=descriptor.provider.value,
                operation="register",
            )

        provider = descriptor.provider

        with self._lock:
            if provider in self._entries and not replace:
                raise IntegrationConflictError(
                    f"Integration provider '{provider.value}' is already registered.",
                    provider=provider.value,
                    operation="register",
                )

            self._entries[provider] = RegisteredIntegration(
                descriptor=descriptor,
                factory=factory,
            )

    def unregister(self, provider: IntegrationProvider | str) -> None:
        """Remove a provider registration.

        Connection lifecycle is intentionally outside the registry. Removing a
        provider from the registry therefore does not claim to revoke or
        disconnect existing user connections.
        """
        normalized = self._normalize_provider(provider)

        with self._lock:
            if normalized not in self._entries:
                raise IntegrationNotFoundError(
                    f"Integration provider '{normalized.value}' is not registered.",
                    provider=normalized.value,
                    operation="unregister",
                )
            del self._entries[normalized]

    def is_registered(self, provider: IntegrationProvider | str) -> bool:
        normalized = self._normalize_provider(provider)
        with self._lock:
            return normalized in self._entries

    def get(
        self,
        provider: IntegrationProvider | str,
    ) -> RegisteredIntegration:
        normalized = self._normalize_provider(provider)

        with self._lock:
            registration = self._entries.get(normalized)

        if registration is None:
            raise IntegrationNotFoundError(
                f"Integration provider '{normalized.value}' is not registered.",
                provider=normalized.value,
                operation="get",
            )

        return registration

    def descriptor(
        self,
        provider: IntegrationProvider | str,
    ) -> IntegrationDescriptor:
        return self.get(provider).descriptor

    def factory(
        self,
        provider: IntegrationProvider | str,
    ) -> ConnectorFactory:
        return self.get(provider).factory

    def create_connector(
        self,
        provider: IntegrationProvider | str,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Construct a connector through the registered provider factory."""
        registration = self.get(provider)

        if not registration.descriptor.enabled:
            raise IntegrationConfigurationError(
                f"Integration provider '{registration.descriptor.provider.value}' is disabled.",
                provider=registration.descriptor.provider.value,
                operation="create_connector",
            )

        try:
            return registration.factory(*args, **kwargs)
        except IntegrationConfigurationError:
            raise
        except Exception as exc:
            raise IntegrationConfigurationError(
                "Integration connector could not be constructed.",
                provider=registration.descriptor.provider.value,
                operation="create_connector",
                details={"exception_type": type(exc).__name__},
            ) from exc

    def list_descriptors(
        self,
        *,
        enabled_only: bool = True,
    ) -> tuple[IntegrationDescriptor, ...]:
        with self._lock:
            entries = tuple(self._entries.values())

        descriptors = tuple(entry.descriptor for entry in entries)
        if enabled_only:
            descriptors = tuple(
                descriptor
                for descriptor in descriptors
                if descriptor.enabled
            )

        return tuple(
            sorted(
                descriptors,
                key=lambda descriptor: descriptor.provider.value,
            )
        )

    def list_providers(
        self,
        *,
        enabled_only: bool = True,
    ) -> tuple[IntegrationProvider, ...]:
        return tuple(
            descriptor.provider
            for descriptor in self.list_descriptors(
                enabled_only=enabled_only,
            )
        )

    def capabilities(
        self,
        provider: IntegrationProvider | str,
    ) -> tuple:
        return self.descriptor(provider).capabilities

    def clear(self) -> None:
        """Clear all registrations.

        Intended for application startup configuration and isolated tests.
        It does not disconnect existing connector instances.
        """
        with self._lock:
            self._entries.clear()

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


def build_registry(
    registrations: Optional[Mapping[
        IntegrationProvider,
        tuple[IntegrationDescriptor, ConnectorFactory],
    ]] = None,
) -> IntegrationRegistry:
    """Build a registry from explicit application registrations.

    The default is intentionally empty. Provider imports are not performed
    implicitly because applications may deploy only a subset of integrations.
    """
    registry = IntegrationRegistry()

    if registrations:
        for provider, (descriptor, factory) in registrations.items():
            if provider != descriptor.provider:
                raise IntegrationConfigurationError(
                    "Registration key does not match descriptor provider.",
                    provider=str(provider),
                    operation="build_registry",
                )
            registry.register(descriptor, factory)

    return registry
