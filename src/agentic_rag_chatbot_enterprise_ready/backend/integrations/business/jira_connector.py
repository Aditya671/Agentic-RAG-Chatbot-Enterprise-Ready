"""Enterprise Jira Cloud connector.

Public application-facing boundary for the independent enterprise integration
layer. Initial scope is read-only Jira Cloud access using OAuth 2.0 3LO and
the current Jira Cloud REST API v3.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Mapping, Optional, Sequence

from .jira.auth import JiraTokenProvider
from .jira.client import JiraRESTClient
from .jira.exceptions import JiraConfigurationError, JiraQueryError
from .jira.models import (
    JiraAuthConfig,
    JiraCapabilities,
    JiraConnectionStatus,
    JiraIssue,
    JiraIssueSearchResult,
    JiraProject,
)

_SAFE_FIELD = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]*$")
_SAFE_ISSUE_KEY = re.compile(r"^[A-Za-z][A-Za-z0-9_]*-[0-9]+$")


class JiraConnector:
    """Jira capability facade."""

    PROVIDER_NAME = "jira"
    API_VERSION = "3"

    def __init__(
        self,
        config: JiraAuthConfig,
        *,
        access_token: Optional[str] = None,
        cloud_id: Optional[str] = None,
        site_url: Optional[str] = None,
        site_name: Optional[str] = None,
        rest_client: Optional[JiraRESTClient] = None,
        capabilities: Optional[JiraCapabilities] = None,
    ) -> None:
        self.config = config
        self.auth = JiraTokenProvider(config)
        self.capabilities = capabilities or JiraCapabilities()
        self._access_token = access_token
        self._cloud_id = cloud_id
        self._site_url = site_url
        self._site_name = site_name
        self._client = rest_client

        if access_token and cloud_id and rest_client is None:
            self._client = JiraRESTClient(
                access_token=access_token,
                cloud_id=cloud_id,
            )

    @property
    def is_authenticated(self) -> bool:
        return self._client is not None

    @property
    def cloud_id(self) -> Optional[str]:
        return self._cloud_id

    @property
    def site_url(self) -> Optional[str]:
        return self._site_url

    def get_capabilities(self) -> Dict[str, bool]:
        return self.capabilities.as_dict()

    def get_authorization_url(
        self,
        *,
        state: Optional[str] = None,
        pkce_verifier: Optional[str] = None,
        prompt: str = "consent",
    ) -> tuple[str, str]:
        return self.auth.build_authorization_url(
            state=state,
            pkce_verifier=pkce_verifier,
            prompt=prompt,
        )

    async def exchange_authorization_code(
        self,
        *,
        code: str,
        pkce_verifier: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload = await self.auth.exchange_authorization_code(
            code=code,
            pkce_verifier=pkce_verifier,
        )

        resources = await self.auth.get_accessible_resources(
            access_token=payload["access_token"]
        )
        if not resources:
            raise JiraConfigurationError(
                "The Atlassian account has no accessible Jira Cloud resources."
            )

        selected = resources[0]
        self.set_credentials(
            access_token=payload["access_token"],
            cloud_id=selected["id"],
            site_url=selected.get("url"),
            site_name=selected.get("name"),
        )
        payload["_accessible_resources"] = resources
        return payload

    def set_credentials(
        self,
        *,
        access_token: str,
        cloud_id: str,
        site_url: Optional[str] = None,
        site_name: Optional[str] = None,
    ) -> None:
        if not access_token:
            raise JiraConfigurationError("access_token is required.")
        if not cloud_id:
            raise JiraConfigurationError("cloud_id is required.")

        self._access_token = access_token
        self._cloud_id = cloud_id
        self._site_url = site_url.rstrip("/") if site_url else None
        self._site_name = site_name
        self._client = JiraRESTClient(
            access_token=access_token,
            cloud_id=cloud_id,
        )

    def disconnect(self) -> None:
        self._access_token = None
        self._cloud_id = None
        self._site_url = None
        self._site_name = None
        self._client = None

    def _require_client(self) -> JiraRESTClient:
        if self._client is None:
            raise JiraConfigurationError(
                "Jira is not connected. Authenticate first."
            )
        return self._client

    async def health_check(self) -> JiraConnectionStatus:
        client = self._require_client()

        try:
            payload = await client.get(
                "/myself",
                params={"expand": "groups"},
            )
            return JiraConnectionStatus(
                connected=True,
                cloud_id=self._cloud_id,
                site_url=self._site_url,
                site_name=self._site_name,
                account_id=payload.get("accountId"),
            )
        except Exception as exc:
            return JiraConnectionStatus(
                connected=False,
                cloud_id=self._cloud_id,
                site_url=self._site_url,
                site_name=self._site_name,
                error=str(exc),
            )

    async def get_current_user(self) -> Mapping[str, Any]:
        return await self._require_client().get("/myself")

    async def get_issue(
        self,
        issue_key_or_id: str,
        *,
        fields: Optional[Sequence[str]] = None,
    ) -> JiraIssue:
        if not issue_key_or_id or not re.fullmatch(
            r"^[A-Za-z][A-Za-z0-9_-]*$|^[0-9]+$",
            issue_key_or_id,
        ):
            raise JiraQueryError("Invalid issue key or ID.")

        params: Dict[str, Any] = {}
        if fields:
            params["fields"] = ",".join(
                self._validate_field(field)
                for field in fields
            )

        payload = await self._require_client().get(
            f"/issue/{issue_key_or_id}",
            params=params,
        )
        return JiraIssue.from_api(payload)

    @staticmethod
    def _validate_field(field: str) -> str:
        if not field or not _SAFE_FIELD.fullmatch(field):
            raise JiraQueryError(f"Unsafe Jira field: {field!r}")
        return field

    @staticmethod
    def _validate_limit(limit: int) -> int:
        if not isinstance(limit, int) or not 1 <= limit <= 100:
            raise JiraQueryError("max_results must be between 1 and 100.")
        return limit

    @staticmethod
    def _validate_jql(jql: str) -> str:
        if not isinstance(jql, str) or not jql.strip():
            raise JiraQueryError("JQL must be non-empty.")
        normalized = jql.strip()
        if len(normalized) > 4000:
            raise JiraQueryError("JQL is too long.")
        # Prevent chaining an application-level second statement.
        if ";" in normalized:
            raise JiraQueryError("Multiple JQL statements are not allowed.")
        return normalized

    async def search_issues(
        self,
        jql: str,
        *,
        fields: Sequence[str] = (
            "summary",
            "status",
            "priority",
            "assignee",
            "reporter",
            "project",
            "issuetype",
            "created",
            "updated",
        ),
        max_results: int = 25,
        next_page_token: Optional[str] = None,
    ) -> JiraIssueSearchResult:
        jql = self._validate_jql(jql)
        max_results = self._validate_limit(max_results)
        validated_fields = [
            self._validate_field(field)
            for field in fields
        ]

        params: Dict[str, Any] = {
            "jql": jql,
            "maxResults": max_results,
            "fields": ",".join(validated_fields),
        }
        if next_page_token:
            if len(next_page_token) > 2048:
                raise JiraQueryError("next_page_token is too long.")
            params["nextPageToken"] = next_page_token

        payload = await self._require_client().get(
            "/search/jql",
            params=params,
        )
        return JiraIssueSearchResult.from_api(payload)

    async def search_text(
        self,
        text: str,
        *,
        max_results: int = 25,
    ) -> JiraIssueSearchResult:
        if not text or not text.strip():
            raise JiraQueryError("search text is required.")

        # Use JQL text search but keep construction deterministic. Quotes and
        # backslashes are escaped before embedding into the JQL string.
        value = (
            text.strip()
            .replace("\\", "\\\\")
            .replace('"', '\\"')
        )
        jql = f'text ~ "{value}" ORDER BY updated DESC'
        return await self.search_issues(
            jql,
            max_results=max_results,
        )

    async def list_projects(
        self,
        *,
        start_at: int = 0,
        max_results: int = 50,
    ) -> list[JiraProject]:
        if not isinstance(start_at, int) or start_at < 0:
            raise JiraQueryError("start_at must be non-negative.")
        if not 1 <= max_results <= 100:
            raise JiraQueryError("max_results must be between 1 and 100.")

        payload = await self._require_client().get(
            "/project/search",
            params={
                "startAt": start_at,
                "maxResults": max_results,
            },
        )
        return [
            JiraProject.from_api(item)
            for item in (payload.get("values") or [])
        ]

    async def get_project(self, project_key_or_id: str) -> JiraProject:
        if not project_key_or_id or not re.fullmatch(
            r"^[A-Za-z][A-Za-z0-9_-]*$|^[0-9]+$",
            project_key_or_id,
        ):
            raise JiraQueryError("Invalid Jira project key or ID.")

        payload = await self._require_client().get(
            f"/project/{project_key_or_id}"
        )
        return JiraProject.from_api(payload)
