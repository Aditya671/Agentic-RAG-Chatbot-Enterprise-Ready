"""SAP integration exceptions."""


class SAPError(RuntimeError):
    """Base SAP integration error."""


class SAPConfigurationError(SAPError):
    """Invalid SAP connector configuration."""


class SAPAuthenticationError(SAPError):
    """OAuth/basic authentication failure."""


class SAPAuthorizationError(SAPError):
    """Authenticated identity lacks SAP API access."""


class SAPNotFoundError(SAPError):
    """Requested SAP resource was not found."""


class SAPRateLimitError(SAPError):
    """SAP endpoint throttled the request."""


class SAPQueryError(SAPError):
    """Invalid or unsafe OData query."""


class SAPAPIError(SAPError):
    """Unexpected SAP API failure."""
