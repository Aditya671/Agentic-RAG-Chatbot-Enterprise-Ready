"""SharePoint integration exceptions."""

class SharePointError(RuntimeError):
    """Base exception for SharePoint integration failures."""


class SharePointConfigurationError(SharePointError):
    """Invalid or incomplete SharePoint configuration."""


class SharePointAuthenticationError(SharePointError):
    """Authentication or token acquisition failed."""


class SharePointAuthorizationError(SharePointError):
    """The identity is authenticated but lacks required permissions."""


class SharePointNotFoundError(SharePointError):
    """Requested SharePoint resource does not exist."""


class SharePointRateLimitError(SharePointError):
    """Microsoft Graph rate-limited the request."""


class SharePointAPIError(SharePointError):
    """Microsoft Graph returned an unexpected error."""
