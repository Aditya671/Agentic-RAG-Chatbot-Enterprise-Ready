"""Enterprise SharePoint Online connector.

Public application boundary for SharePoint integration.

Provider API:
- Microsoft Graph v1.0
- Microsoft Entra ID
- delegated user authorization for opt-in experiences
- app-only authentication for controlled service scenarios

The connector exposes deterministic business capabilities instead of exposing
raw Graph calls to the agent.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence

from .sharepoint.auth import SharePointAuthConfig, SharePointTokenProvider
from .sharepoint.client import SharePointGraphClient
from .sharepoint.exceptions import SharePointConfigurationError
from .sharepoint.models import (
    SharePointCapabilities,
    SharePointConnectionStatus,
    SharePointDrive,
    SharePointItem,
    SharePointSite,
)


class SharePointConnector:
    """SharePoint integration facade used by the application/integration manager."""

    PROVIDER_NAME = "sharepoint"
    API_VERSION = "v1.0"

    def __init__(
        self,
        config: SharePointAuthConfig,
        *,
        access_token: Optional[str] = None,
        graph_client: Optional[SharePointGraphClient] = None,
        capabilities: Optional[SharePointCapabilities] = None,
    ) -> None:
        self.config = config
        self.auth = SharePointTokenProvider(config)
        self.capabilities = capabilities or SharePointCapabilities()
        self._access_token = access_token
        self._client = graph_client

        if access_token and graph_client is None:
            self._client = SharePointGraphClient(
                access_token=access_token,
                graph_base_url=config.graph_base_url,
            )

    @property
    def is_authenticated(self) -> bool:
        return bool(self._client)

    def get_capabilities(self) -> Dict[str, bool]:
        return self.capabilities.as_dict()

    def get_authorization_url(
        self,
        *,
        state: Optional[str] = None,
        pkce_verifier: Optional[str] = None,
    ) -> tuple[str, str, Optional[str]]:
        verifier = pkce_verifier
        challenge = None

        if verifier:
            challenge = self.auth.create_pkce_challenge(verifier)

        url, generated_state = self.auth.build_authorization_url(
            state=state,
            code_challenge=challenge,
        )
        return url, generated_state, verifier

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

    async def authenticate_app_only(self) -> SharePointConnectionStatus:
        token = await self.auth.acquire_app_only_token()
        self._access_token = token
        self._client = SharePointGraphClient(
            access_token=token,
            graph_base_url=self.config.graph_base_url,
        )
        return await self.health_check()

    def set_access_token(self, access_token: str) -> None:
        if not access_token:
            raise SharePointConfigurationError("access_token is required.")

        self._access_token = access_token
        self._client = SharePointGraphClient(
            access_token=access_token,
            graph_base_url=self.config.graph_base_url,
        )

    def disconnect(self) -> None:
        # Do not persist or log the token. Drop local references only.
        self._access_token = None
        self._client = None

    def _require_client(self) -> SharePointGraphClient:
        if self._client is None:
            raise SharePointConfigurationError(
                "SharePoint is not connected. Authenticate first."
            )
        return self._client

    async def health_check(self) -> SharePointConnectionStatus:
        client = self._require_client()

        try:
            if self.config.auth_mode == "delegated":
                me = await client.get("/me?$select=id,userPrincipalName,displayName")
                return SharePointConnectionStatus(
                    connected=True,
                    auth_mode=self.config.auth_mode,
                    tenant_id=self.config.tenant_id,
                    graph_base_url=self.config.graph_base_url,
                    user_id=me.get("id"),
                    user_principal_name=me.get("userPrincipalName"),
                    scopes=list(self.config.delegated_scopes),
                )

            # /sites/root is a useful app-only SharePoint reachability check,
            # while avoiding a tenant-wide search during connection validation.
            await client.get("/sites/root?$select=id,name,webUrl")
            return SharePointConnectionStatus(
                connected=True,
                auth_mode=self.config.auth_mode,
                tenant_id=self.config.tenant_id,
                graph_base_url=self.config.graph_base_url,
                scopes=[".default"],
            )
        except Exception as exc:
            return SharePointConnectionStatus(
                connected=False,
                auth_mode=self.config.auth_mode,
                tenant_id=self.config.tenant_id,
                graph_base_url=self.config.graph_base_url,
                scopes=list(self.config.delegated_scopes),
                error=str(exc),
            )

    async def get_site_by_path(self, hostname: str, site_path: str) -> SharePointSite:
        if not hostname or not hostname.strip():
            raise ValueError("hostname is required.")
        if not site_path or not site_path.strip():
            raise ValueError("site_path is required.")

        path = site_path.strip("/")
        encoded = path.replace("'", "''")
        client = self._require_client()

        payload = await client.get(
            f"/sites/{hostname}:/{encoded}",
            params={"$select": "id,name,displayName,webUrl,description,siteCollection"},
        )
        return SharePointSite.from_graph(payload)

    async def get_site(self, site_id: str) -> SharePointSite:
        client = self._require_client()
        payload = await client.get(
            f"/sites/{site_id}",
            params={
                "$select": "id,name,displayName,webUrl,description,siteCollection"
            },
        )
        return SharePointSite.from_graph(payload)

    async def list_drives(self, site_id: str) -> List[SharePointDrive]:
        client = self._require_client()
        values = await client.paginate(
            f"/sites/{site_id}/drives",
            params={"$select": "id,name,webUrl,driveType"},
        )
        return [SharePointDrive.from_graph(value) for value in values]

    async def get_drive(self, drive_id: str) -> SharePointDrive:
        client = self._require_client()
        payload = await client.get(
            f"/drives/{drive_id}",
            params={"$select": "id,name,webUrl,driveType"},
        )
        return SharePointDrive.from_graph(payload)

    async def list_children(
        self,
        drive_id: str,
        *,
        item_id: Optional[str] = None,
    ) -> List[SharePointItem]:
        client = self._require_client()

        endpoint = (
            f"/drives/{drive_id}/root/children"
            if not item_id
            else f"/drives/{drive_id}/items/{item_id}/children"
        )

        values = await client.paginate(
            endpoint,
            params={
                "$select": (
                    "id,name,webUrl,size,file,folder,parentReference,"
                    "lastModifiedDateTime,createdDateTime"
                )
            },
        )
        return [SharePointItem.from_graph(value) for value in values]

    async def get_item(
        self,
        drive_id: str,
        item_id: str,
    ) -> SharePointItem:
        client = self._require_client()
        payload = await client.get(
            f"/drives/{drive_id}/items/{item_id}",
            params={
                "$select": (
                    "id,name,webUrl,size,file,folder,parentReference,"
                    "lastModifiedDateTime,createdDateTime"
                )
            },
        )
        return SharePointItem.from_graph(payload)

    async def download_file(
        self,
        drive_id: str,
        item_id: str,
    ) -> bytes:
        client = self._require_client()
        payload = await client.get(
            f"/drives/{drive_id}/items/{item_id}/content"
        )
        if not isinstance(payload, (bytes, bytearray)):
            raise TypeError("SharePoint file download did not return bytes.")
        return bytes(payload)

    async def search_files(
        self,
        query: str,
        *,
        site_id: Optional[str] = None,
        top: int = 25,
    ) -> List[SharePointItem]:
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must be a non-empty string.")
        if not isinstance(top, int) or not 1 <= top <= 200:
            raise ValueError("top must be between 1 and 200.")

        client = self._require_client()

        # Microsoft Graph Search is tenant-wide by default. The optional
        # site filter keeps the connector within an explicitly selected site.
        payload = await client.post(
            "/search/query",
            json={
                "requests": [
                    {
                        "entityTypes": ["driveItem"],
                        "query": {"queryString": query.strip()},
                        "from": 0,
                        "size": top,
                    }
                ]
            },
        )

        items: List[SharePointItem] = []
        for hit_container in payload.get("value", []):
            for hit in hit_container.get("hitsContainers", []):
                for hit_item in hit.get("hits", []):
                    resource = hit_item.get("resource") or {}
                    parent_reference = resource.get("parentReference") or {}

                    if site_id and parent_reference.get("siteId") != site_id:
                        continue

                    items.append(SharePointItem.from_graph(resource))

        return items

    async def list_site_files(
        self,
        hostname: str,
        site_path: str,
    ) -> List[SharePointItem]:
        """Convenience capability: resolve a site, choose its default drive,
        and list root-level files/folders.
        """
        site = await self.get_site_by_path(hostname, site_path)
        drives = await self.list_drives(site.id)
        if not drives:
            return []
        return await self.list_children(drives[0].id)

    async def get_user(self) -> Mapping[str, Any]:
        if self.config.auth_mode != "delegated":
            raise SharePointConfigurationError(
                "get_user is only available in delegated authentication mode."
            )

        client = self._require_client()
        return await client.get(
            "/me",
            params={
                "$select": "id,displayName,mail,userPrincipalName",
            },
        )
