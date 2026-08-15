"""Typed models at the Salesforce integration boundary."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional


@dataclass(frozen=True)
class SalesforceAuthConfig:
    """OAuth configuration for a Salesforce External Client App."""

    client_id: str
    redirect_uri: Optional[str] = None
    client_secret: Optional[str] = None
    login_url: str = "https://login.salesforce.com"
    api_version: str = "v67.0"
    auth_mode: str = "delegated"
    scopes: tuple[str, ...] = ("api", "refresh_token", "offline_access")
    require_pkce: bool = False

    def __post_init__(self) -> None:
        if not self.client_id or not self.client_id.strip():
            raise ValueError("client_id is required.")
        if not self.login_url.startswith("https://"):
            raise ValueError("login_url must use HTTPS.")
        if not self.api_version.startswith("v"):
            raise ValueError("api_version must look like vXX.0.")
        if self.auth_mode not in {"delegated", "client_credentials"}:
            raise ValueError(
                "auth_mode must be 'delegated' or 'client_credentials'."
            )
        if self.auth_mode == "delegated" and not self.redirect_uri:
            raise ValueError("redirect_uri is required for delegated mode.")
        if self.auth_mode == "client_credentials" and not self.client_secret:
            raise ValueError("client_secret is required for client_credentials.")
        object.__setattr__(self, "scopes", tuple(dict.fromkeys(self.scopes)))

    @property
    def authorize_url(self) -> str:
        return f"{self.login_url.rstrip('/')}/services/oauth2/authorize"

    @property
    def token_url(self) -> str:
        return f"{self.login_url.rstrip('/')}/services/oauth2/token"


@dataclass(frozen=True)
class SalesforceConnectionStatus:
    connected: bool
    auth_mode: str
    instance_url: Optional[str]
    api_version: str
    organization_id: Optional[str] = None
    user_id: Optional[str] = None
    username: Optional[str] = None
    error: Optional[str] = None


@dataclass(frozen=True)
class SalesforceRecord:
    id: Optional[str]
    type: Optional[str]
    fields: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_api(cls, payload: Mapping[str, Any]) -> "SalesforceRecord":
        fields = {
            key: value
            for key, value in payload.items()
            if key not in {"attributes", "Id"}
        }
        attributes = payload.get("attributes") or {}
        return cls(
            id=payload.get("Id"),
            type=attributes.get("type"),
            fields=fields,
        )


@dataclass(frozen=True)
class SalesforceQueryResult:
    records: List[SalesforceRecord]
    total_size: int
    done: bool
    next_records_url: Optional[str] = None

    @classmethod
    def from_api(cls, payload: Mapping[str, Any]) -> "SalesforceQueryResult":
        return cls(
            records=[
                SalesforceRecord.from_api(record)
                for record in payload.get("records", [])
            ],
            total_size=int(payload.get("totalSize", 0)),
            done=bool(payload.get("done", True)),
            next_records_url=payload.get("nextRecordsUrl"),
        )


@dataclass(frozen=True)
class SalesforceCapabilities:
    read_records: bool = True
    query_soql: bool = True
    read_accounts: bool = True
    read_contacts: bool = True
    read_opportunities: bool = True
    read_cases: bool = True
    write_records: bool = False

    def as_dict(self) -> Dict[str, bool]:
        return {
            "read_records": self.read_records,
            "query_soql": self.query_soql,
            "read_accounts": self.read_accounts,
            "read_contacts": self.read_contacts,
            "read_opportunities": self.read_opportunities,
            "read_cases": self.read_cases,
            "write_records": self.write_records,
        }
