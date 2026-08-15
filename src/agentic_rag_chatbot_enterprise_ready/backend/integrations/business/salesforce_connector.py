"""Enterprise Salesforce connector.

Public application-facing boundary for the independent enterprise integration
layer. The connector targets Salesforce Platform REST API v67.0 and External
Client Apps.

The initial business surface is read-only.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Mapping, Optional

from .salesforce.auth import SalesforceTokenProvider
from .salesforce.client import SalesforceRESTClient
from .salesforce.exceptions import (
    SalesforceConfigurationError,
    SalesforceQueryError,
)
from .salesforce.models import (
    SalesforceAuthConfig,
    SalesforceCapabilities,
    SalesforceConnectionStatus,
    SalesforceQueryResult,
    SalesforceRecord,
)

_SAFE_OBJECT = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
_SAFE_FIELD = re.compile(r"^[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)?$")


class SalesforceConnector:
    """Salesforce capability facade."""

    PROVIDER_NAME = "salesforce"
    API_VERSION = "v67.0"

    def __init__(
        self,
        config: SalesforceAuthConfig,
        *,
        access_token: Optional[str] = None,
        instance_url: Optional[str] = None,
        rest_client: Optional[SalesforceRESTClient] = None,
        capabilities: Optional[SalesforceCapabilities] = None,
    ) -> None:
        self.config = config
        self.auth = SalesforceTokenProvider(config)
        self.capabilities = capabilities or SalesforceCapabilities()
        self._access_token = access_token
        self._instance_url = instance_url
        self._client = rest_client

        if access_token and instance_url and rest_client is None:
            self._client = SalesforceRESTClient(
                access_token=access_token,
                instance_url=instance_url,
                api_version=config.api_version,
            )

    @property
    def is_authenticated(self) -> bool:
        return self._client is not None

    @property
    def instance_url(self) -> Optional[str]:
        return self._instance_url

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

    async def authenticate_client_credentials(self) -> SalesforceConnectionStatus:
        token_payload = await self.auth.acquire_client_credentials_token()
        self.set_credentials(
            access_token=token_payload["access_token"],
            instance_url=token_payload["instance_url"],
        )
        return await self.health_check()

    def set_credentials(self, *, access_token: str, instance_url: str) -> None:
        if not access_token:
            raise SalesforceConfigurationError("access_token is required.")
        if not instance_url.startswith("https://"):
            raise SalesforceConfigurationError(
                "instance_url must use HTTPS."
            )

        self._access_token = access_token
        self._instance_url = instance_url.rstrip("/")
        self._client = SalesforceRESTClient(
            access_token=access_token,
            instance_url=self._instance_url,
            api_version=self.config.api_version,
        )

    def disconnect(self) -> None:
        self._access_token = None
        self._instance_url = None
        self._client = None

    def _require_client(self) -> SalesforceRESTClient:
        if self._client is None:
            raise SalesforceConfigurationError(
                "Salesforce is not connected. Authenticate first."
            )
        return self._client

    async def health_check(self) -> SalesforceConnectionStatus:
        client = self._require_client()

        try:
            identity = await client.get("/sobjects")
            # /sobjects is used only as a lightweight authenticated platform
            # check; the payload is intentionally not exposed to the agent.
            _ = identity
            return SalesforceConnectionStatus(
                connected=True,
                auth_mode=self.config.auth_mode,
                instance_url=self._instance_url,
                api_version=self.config.api_version,
            )
        except Exception as exc:
            return SalesforceConnectionStatus(
                connected=False,
                auth_mode=self.config.auth_mode,
                instance_url=self._instance_url,
                api_version=self.config.api_version,
                error=str(exc),
            )

    async def get_identity(self) -> Mapping[str, Any]:
        client = self._require_client()
        return await client.get("/connect/identity")

    async def query_soql(self, soql: str) -> SalesforceQueryResult:
        """Execute a caller-supplied SOQL query.

        This is a controlled integration capability, not an unrestricted HTTP
        endpoint. Production agent tooling should prefer the typed business
        search methods below.
        """
        if not isinstance(soql, str) or not soql.strip():
            raise SalesforceQueryError("SOQL query must be non-empty.")

        normalized = soql.strip()
        if ";" in normalized:
            raise SalesforceQueryError("Multiple SOQL statements are not allowed.")
        if not re.match(r"(?is)^select\s+", normalized):
            raise SalesforceQueryError("Only SELECT SOQL queries are allowed.")

        client = self._require_client()
        payload = await client.get(
            "/query",
            params={"q": normalized},
        )
        return SalesforceQueryResult.from_api(payload)

    async def query_more(self, next_records_url: str) -> SalesforceQueryResult:
        if not next_records_url.startswith(self._instance_url or ""):
            raise SalesforceQueryError(
                "next_records_url must belong to the connected Salesforce instance."
            )
        client = self._require_client()
        payload = await client.get(next_records_url)
        return SalesforceQueryResult.from_api(payload)

    @staticmethod
    def _escape_soql_string(value: str) -> str:
        # SOQL string literals use backslash escaping. Also escape the single
        # quote so user-controlled search values cannot change the literal.
        return value.replace("\\", "\\\\").replace("'", "\\'")

    @staticmethod
    def _validate_field(field: str) -> str:
        if not _SAFE_FIELD.fullmatch(field):
            raise SalesforceQueryError(f"Unsafe Salesforce field: {field!r}")
        return field

    @staticmethod
    def _validate_object(object_name: str) -> str:
        if not _SAFE_OBJECT.fullmatch(object_name):
            raise SalesforceQueryError(
                f"Unsafe Salesforce object name: {object_name!r}"
            )
        return object_name

    async def search_records(
        self,
        *,
        object_name: str,
        search_field: str,
        query: str,
        fields: tuple[str, ...] = ("Id", "Name"),
        limit: int = 25,
    ) -> SalesforceQueryResult:
        if not query or not query.strip():
            raise SalesforceQueryError("query must be non-empty.")
        if not 1 <= limit <= 200:
            raise SalesforceQueryError("limit must be between 1 and 200.")

        obj = self._validate_object(object_name)
        field = self._validate_field(search_field)
        selected_fields = tuple(self._validate_field(field_name) for field_name in fields)
        if not selected_fields:
            raise SalesforceQueryError("At least one field is required.")

        value = self._escape_soql_string(query.strip())
        projection = ", ".join(selected_fields)
        soql = (
            f"SELECT {projection} FROM {obj} "
            f"WHERE {field} LIKE '%{value}%' "
            f"ORDER BY LastModifiedDate DESC "
            f"LIMIT {limit}"
        )
        return await self.query_soql(soql)

    async def search_accounts(
        self,
        query: str,
        *,
        limit: int = 25,
    ) -> SalesforceQueryResult:
        return await self.search_records(
            object_name="Account",
            search_field="Name",
            query=query,
            fields=("Id", "Name", "Industry", "Type", "Website"),
            limit=limit,
        )

    async def search_contacts(
        self,
        query: str,
        *,
        limit: int = 25,
    ) -> SalesforceQueryResult:
        return await self.search_records(
            object_name="Contact",
            search_field="Name",
            query=query,
            fields=("Id", "Name", "Email", "Phone", "Account.Name"),
            limit=limit,
        )

    async def search_opportunities(
        self,
        query: str,
        *,
        limit: int = 25,
    ) -> SalesforceQueryResult:
        return await self.search_records(
            object_name="Opportunity",
            search_field="Name",
            query=query,
            fields=("Id", "Name", "StageName", "Amount", "CloseDate", "Account.Name"),
            limit=limit,
        )

    async def search_cases(
        self,
        query: str,
        *,
        limit: int = 25,
    ) -> SalesforceQueryResult:
        return await self.search_records(
            object_name="Case",
            search_field="Subject",
            query=query,
            fields=("Id", "CaseNumber", "Subject", "Status", "Priority", "Account.Name"),
            limit=limit,
        )
