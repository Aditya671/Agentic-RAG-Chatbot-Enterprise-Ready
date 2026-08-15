"""Jira integration exceptions."""


class JiraError(RuntimeError):
    """Base exception for Jira integration failures."""


class JiraConfigurationError(JiraError):
    """Invalid Jira integration configuration."""


class JiraAuthenticationError(JiraError):
    """OAuth authentication failure."""


class JiraAuthorizationError(JiraError):
    """Authenticated identity lacks Jira access."""


class JiraNotFoundError(JiraError):
    """Requested Jira resource was not found."""


class JiraRateLimitError(JiraError):
    """Jira/Atlassian throttled the request."""


class JiraQueryError(JiraError):
    """Invalid or unsafe JQL/query."""


class JiraAPIError(JiraError):
    """Unexpected Jira API failure."""
