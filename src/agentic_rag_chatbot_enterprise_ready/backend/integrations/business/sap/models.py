"""Typed models for the SAP integration boundary."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional, Sequence


@dataclass(frozen=True)
class SAPAuthConfig:
    """Configuration for a SAP OData endpoint.

    The connector intentionally keeps the target generic because SAP
    landscapes may expose S/4HANA Cloud, S/4HANA on-premise through BTP
    connectivity, or another SAP product using OData.
    """

    base_url: str
    auth_mode: str = "oauth2_client_credentials"
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    token_url: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    api_version: str = "v4"
    destination_name: Optional[str] = None

    def __post_init__(self) -> None:
        normalized = self.base_url.rstrip("/")
        if not normalized.startswith("https://"):
            raise ValueError("base_url must use HTTPS.")
        object.__setattr__(self, "base_url", normalized)

        if self.auth_mode not in {
            "oauth2_client_credentials",
            "basic",
            "bearer",
        }:
            raise ValueError(
                "auth_mode must be oauth2_client_credentials, basic, or bearer."
            )

        if self.api_version not in {"v2", "v4"}:
            raise ValueError("api_version must be v2 or v4.")

        if self.auth_mode == "oauth2_client_credentials":
            if not self.client_id or not self.client_secret or not self.token_url:
                raise ValueError(
                    "client_id, client_secret, and token_url are required "
                    "for OAuth2 client credentials."
                )
            if not self.token_url.startswith("https://"):
                raise ValueError("token_url must use HTTPS.")

        if self.auth_mode == "basic":
            if not self.username or self.password is None:
                raise ValueError(
                    "username and password are required for basic auth."
                )

    @property
    def odata_root(self) -> str:
        return self.base_url


@dataclass(frozen=True)
class SAPConnectionStatus:
    connected: bool
    base_url: str
    auth_mode: str
    api_version: str
    error: Optional[str] = None


@dataclass(frozen=True)
class SAPODataResult:
    records: list[Dict[str, Any]]
    count: Optional[int] = None
    next_link: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_api(cls, payload: Mapping[str, Any]) -> "SAPODataResult":
        # OData V4: {"value": [...]}
        if "value" in payload:
            values = payload.get("value") or []
            return cls(
                records=[dict(item) for item in values],
                count=payload.get("@odata.count"),
                next_link=payload.get("@odata.nextLink"),
                raw=dict(payload),
            )

        # OData V2: {"d": {"results": [...], "__next": "..."}}
        data = payload.get("d") or {}
        values = data.get("results") or []
        return cls(
            records=[dict(item) for item in values],
            count=payload.get("d", {}).get("__count")
            if isinstance(payload.get("d"), dict)
            else None,
            next_link=data.get("__next"),
            raw=dict(payload),
        )


@dataclass(frozen=True)
class SAPCapabilities:
    read_odata: bool = True
    query_odata: bool = True
    metadata: bool = True
    write_records: bool = False
    delete_records: bool = False
    execute_actions: bool = False

    def as_dict(self) -> Dict[str, bool]:
        return {
            "read_odata": self.read_odata,
            "query_odata": self.query_odata,
            "metadata": self.metadata,
            "write_records": self.write_records,
            "delete_records": self.delete_records,
            "execute_actions": self.execute_actions,
        }
