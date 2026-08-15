"""ServiceNow integration exceptions."""


class ServiceNowError(RuntimeError):
    """Base exception for ServiceNow integration failures."""


class ServiceNowConfigurationError(ServiceNowError):
    """Invalid ServiceNow integration configuration."""


class ServiceNowAuthenticationError(ServiceNowError):
    """OAuth/token acquisition failure."""


class ServiceNowAuthorizationError(ServiceNowError):
    """Authenticated identity lacks required ServiceNow access."""


class ServiceNowNotFoundError(ServiceNowError):
    """Requested ServiceNow resource was not found."""


class ServiceNowRateLimitError(ServiceNowError):
    """ServiceNow throttled the request."""


class ServiceNowQueryError(ServiceNowError):
    """Invalid or unsafe ServiceNow query."""


class ServiceNowAPIError(ServiceNowError):
    """Unexpected ServiceNow API failure."""
