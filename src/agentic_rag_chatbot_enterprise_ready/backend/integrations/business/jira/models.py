"""Typed models for the Jira integration boundary."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence


@dataclass(frozen=True)
class JiraAuthConfig:
    """Atlassian OAuth 2.0 3LO configuration."""

    client_id: str
    client_secret: Optional[str] = None
    redirect_uri: Optional[str] = None
    scopes: Sequence[str] = ("read:jira-work", "read:jira-user", "offline_access")
    require_pkce: bool = False
    auth_mode: str = "delegated"

    def __post_init__(self) -> None:
        if not self.client_id.strip():
            raise ValueError("client_id is required.")
        if self.auth_mode != "delegated":
            raise ValueError(
                "Jira Cloud integration currently supports delegated OAuth 2.0 3LO only."
            )
        if not self.redirect_uri:
            raise ValueError("redirect_uri is required.")
        if not self.redirect_uri.startswith("https://"):
            raise ValueError("redirect_uri must use HTTPS.")
        object.__setattr__(self, "scopes", tuple(dict.fromkeys(self.scopes)))

    @property
    def authorize_url(self) -> str:
        return "https://auth.atlassian.com/authorize"

    @property
    def token_url(self) -> str:
        return "https://auth.atlassian.com/oauth/token"

    @property
    def accessible_resources_url(self) -> str:
        return "https://api.atlassian.com/oauth/token/accessible-resources"


@dataclass(frozen=True)
class JiraConnectionStatus:
    connected: bool
    cloud_id: Optional[str]
    site_url: Optional[str]
    site_name: Optional[str]
    account_id: Optional[str] = None
    error: Optional[str] = None


@dataclass(frozen=True)
class JiraIssue:
    id: Optional[str]
    key: Optional[str]
    fields: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_api(cls, payload: Mapping[str, Any]) -> "JiraIssue":
        return cls(
            id=str(payload["id"]) if payload.get("id") is not None else None,
            key=payload.get("key"),
            fields=dict(payload.get("fields") or {}),
        )


@dataclass(frozen=True)
class JiraIssueSearchResult:
    issues: List[JiraIssue]
    total: Optional[int]
    next_page_token: Optional[str]
    is_last: bool

    @classmethod
    def from_api(cls, payload: Mapping[str, Any]) -> "JiraIssueSearchResult":
        return cls(
            issues=[
                JiraIssue.from_api(item)
                for item in (payload.get("issues") or [])
            ],
            total=payload.get("total"),
            next_page_token=payload.get("nextPageToken"),
            is_last=bool(payload.get("isLast", False)),
        )


@dataclass(frozen=True)
class JiraProject:
    id: Optional[str]
    key: Optional[str]
    name: Optional[str]
    project_type_key: Optional[str] = None

    @classmethod
    def from_api(cls, payload: Mapping[str, Any]) -> "JiraProject":
        return cls(
            id=str(payload["id"]) if payload.get("id") is not None else None,
            key=payload.get("key"),
            name=payload.get("name"),
            project_type_key=payload.get("projectTypeKey"),
        )


@dataclass(frozen=True)
class JiraCapabilities:
    read_issues: bool = True
    search_issues: bool = True
    read_projects: bool = True
    read_user: bool = True
    read_comments: bool = True
    write_issues: bool = False
    delete_issues: bool = False
    manage_projects: bool = False

    def as_dict(self) -> Dict[str, bool]:
        return {
            "read_issues": self.read_issues,
            "search_issues": self.search_issues,
            "read_projects": self.read_projects,
            "read_user": self.read_user,
            "read_comments": self.read_comments,
            "write_issues": self.write_issues,
            "delete_issues": self.delete_issues,
            "manage_projects": self.manage_projects,
        }
