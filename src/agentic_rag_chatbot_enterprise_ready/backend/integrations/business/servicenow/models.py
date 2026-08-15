"""Typed models for the ServiceNow integration boundary."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence


@dataclass(frozen=True)
class ServiceNowAuthConfig:
    """OAuth configuration for an external ServiceNow client."""

    instance_url: str
    client_id: str
    client_secret: Optional[str] = None
    redirect_uri: Optional[str] = None
    auth_mode: str = "delegated"
    api_path: str = "/api/now"
    api_version: Optional[str] = None
    scopes: Sequence[str] = ("useraccount",)
    require_pkce: bool = False

    def __post_init__(self) -> None:
        if not self.instance_url or not self.instance_url.strip():
            raise ValueError("instance_url is required.")
        normalized = self.instance_url.rstrip("/")
        if not normalized.startswith("https://"):
            raise ValueError("instance_url must use HTTPS.")
        object.__setattr__(self, "instance_url", normalized)

        if not self.client_id or not self.client_id.strip():
            raise ValueError("client_id is required.")

        if self.auth_mode not in {"delegated", "client_credentials"}:
            raise ValueError(
                "auth_mode must be 'delegated' or 'client_credentials'."
            )

        if self.auth_mode == "delegated" and not self.redirect_uri:
            raise ValueError("redirect_uri is required for delegated mode.")

        if self.auth_mode == "client_credentials" and not self.client_secret:
            raise ValueError(
                "client_secret is required for client_credentials mode."
            )

        api_path = "/" + self.api_path.strip("/")
        if not api_path:
            api_path = "/api/now"
        object.__setattr__(self, "api_path", api_path)
        object.__setattr__(self, "scopes", tuple(dict.fromkeys(self.scopes)))

    @property
    def authorize_url(self) -> str:
        return f"{self.instance_url}/oauth_auth.do"

    @property
    def token_url(self) -> str:
        return f"{self.instance_url}/oauth_token.do"

    @property
    def rest_base_url(self) -> str:
        version = (
            f"/{self.api_version.strip('/')}"
            if self.api_version
            else ""
        )
        return f"{self.instance_url}{self.api_path}{version}"


@dataclass(frozen=True)
class ServiceNowConnectionStatus:
    connected: bool
    auth_mode: str
    instance_url: str
    error: Optional[str] = None


@dataclass(frozen=True)
class ServiceNowRecord:
    sys_id: Optional[str]
    fields: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_api(cls, payload: Mapping[str, Any]) -> "ServiceNowRecord":
        values = dict(payload)
        sys_id = values.get("sys_id")
        return cls(
            sys_id=str(sys_id) if sys_id is not None else None,
            fields=values,
        )


@dataclass(frozen=True)
class ServiceNowQueryResult:
    records: List[ServiceNowRecord]
    count: int
    next_offset: Optional[int] = None

    @classmethod
    def from_api(
        cls,
        payload: Mapping[str, Any],
        *,
        requested_offset: int = 0,
        limit: int = 100,
    ) -> "ServiceNowQueryResult":
        records = [
            ServiceNowRecord.from_api(item)
            for item in (payload.get("result") or [])
        ]
        count = len(records)
        next_offset = (
            requested_offset + count
            if count >= limit and count > 0
            else None
        )
        return cls(
            records=records,
            count=count,
            next_offset=next_offset,
        )


@dataclass(frozen=True)
class ServiceNowCapabilities:
    read_incidents: bool = True
    read_requests: bool = True
    read_changes: bool = True
    read_records: bool = True
    query_records: bool = True
    write_records: bool = False
    delete_records: bool = False

    def as_dict(self) -> Dict[str, bool]:
        return {
            "read_incidents": self.read_incidents,
            "read_requests": self.read_requests,
            "read_changes": self.read_changes,
            "read_records": self.read_records,
            "query_records": self.query_records,
            "write_records": self.write_records,
            "delete_records": self.delete_records,
        }
