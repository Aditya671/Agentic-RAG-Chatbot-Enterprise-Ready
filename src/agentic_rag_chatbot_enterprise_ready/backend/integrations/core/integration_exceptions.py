"""Application-level exceptions for the enterprise integration layer.

Provider connectors expose provider-specific exceptions. The integration
management layer translates those failures into this small, provider-neutral
hierarchy so the rest of the application does not need to know whether a
failure originated in Jira, SAP, Salesforce, ServiceNow, or SharePoint.

Design rule:
    provider-specific error
        -> connector boundary
        -> integration-layer error
        -> application / API / agent policy

These exceptions intentionally carry operational context, never secrets.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional


class IntegrationError(RuntimeError):
    """Base class for all application-level integration failures."""

    code = "integration_error"
    retryable = False
    user_safe = True

    def __init__(
        self,
        message: str,
        *,
        provider: Optional[str] = None,
        connection_id: Optional[str] = None,
        operation: Optional[str] = None,
        details: Optional[Mapping[str, Any]] = None,
    ) -> None:
        if not isinstance(message, str) or not message.strip():
            raise ValueError("Integration error message is required.")

        self.provider = provider
        self.connection_id = connection_id
        self.operation = operation
        self.details = dict(details or {})

        # Never permit the exception itself to become a credential container.
        forbidden = {
            "access_token",
            "refresh_token",
            "client_secret",
            "password",
            "api_key",
            "authorization",
        }
        if forbidden.intersection(self.details):
            raise ValueError(
                "Integration exception details must not contain credentials."
            )

        super().__init__(message)

    def to_dict(self) -> dict[str, Any]:
        """Return an API/audit-safe representation."""
        return {
            "code": self.code,
            "message": str(self),
            "provider": self.provider,
            "connection_id": self.connection_id,
            "operation": self.operation,
            "retryable": self.retryable,
            "user_safe": self.user_safe,
            "details": dict(self.details),
        }


class IntegrationConfigurationError(IntegrationError):
    """Integration is incorrectly configured."""

    code = "integration_configuration_error"


class IntegrationNotFoundError(IntegrationError):
    """Requested integration/provider/connection/resource was not found."""

    code = "integration_not_found"


class IntegrationAuthenticationError(IntegrationError):
    """Authentication failed or credentials are no longer valid."""

    code = "integration_authentication_error"


class IntegrationAuthorizationError(IntegrationError):
    """Authenticated identity is not permitted to perform an operation."""

    code = "integration_authorization_error"


class IntegrationConnectionError(IntegrationError):
    """Connection could not be established or reached."""

    code = "integration_connection_error"
    retryable = True


class IntegrationTimeoutError(IntegrationConnectionError):
    """Integration operation exceeded its configured timeout."""

    code = "integration_timeout"
    retryable = True


class IntegrationRateLimitError(IntegrationError):
    """Provider throttled the integration request."""

    code = "integration_rate_limit"
    retryable = True

    def __init__(
        self,
        message: str,
        *,
        retry_after: Optional[float] = None,
        **kwargs: Any,
    ) -> None:
        if retry_after is not None and retry_after < 0:
            raise ValueError("retry_after cannot be negative.")

        self.retry_after = retry_after
        super().__init__(message, **kwargs)

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload["retry_after"] = self.retry_after
        return payload


class IntegrationValidationError(IntegrationError):
    """Application input or capability request is invalid."""

    code = "integration_validation_error"


class IntegrationCapabilityError(IntegrationError):
    """Requested integration capability is unavailable or disabled."""

    code = "integration_capability_error"


class IntegrationPolicyError(IntegrationError):
    """Application security/policy blocked an integration operation."""

    code = "integration_policy_error"


class IntegrationConflictError(IntegrationError):
    """Operation conflicts with the current integration state."""

    code = "integration_conflict"


class IntegrationStateError(IntegrationError):
    """Integration lifecycle state does not permit the requested operation."""

    code = "integration_state_error"


class IntegrationProviderError(IntegrationError):
    """Provider returned an error that has no more specific mapping."""

    code = "integration_provider_error"


class IntegrationUnavailableError(IntegrationError):
    """Provider/service is temporarily unavailable."""

    code = "integration_unavailable"
    retryable = True


class IntegrationInternalError(IntegrationError):
    """Unexpected internal integration-layer failure."""

    code = "integration_internal_error"
    user_safe = False
