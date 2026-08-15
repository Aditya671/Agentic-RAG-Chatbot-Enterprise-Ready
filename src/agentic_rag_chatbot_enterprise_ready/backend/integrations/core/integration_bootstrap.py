"""Application bootstrap and registration for the five enterprise integrations.

This is the composition root for:
    SharePoint, Salesforce, ServiceNow, Jira, SAP

It is intentionally the only integration-management module that knows the
provider connector import paths. The registry, manager, models, exceptions,
credential store, and adapters remain provider-neutral.

The default bindings use lazy imports so importing the application integration
package does not eagerly initialize SDKs or contact providers.

Connection construction is deliberately explicit:

    manager.connect(
        request,
        connector_kwargs={
            "config": {...non-secret config...},
            "secret_reference": reference,
            "auth_mode": IntegrationAuthMode.OAUTH2,
        },
    )

The adapter resolves the opaque SecretReference and constructs the provider
connector. Raw credential values never enter manager state.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Optional

from .credential_store import SecretReference, SecretStore
from .integration_exceptions import IntegrationConfigurationError
from .integration_models import (
    CapabilityOperation,
    IntegrationAuthMode,
    IntegrationCapability,
    IntegrationDescriptor,
    IntegrationProvider,
    IntegrationScope,
)
from .integration_registry import IntegrationRegistry
from .provider_adapters import AdapterRequest, ProviderAdapter, ProviderConstructor


@dataclass(frozen=True)
class ProviderBinding:
    """Composition-root binding for one concrete provider connector."""

    provider: IntegrationProvider
    display_name: str
    description: str
    config_factory: Callable[..., Any]
    connector_factory: Callable[..., Any]
    secret_fields: frozenset[str]
    auth_modes: frozenset[IntegrationAuthMode]
    capabilities: tuple[IntegrationCapability, ...]
    supported_scopes: tuple[IntegrationScope, ...] = (
        IntegrationScope.USER,
        IntegrationScope.TENANT,
    )
    enabled: bool = True
    version: str = "1.0"


def _filtered_config_factory(
    config_factory: Callable[..., Any],
) -> Callable[..., Any]:
    """Wrap a dataclass/config constructor and reject unknown application keys.

    Provider auth models are intentionally strict. The application config may
    contain connection metadata used by other layers, so only constructor
    parameters are forwarded.
    """
    if not callable(config_factory):
        raise TypeError("config_factory must be callable.")

    try:
        signature = inspect.signature(config_factory)
    except (TypeError, ValueError):
        return config_factory

    accepted = {
        name
        for name, parameter in signature.parameters.items()
        if parameter.kind
        in {
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            inspect.Parameter.KEYWORD_ONLY,
        }
    }
    accepts_var_kwargs = any(
        parameter.kind == inspect.Parameter.VAR_KEYWORD
        for parameter in signature.parameters.values()
    )

    def factory(**kwargs: Any) -> Any:
        if accepts_var_kwargs:
            return config_factory(**kwargs)
        return config_factory(
            **{
                key: value
                for key, value in kwargs.items()
                if key in accepted
            }
        )

    return factory


def _capability(
    name: str,
    operation: CapabilityOperation,
    description: str,
    *,
    requires_confirmation: bool = False,
) -> IntegrationCapability:
    return IntegrationCapability(
        name=name,
        operation=operation,
        description=description,
        requires_confirmation=requires_confirmation,
    )


def default_provider_bindings() -> tuple[ProviderBinding, ...]:
    """Build bindings against the actual provider connector modules.

    Imports are lazy and occur only when application startup explicitly asks
    for the default integration registry.
    """

    try:
        from ..collaboration.sharepoint.auth import SharePointAuthConfig
        from ..collaboration.sharepoint_connector import SharePointConnector

        from ..business.salesforce.models import SalesforceAuthConfig
        from ..business.salesforce_connector import SalesforceConnector

        from ..business.servicenow.models import ServiceNowAuthConfig
        from ..business.servicenow_connector import ServiceNowConnector

        from ..business.jira.models import JiraAuthConfig
        from ..business.jira_connector import JiraConnector

        from ..business.sap.models import SAPAuthConfig
        from ..business.sap_connector import SAPConnector
    except ImportError as exc:
        raise IntegrationConfigurationError(
            "One or more enterprise integration provider modules are unavailable.",
            operation="default_provider_bindings",
            details={"exception_type": type(exc).__name__},
        ) from exc

    return (
        ProviderBinding(
            provider=IntegrationProvider.SHAREPOINT,
            display_name="Microsoft SharePoint",
            description="SharePoint Online through Microsoft Graph.",
            config_factory=_filtered_config_factory(SharePointAuthConfig),
            connector_factory=SharePointConnector,
            secret_fields=frozenset(
                {"access_token", "refresh_token", "client_secret"}
            ),
            auth_modes=frozenset({IntegrationAuthMode.OAUTH2}),
            capabilities=(
                _capability("read_sites", CapabilityOperation.READ, "Read SharePoint sites."),
                _capability("read_drives", CapabilityOperation.READ, "Read SharePoint document libraries."),
                _capability("read_files", CapabilityOperation.READ, "Read SharePoint file metadata."),
                _capability("download_files", CapabilityOperation.READ, "Download SharePoint files."),
                _capability("search_files", CapabilityOperation.SEARCH, "Search SharePoint files."),
                _capability(
                    "write_files",
                    CapabilityOperation.WRITE,
                    "Modify SharePoint files.",
                    requires_confirmation=True,
                ),
            ),
            version=getattr(SharePointConnector, "API_VERSION", "1.0"),
        ),
        ProviderBinding(
            provider=IntegrationProvider.SALESFORCE,
            display_name="Salesforce",
            description="Salesforce CRM through the Platform REST API.",
            config_factory=_filtered_config_factory(SalesforceAuthConfig),
            connector_factory=SalesforceConnector,
            secret_fields=frozenset(
                {"access_token", "refresh_token", "client_secret", "instance_url"}
            ),
            auth_modes=frozenset({IntegrationAuthMode.OAUTH2}),
            capabilities=(
                _capability("read_records", CapabilityOperation.READ, "Read Salesforce records."),
                _capability("query_soql", CapabilityOperation.SEARCH, "Execute controlled SELECT SOQL."),
                _capability("read_accounts", CapabilityOperation.SEARCH, "Search Salesforce accounts."),
                _capability("read_contacts", CapabilityOperation.SEARCH, "Search Salesforce contacts."),
                _capability("read_opportunities", CapabilityOperation.SEARCH, "Search Salesforce opportunities."),
                _capability("read_cases", CapabilityOperation.SEARCH, "Search Salesforce cases."),
                _capability(
                    "write_records",
                    CapabilityOperation.WRITE,
                    "Modify Salesforce records.",
                    requires_confirmation=True,
                ),
            ),
            version=getattr(SalesforceConnector, "API_VERSION", "1.0"),
        ),
        ProviderBinding(
            provider=IntegrationProvider.SERVICENOW,
            display_name="ServiceNow",
            description="ServiceNow ITSM through the Table API.",
            config_factory=_filtered_config_factory(ServiceNowAuthConfig),
            connector_factory=ServiceNowConnector,
            secret_fields=frozenset(
                {"access_token", "refresh_token", "client_secret"}
            ),
            auth_modes=frozenset({IntegrationAuthMode.OAUTH2}),
            capabilities=(
                _capability("read_incidents", CapabilityOperation.SEARCH, "Search ServiceNow incidents."),
                _capability("read_requests", CapabilityOperation.SEARCH, "Search ServiceNow requests."),
                _capability("read_changes", CapabilityOperation.SEARCH, "Search ServiceNow changes."),
                _capability("read_records", CapabilityOperation.READ, "Read ServiceNow records."),
                _capability("query_records", CapabilityOperation.SEARCH, "Query controlled ServiceNow records."),
                _capability(
                    "write_records",
                    CapabilityOperation.WRITE,
                    "Modify ServiceNow records.",
                    requires_confirmation=True,
                ),
                _capability(
                    "delete_records",
                    CapabilityOperation.DELETE,
                    "Delete ServiceNow records.",
                    requires_confirmation=True,
                ),
            ),
            version="1.0",
        ),
        ProviderBinding(
            provider=IntegrationProvider.JIRA,
            display_name="Jira Cloud",
            description="Jira Cloud through Atlassian OAuth 2.0 and REST API v3.",
            config_factory=_filtered_config_factory(JiraAuthConfig),
            connector_factory=JiraConnector,
            secret_fields=frozenset(
                {
                    "access_token",
                    "refresh_token",
                    "client_secret",
                    "cloud_id",
                    "site_url",
                    "site_name",
                }
            ),
            auth_modes=frozenset({IntegrationAuthMode.OAUTH2}),
            capabilities=(
                _capability("read_issues", CapabilityOperation.READ, "Read Jira issues."),
                _capability("search_issues", CapabilityOperation.SEARCH, "Search Jira issues."),
                _capability("read_projects", CapabilityOperation.READ, "Read Jira projects."),
                _capability("read_user", CapabilityOperation.READ, "Read Jira user information."),
                _capability("read_comments", CapabilityOperation.READ, "Read Jira issue comments."),
                _capability(
                    "write_issues",
                    CapabilityOperation.WRITE,
                    "Modify Jira issues.",
                    requires_confirmation=True,
                ),
                _capability(
                    "delete_issues",
                    CapabilityOperation.DELETE,
                    "Delete Jira issues.",
                    requires_confirmation=True,
                ),
                _capability(
                    "manage_projects",
                    CapabilityOperation.ADMIN,
                    "Manage Jira projects.",
                    requires_confirmation=True,
                ),
            ),
            version=getattr(JiraConnector, "API_VERSION", "1.0"),
        ),
        ProviderBinding(
            provider=IntegrationProvider.SAP,
            display_name="SAP",
            description="SAP OData enterprise integration.",
            config_factory=_filtered_config_factory(SAPAuthConfig),
            connector_factory=SAPConnector,
            secret_fields=frozenset(
                {
                    "access_token",
                    "client_secret",
                    "username",
                    "password",
                }
            ),
            auth_modes=frozenset(
                {
                    IntegrationAuthMode.OAUTH2,
                    IntegrationAuthMode.BASIC,
                    IntegrationAuthMode.BEARER,
                }
            ),
            capabilities=(
                _capability("read_odata", CapabilityOperation.READ, "Read SAP OData resources."),
                _capability("query_odata", CapabilityOperation.SEARCH, "Query SAP OData entity sets."),
                _capability("metadata", CapabilityOperation.READ, "Read SAP OData metadata."),
                _capability(
                    "write_records",
                    CapabilityOperation.WRITE,
                    "Modify SAP records.",
                    requires_confirmation=True,
                ),
                _capability(
                    "delete_records",
                    CapabilityOperation.DELETE,
                    "Delete SAP records.",
                    requires_confirmation=True,
                ),
                _capability(
                    "execute_actions",
                    CapabilityOperation.ACTION,
                    "Execute SAP OData actions.",
                    requires_confirmation=True,
                ),
            ),
            version="odata-v2-v4",
        ),
    )


def register_provider_bindings(
    registry: IntegrationRegistry,
    secret_store: SecretStore,
    bindings: Optional[tuple[ProviderBinding, ...]] = None,
) -> IntegrationRegistry:
    """Register concrete provider adapters into an existing registry."""

    if not isinstance(registry, IntegrationRegistry):
        raise TypeError("registry must be an IntegrationRegistry.")

    if not hasattr(secret_store, "get_secret"):
        raise TypeError("secret_store must implement SecretStore.")

    for binding in bindings or default_provider_bindings():
        constructor = ProviderConstructor(
            provider=binding.provider,
            config_factory=binding.config_factory,
            connector_factory=binding.connector_factory,
            secret_fields=binding.secret_fields,
            config_fields=frozenset(),
            auth_modes=binding.auth_modes,
        )

        adapter = ProviderAdapter(
            constructor=constructor,
            secret_store=secret_store,
        )

        def factory(
            *,
            config: Optional[Mapping[str, Any]] = None,
            secret_reference: Optional[SecretReference] = None,
            auth_mode: Optional[IntegrationAuthMode] = None,
            _binding=binding,
            _adapter=adapter,
        ) -> Any:
            return _adapter.create(
                AdapterRequest(
                    provider=_binding.provider,
                    config=config or {},
                    secret_reference=secret_reference,
                    auth_mode=auth_mode,
                )
            )

        descriptor = IntegrationDescriptor(
            provider=binding.provider,
            display_name=binding.display_name,
            description=binding.description,
            auth_modes=binding.auth_modes,
            supported_scopes=binding.supported_scopes,
            capabilities=binding.capabilities,
            enabled=binding.enabled,
            version=binding.version,
        )

        registry.register(descriptor, factory)

    return registry


def build_default_registry(
    secret_store: SecretStore,
) -> IntegrationRegistry:
    """Build the production composition root for all configured providers."""
    registry = IntegrationRegistry()
    return register_provider_bindings(
        registry,
        secret_store,
        default_provider_bindings(),
    )
