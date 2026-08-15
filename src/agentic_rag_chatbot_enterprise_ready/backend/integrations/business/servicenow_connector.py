"""Enterprise ServiceNow connector.

Public application-facing boundary for the independent enterprise integration
layer. Initial scope is read-only ITSM access through ServiceNow's Table API.

The connector is deliberately capability-oriented; agent-facing code should
prefer the typed incident/request/change methods over arbitrary table access.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Mapping, Optional, Sequence

from .servicenow.auth import ServiceNowTokenProvider
from .servicenow.client import ServiceNowRESTClient
from .servicenow.exceptions import (
    ServiceNowConfigurationError,
    ServiceNowQueryError,
)
from .servicenow.models import (
    ServiceNowAuthConfig,
    ServiceNowCapabilities,
    ServiceNowConnectionStatus,
    ServiceNowQueryResult,
)

_SAFE_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class ServiceNowConnector:
    """ServiceNow capability facade."""

    PROVIDER_NAME = "servicenow"

    def __init__(
        self,
        config: ServiceNowAuthConfig,
        *,
        access_token: Optional[str] = None,
        rest_client: Optional[ServiceNowRESTClient] = None,
        capabilities: Optional[ServiceNowCapabilities] = None,
    ) -> None:
        self.config = config
        self.auth = ServiceNowTokenProvider(config)
        self.capabilities = capabilities or ServiceNowCapabilities()
        self._access_token = access_token
        self._client = rest_client

        if access_token and rest_client is None:
            self._client = ServiceNowRESTClient(
                access_token=access_token,
                instance_url=config.instance_url,
                api_path=config.api_path,
                api_version=config.api_version,
            )

    @property
    def is_authenticated(self) -> bool:
        return self._client is not None

    def get_capabilities(self) -> Dict[str, bool]:
        return self.capabilities.as_dict()

    def get_authorization_url(
        self,
        *,
        state: Optional[str] = None,
        pkce_verifier: Optional[str] = None,
    ) -> tuple[str, str]:
        return self.auth.build_authorization_url(
            state=state,
            pkce_verifier=pkce_verifier,
        )

    async def exchange_authorization_code(
        self,
        *,
        code: str,
        pkce_verifier: Optional[str] = None,
    ) -> Dict[str, Any]:
        return await self.auth.exchange_authorization_code(
            code=code,
            pkce_verifier=pkce_verifier,
        )

    async def authenticate_client_credentials(
        self,
    ) -> ServiceNowConnectionStatus:
        payload = await self.auth.acquire_client_credentials_token()
        self.set_access_token(payload["access_token"])
        return await self.health_check()

    def set_access_token(self, access_token: str) -> None:
        if not access_token:
            raise ServiceNowConfigurationError("access_token is required.")

        self._access_token = access_token
        self._client = ServiceNowRESTClient(
            access_token=access_token,
            instance_url=self.config.instance_url,
            api_path=self.config.api_path,
            api_version=self.config.api_version,
        )

    def disconnect(self) -> None:
        self._access_token = None
        self._client = None

    def _require_client(self) -> ServiceNowRESTClient:
        if self._client is None:
            raise ServiceNowConfigurationError(
                "ServiceNow is not connected. Authenticate first."
            )
        return self._client

    async def health_check(self) -> ServiceNowConnectionStatus:
        client = self._require_client()

        try:
            await client.get(
                "/table/incident",
                params={
                    "sysparm_limit": 1,
                    "sysparm_fields": "sys_id",
                },
            )
            return ServiceNowConnectionStatus(
                connected=True,
                auth_mode=self.config.auth_mode,
                instance_url=self.config.instance_url,
            )
        except Exception as exc:
            return ServiceNowConnectionStatus(
                connected=False,
                auth_mode=self.config.auth_mode,
                instance_url=self.config.instance_url,
                error=str(exc),
            )

    @staticmethod
    def _validate_identifier(value: str, name: str) -> str:
        if not value or not _SAFE_IDENTIFIER.fullmatch(value):
            raise ServiceNowQueryError(
                f"Unsafe {name}: {value!r}"
            )
        return value

    @staticmethod
    def _validate_limit(limit: int) -> int:
        if not isinstance(limit, int) or not 1 <= limit <= 1000:
            raise ServiceNowQueryError(
                "limit must be an integer between 1 and 1000."
            )
        return limit

    async def query_table(
        self,
        *,
        table: str,
        encoded_query: Optional[str] = None,
        fields: Optional[Sequence[str]] = None,
        limit: int = 100,
        offset: int = 0,
        display_value: str = "false",
    ) -> ServiceNowQueryResult:
        """Read records from an allowlisted table using ServiceNow sysparm_query.

        This is a controlled read capability. No arbitrary HTTP method is
        exposed, and table/field identifiers are validated before dispatch.
        """
        table = self._validate_identifier(table, "table")
        limit = self._validate_limit(limit)

        if not isinstance(offset, int) or offset < 0:
            raise ServiceNowQueryError("offset must be a non-negative integer.")

        if display_value not in {"true", "false", "all"}:
            raise ServiceNowQueryError(
                "display_value must be true, false, or all."
            )

        validated_fields = None
        if fields:
            validated_fields = [
                self._validate_identifier(field, "field")
                for field in fields
            ]

        params: Dict[str, Any] = {
            "sysparm_limit": limit,
            "sysparm_offset": offset,
            "sysparm_display_value": display_value,
        }

        if encoded_query:
            if not isinstance(encoded_query, str):
                raise ServiceNowQueryError(
                    "encoded_query must be a string."
                )
            if len(encoded_query) > 2000:
                raise ServiceNowQueryError(
                    "encoded_query is too long."
                )
            params["sysparm_query"] = encoded_query

        if validated_fields:
            params["sysparm_fields"] = ",".join(validated_fields)

        payload = await self._require_client().get(
            f"/table/{table}",
            params=params,
        )
        return ServiceNowQueryResult.from_api(
            payload,
            requested_offset=offset,
            limit=limit,
        )

    async def get_record(
        self,
        *,
        table: str,
        sys_id: str,
        fields: Optional[Sequence[str]] = None,
        display_value: str = "false",
    ) -> Mapping[str, Any]:
        table = self._validate_identifier(table, "table")
        if not sys_id or not re.fullmatch(r"^[A-Za-z0-9]{32}$", sys_id):
            raise ServiceNowQueryError(
                "sys_id must be a 32-character ServiceNow identifier."
            )

        params: Dict[str, Any] = {
            "sysparm_display_value": display_value,
        }

        if fields:
            params["sysparm_fields"] = ",".join(
                self._validate_identifier(field, "field")
                for field in fields
            )

        payload = await self._require_client().get(
            f"/table/{table}/{sys_id}",
            params=params,
        )
        return payload.get("result") or {}

    async def search_incidents(
        self,
        query: str,
        *,
        limit: int = 25,
    ) -> ServiceNowQueryResult:
        if not query or not query.strip():
            raise ServiceNowQueryError("incident search query is required.")

        # The input is treated as a literal search phrase against short_description.
        # We do not expose arbitrary encoded-query construction through this method.
        phrase = query.strip().replace("^", "^^")
        encoded = f"short_descriptionLIKE{phrase}"
        return await self.query_table(
            table="incident",
            encoded_query=encoded,
            fields=(
                "sys_id",
                "number",
                "short_description",
                "state",
                "priority",
                "assigned_to",
                "assignment_group",
                "opened_at",
                "updated_on",
            ),
            limit=limit,
            display_value="true",
        )

    async def search_requests(
        self,
        query: str,
        *,
        limit: int = 25,
    ) -> ServiceNowQueryResult:
        if not query or not query.strip():
            raise ServiceNowQueryError("request search query is required.")

        phrase = query.strip().replace("^", "^^")
        encoded = f"short_descriptionLIKE{phrase}"
        return await self.query_table(
            table="sc_request",
            encoded_query=encoded,
            fields=(
                "sys_id",
                "number",
                "short_description",
                "request_state",
                "requested_for",
                "opened_at",
                "updated_on",
            ),
            limit=limit,
            display_value="true",
        )

    async def search_changes(
        self,
        query: str,
        *,
        limit: int = 25,
    ) -> ServiceNowQueryResult:
        if not query or not query.strip():
            raise ServiceNowQueryError("change search query is required.")

        phrase = query.strip().replace("^", "^^")
        encoded = f"short_descriptionLIKE{phrase}"
        return await self.query_table(
            table="change_request",
            encoded_query=encoded,
            fields=(
                "sys_id",
                "number",
                "short_description",
                "state",
                "risk",
                "priority",
                "assigned_to",
                "assignment_group",
                "start_date",
                "end_date",
            ),
            limit=limit,
            display_value="true",
        )
