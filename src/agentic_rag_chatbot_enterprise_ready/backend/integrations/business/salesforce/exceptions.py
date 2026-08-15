"""Salesforce integration exceptions."""


class SalesforceError(RuntimeError):
    """Base exception for Salesforce integration failures."""


class SalesforceConfigurationError(SalesforceError):
    """Invalid Salesforce integration configuration."""


class SalesforceAuthenticationError(SalesforceError):
    """Salesforce OAuth/token acquisition failure."""


class SalesforceAuthorizationError(SalesforceError):
    """Authenticated identity lacks required Salesforce access."""


class SalesforceNotFoundError(SalesforceError):
    """Requested Salesforce resource was not found."""


class SalesforceRateLimitError(SalesforceError):
    """Salesforce throttled the request."""


class SalesforceQueryError(SalesforceError):
    """SOQL query is invalid or violates the connector policy."""


class SalesforceAPIError(SalesforceError):
    """Unexpected Salesforce API failure."""
