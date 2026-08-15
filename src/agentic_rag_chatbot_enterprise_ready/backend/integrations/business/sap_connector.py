"""Enterprise SAP OData connector.

Initial scope is read-only OData access suitable for SAP S/4HANA and other
SAP products exposing governed OData services.

The connector does not assume a particular business API such as Sales Orders
or Purchase Orders because SAP landscapes expose different services and
customizations. Business API adapters can be added above this stable boundary.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Mapping, Optional, Sequence

from .sap.auth import SAPTokenProvider
from .sap.client import SAPODataClient
from .sap.exceptions import SAPConfigurationError, SAPQueryError
from .sap.models import (
    SAPAuthConfig,
    SAPCapabilities,
    SAPConnectionStatus,
    SAPODataResult,
)

_SAFE_SEGMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_.-]*$")
_SAFE_PROPERTY = re.compile(r"^[A-Za-z_][A-Za-z0-9_.-]*$")
_ALLOWED_FILTER_CHARS = re.compile(r"^[\w\s().,'\"=<>!:+*/%_-]+$", re.UNICODE)


class SAPConnector:
    """SAP OData capability facade."""

    PROVIDER_NAME = "sap"

    def __init__(
        self,
        config: SAPAuthConfig,
        *,
        access_token: Optional[str] = None,
        client: Optional[SAPODataClient] = None,
        capabilities: Optional[SAPCapabilities] = None,
    ) -> None:
        self.config = config
        self.auth = SAPTokenProvider(config)
        self.capabilities = capabilities or SAPCapabilities()
        self._access_token = access_token
        self._client = client

        if client is None:
            self._client = SAPODataClient(
                config,
                access_token=access_token,
            )

    @property
    def is_authenticated(self) -> bool:
        return (
            self.config.auth_mode == "basic"
            or self._access_token is not None
        )

    def get_capabilities(self) -> Dict[str, bool]:
        return self.capabilities.as_dict()

    async def authenticate(self) -> SAPConnectionStatus:
        if self.config.auth_mode == "oauth2_client_credentials":
            payload = await self.auth.acquire_token()
            self.set_access_token(payload["access_token"])

        return await self.health_check()

    def set_access_token(self, access_token: str) -> None:
        self._access_token = access_token
        self._client.set_access_token(access_token)

    def disconnect(self) -> None:
        self._access_token = None
        if self.config.auth_mode != "basic":
            self._client.access_token = None

    def _require_client(self) -> SAPODataClient:
        if self._client is None:
            raise SAPConfigurationError("SAP client is not initialized.")
        if self.config.auth_mode != "basic" and not self._access_token:
            raise SAPConfigurationError(
                "SAP is not authenticated. Authenticate first."
            )
        return self._client

    @staticmethod
    def _validate_segment(value: str, name: str) -> str:
        if not value or not _SAFE_SEGMENT.fullmatch(value):
            raise SAPQueryError(f"Unsafe {name}: {value!r}")
        return value

    @staticmethod
    def _validate_property(value: str) -> str:
        if not value or not _SAFE_PROPERTY.fullmatch(value):
            raise SAPQueryError(f"Unsafe property: {value!r}")
        return value

    @staticmethod
    def _validate_limit(value: int) -> int:
        if not isinstance(value, int) or not 1 <= value <= 1000:
            raise SAPQueryError("top must be an integer between 1 and 1000.")
        return value

    @staticmethod
    def _validate_filter(value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        if not isinstance(value, str) or len(value) > 2000:
            raise SAPQueryError("OData filter is invalid or too long.")
        if any(char in value for char in "\r\n\t"):
            raise SAPQueryError("OData filter contains control characters.")
        if not _ALLOWED_FILTER_CHARS.fullmatch(value):
            raise SAPQueryError("OData filter contains unsafe characters.")
        return value

    async def health_check(self) -> SAPConnectionStatus:
        client = self._require_client()

        try:
            # $metadata is a protocol-level read and does not assume a
            # business-specific SAP service/entity exists.
            await client.get("$metadata")
            return SAPConnectionStatus(
                connected=True,
                base_url=self.config.base_url,
                auth_mode=self.config.auth_mode,
                api_version=self.config.api_version,
            )
        except Exception as exc:
            return SAPConnectionStatus(
                connected=False,
                base_url=self.config.base_url,
                auth_mode=self.config.auth_mode,
                api_version=self.config.api_version,
                error=str(exc),
            )

    async def metadata(self) -> Any:
        return await self._require_client().get("$metadata")

    async def query_entity_set(
        self,
        *,
        entity_set: str,
        select: Optional[Sequence[str]] = None,
        filter_expression: Optional[str] = None,
        order_by: Optional[Sequence[str]] = None,
        top: int = 100,
        skip: int = 0,
        count: bool = False,
    ) -> SAPODataResult:
        """Read an OData entity set without exposing arbitrary HTTP operations."""
        entity_set = self._validate_segment(entity_set, "entity_set")
        top = self._validate_limit(top)

        if not isinstance(skip, int) or skip < 0:
            raise SAPQueryError("skip must be a non-negative integer.")

        params: Dict[str, Any] = {
            "$top": top,
            "$skip": skip,
        }

        if select:
            params["$select"] = ",".join(
                self._validate_property(item)
                for item in select
            )

        validated_filter = self._validate_filter(filter_expression)
        if validated_filter:
            params["$filter"] = validated_filter

        if order_by:
            clauses = []
            for item in order_by:
                parts = item.strip().split()
                if len(parts) > 2 or not parts:
                    raise SAPQueryError(f"Invalid order_by item: {item!r}")
                property_name = self._validate_property(parts[0])
                direction = ""
                if len(parts) == 2:
                    if parts[1].lower() not in {"asc", "desc"}:
                        raise SAPQueryError(
                            f"Invalid order direction: {parts[1]!r}"
                        )
                    direction = f" {parts[1].lower()}"
                clauses.append(property_name + direction)
            params["$orderby"] = ",".join(clauses)

        if count:
            params["$count"] = "true" if self.config.api_version == "v4" else "allpages"

        payload = await self._require_client().get(
            entity_set,
            params=params,
        )
        return SAPODataResult.from_api(payload)

    async def get_entity(
        self,
        *,
        entity_set: str,
        key: str,
        select: Optional[Sequence[str]] = None,
    ) -> Mapping[str, Any]:
        entity_set = self._validate_segment(entity_set, "entity_set")
        if not key or len(key) > 512:
            raise SAPQueryError("key is required and must be <= 512 characters.")

        # Keys are accepted as a complete OData key expression, but control
        # characters and path traversal are never accepted.
        if any(char in key for char in "\r\n\t/\\"):
            raise SAPQueryError("Invalid OData entity key.")

        params: Dict[str, Any] = {}
        if select:
            params["$select"] = ",".join(
                self._validate_property(item)
                for item in select
            )

        payload = await self._require_client().get(
            f"{entity_set}({key})",
            params=params,
        )
        return payload

    async def follow_next_link(self, next_link: str) -> SAPODataResult:
        """Follow only an OData next link belonging to the same SAP host."""
        if not next_link:
            raise SAPQueryError("next_link is required.")

        payload = await self._require_client().get(next_link)
        return SAPODataResult.from_api(payload)
