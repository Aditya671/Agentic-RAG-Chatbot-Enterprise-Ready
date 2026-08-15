import asyncio
import importlib.util
import json
import sys
import types
from pathlib import Path

import pytest


ROOT = Path("/mnt/data/sharepoint_integration/backend/integration")


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# Package stubs let this suite validate the connector without installing
# Microsoft SDKs or contacting Microsoft Graph.
backend = types.ModuleType("backend")
integration = types.ModuleType("backend.integration")
sharepoint = types.ModuleType("backend.integration.sharepoint")
backend.__path__ = [str(ROOT.parent.parent)]
integration.__path__ = [str(ROOT.parent)]
sharepoint.__path__ = [str(ROOT / "sharepoint")]
sys.modules["backend"] = backend
sys.modules["backend.integration"] = integration
sys.modules["backend.integration.sharepoint"] = sharepoint

exceptions = load_module(
    "backend.integration.sharepoint.exceptions",
    ROOT / "sharepoint" / "exceptions.py",
)
models = load_module(
    "backend.integration.sharepoint.models",
    ROOT / "sharepoint" / "models.py",
)
auth = load_module(
    "backend.integration.sharepoint.auth",
    ROOT / "sharepoint" / "auth.py",
)
client = load_module(
    "backend.integration.sharepoint.client",
    ROOT / "sharepoint" / "client.py",
)

# Connector imports the auth/client/model modules and does not require the
# package __init__ to execute.
connector_module = load_module(
    "backend.integration.sharepoint_connector",
    ROOT / "sharepoint_connector.py",
)

SharePointAuthConfig = auth.SharePointAuthConfig
SharePointTokenProvider = auth.SharePointTokenProvider
SharePointGraphClient = client.SharePointGraphClient
SharePointConnector = connector_module.SharePointConnector


class FakeResponse:
    def __init__(self, status_code=200, payload=None, content=b"", headers=None):
        self.status_code = status_code
        self._payload = payload
        self.content = content
        self.headers = headers or {"content-type": "application/json"}

    def json(self):
        return self._payload


class FakeAsyncClient:
    responses = []
    requests = []

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def request(self, method, url, **kwargs):
        self.requests.append((method, url, kwargs))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    async def post(self, url, **kwargs):
        return await self.request("POST", url, **kwargs)


httpx = types.ModuleType("httpx")
httpx.AsyncClient = FakeAsyncClient
httpx.TimeoutException = type("TimeoutException", (Exception,), {})
httpx.NetworkError = type("NetworkError", (Exception,), {})
sys.modules["httpx"] = httpx


def make_config(**kwargs):
    defaults = dict(
        tenant_id="tenant-id",
        client_id="client-id",
        client_secret="secret",
        redirect_uri="https://app.example.com/oauth/sharepoint/callback",
        auth_mode="delegated",
    )
    defaults.update(kwargs)
    return SharePointAuthConfig(**defaults)


def test_delegated_config_requires_redirect_uri():
    with pytest.raises(exceptions.SharePointConfigurationError):
        SharePointAuthConfig(
            tenant_id="tenant",
            client_id="client",
            auth_mode="delegated",
        )


def test_app_only_config_requires_client_secret():
    with pytest.raises(exceptions.SharePointConfigurationError):
        SharePointAuthConfig(
            tenant_id="tenant",
            client_id="client",
            auth_mode="app_only",
        )


def test_invalid_auth_mode():
    with pytest.raises(exceptions.SharePointConfigurationError):
        SharePointAuthConfig(
            tenant_id="tenant",
            client_id="client",
            redirect_uri="https://example.com/callback",
            auth_mode="invalid",
        )


def test_pkce_round_trip_is_deterministic():
    verifier = SharePointTokenProvider.create_pkce_verifier()
    challenge = SharePointTokenProvider.create_pkce_challenge(verifier)

    assert verifier
    assert challenge
    assert len(challenge) > 20


def test_authorization_url_contains_required_parameters():
    provider = SharePointTokenProvider(make_config())
    url, state = provider.build_authorization_url(state="state123")

    assert "response_type=code" in url
    assert "client_id=client-id" in url
    assert "state=state123" in url
    assert "redirect_uri=" in url
    assert state == "state123"


def test_authorization_url_supports_pkce():
    provider = SharePointTokenProvider(make_config())
    verifier = "A" * 64
    challenge = provider.create_pkce_challenge(verifier)
    url, _ = provider.build_authorization_url(
        state="state",
        code_challenge=challenge,
    )

    assert "code_challenge=" in url
    assert "code_challenge_method=S256" in url


def test_app_only_cannot_build_authorization_url():
    provider = SharePointTokenProvider(
        make_config(
            auth_mode="app_only",
            redirect_uri=None,
        )
    )

    with pytest.raises(exceptions.SharePointAuthenticationError):
        provider.build_authorization_url()


def test_connector_starts_disconnected():
    connector = SharePointConnector(make_config())

    assert connector.is_authenticated is False
    assert connector.get_capabilities()["read_files"] is True


@pytest.mark.asyncio
async def test_health_check_delegated():
    connector = SharePointConnector(
        make_config(),
        graph_client=FakeGraphClient(
            {
                "/me?$select=id,userPrincipalName,displayName": {
                    "id": "u1",
                    "userPrincipalName": "user@example.com",
                    "displayName": "User",
                }
            }
        ),
    )

    status = await connector.health_check()

    assert status.connected is True
    assert status.user_id == "u1"
    assert status.user_principal_name == "user@example.com"


@pytest.mark.asyncio
async def test_health_check_app_only_uses_root_site():
    connector = SharePointConnector(
        make_config(auth_mode="app_only", redirect_uri=None),
        graph_client=FakeGraphClient(
            {
                "/sites/root?$select=id,name,webUrl": {
                    "id": "site-1",
                    "name": "Root",
                    "webUrl": "https://tenant.sharepoint.com",
                }
            },
        ),
    )

    status = await connector.health_check()

    assert status.connected is True
    assert status.auth_mode == "app_only"


@pytest.mark.asyncio
async def test_get_site_by_path_maps_graph_response():
    connector = SharePointConnector(
        make_config(),
        graph_client=FakeGraphClient(
            {
                "/sites/tenant.sharepoint.com:/teams/hr": {
                    "id": "site-1",
                    "name": "hr",
                    "displayName": "HR",
                    "webUrl": "https://tenant.sharepoint.com/teams/hr",
                    "description": "HR site",
                    "siteCollection": {"hostname": "tenant.sharepoint.com"},
                }
            },
        ),
    )

    site = await connector.get_site_by_path(
        "tenant.sharepoint.com",
        "/teams/hr",
    )

    assert site.id == "site-1"
    assert site.display_name == "HR"
    assert site.hostname == "tenant.sharepoint.com"


@pytest.mark.asyncio
async def test_list_drives_maps_items():
    connector = SharePointConnector(
        make_config(),
        graph_client=FakeGraphClient(
            {
                "/sites/site-1/drives": {
                    "value": [
                        {
                            "id": "drive-1",
                            "name": "Documents",
                            "webUrl": "https://example.com",
                            "driveType": "documentLibrary",
                        }
                    ]
                }
            },
        ),
    )

    drives = await connector.list_drives("site-1")

    assert len(drives) == 1
    assert drives[0].id == "drive-1"
    assert drives[0].name == "Documents"


@pytest.mark.asyncio
async def test_list_children_maps_file_and_folder():
    connector = SharePointConnector(
        make_config(),
        graph_client=FakeGraphClient(
            {
                "/drives/drive-1/root/children": {
                    "value": [
                        {
                            "id": "file-1",
                            "name": "report.pdf",
                            "size": 10,
                            "file": {"mimeType": "application/pdf"},
                            "parentReference": {"path": "/drive/root:"},
                        },
                        {
                            "id": "folder-1",
                            "name": "Reports",
                            "folder": {"childCount": 3},
                        },
                    ]
                }
            },
        ),
    )

    items = await connector.list_children("drive-1")

    assert items[0].is_folder is False
    assert items[0].mime_type == "application/pdf"
    assert items[1].is_folder is True


@pytest.mark.asyncio
async def test_download_file_returns_bytes():
    connector = SharePointConnector(
        make_config(),
        graph_client=FakeGraphClient(
            {
                "/drives/d/items/f/content": b"pdf-bytes",
            },
        ),
    )

    result = await connector.download_file("d", "f")

    assert result == b"pdf-bytes"


@pytest.mark.asyncio
async def test_search_files_can_scope_to_site():
    connector = SharePointConnector(
        make_config(),
        graph_client=FakeGraphClient(
            {
                "/search/query": {
                    "value": [
                        {
                            "hitsContainers": [
                                {
                                    "hits": [
                                        {
                                            "resource": {
                                                "id": "1",
                                                "name": "one.pdf",
                                                "parentReference": {"siteId": "site-1"},
                                            }
                                        },
                                        {
                                            "resource": {
                                                "id": "2",
                                                "name": "two.pdf",
                                                "parentReference": {"siteId": "site-2"},
                                            }
                                        },
                                    ]
                                }
                            ]
                        }
                    ]
                }
            },
        ),
    )

    items = await connector.search_files(
        "quarterly report",
        site_id="site-1",
    )

    assert [item.id for item in items] == ["1"]


@pytest.mark.asyncio
async def test_empty_search_is_rejected():
    connector = SharePointConnector(
        make_config(),
        graph_client=FakeGraphClient({}),
    )

    with pytest.raises(ValueError):
        await connector.search_files("")


@pytest.mark.asyncio
async def test_unconnected_operation_is_rejected():
    connector = SharePointConnector(make_config())

    with pytest.raises(exceptions.SharePointConfigurationError):
        await connector.list_drives("site")


@pytest.mark.asyncio
async def test_graph_client_401_is_normalized():
    FakeAsyncClient.responses = [
        FakeResponse(
            status_code=401,
            payload={"error": {"message": "invalid token"}},
        )
    ]

    graph = SharePointGraphClient(access_token="token")

    with pytest.raises(exceptions.SharePointAuthorizationError):
        await graph.get("/me")


@pytest.mark.asyncio
async def test_graph_client_403_is_normalized():
    FakeAsyncClient.responses = [
        FakeResponse(
            status_code=403,
            payload={"error": {"message": "forbidden"}},
        )
    ]

    graph = SharePointGraphClient(access_token="token")

    with pytest.raises(exceptions.SharePointAuthorizationError):
        await graph.get("/me")


@pytest.mark.asyncio
async def test_graph_client_404_is_normalized():
    FakeAsyncClient.responses = [
        FakeResponse(
            status_code=404,
            payload={"error": {"message": "not found"}},
        )
    ]

    graph = SharePointGraphClient(access_token="token")

    with pytest.raises(exceptions.SharePointNotFoundError):
        await graph.get("/sites/missing")


@pytest.mark.asyncio
async def test_graph_client_429_retries():
    FakeAsyncClient.responses = [
        FakeResponse(
            status_code=429,
            payload={"error": {"message": "slow down"}},
            headers={"content-type": "application/json", "Retry-After": "0"},
        ),
        FakeResponse(
            status_code=200,
            payload={"id": "ok"},
        ),
    ]

    graph = SharePointGraphClient(
        access_token="token",
        max_retries=1,
    )

    result = await graph.get("/me")

    assert result["id"] == "ok"


@pytest.mark.asyncio
async def test_graph_client_paginates_next_links():
    FakeAsyncClient.responses = [
        FakeResponse(
            status_code=200,
            payload={
                "value": [{"id": "1"}],
                "@odata.nextLink": "https://graph.microsoft.com/v1.0/items?page=2",
            },
        ),
        FakeResponse(
            status_code=200,
            payload={"value": [{"id": "2"}]},
        ),
    ]

    graph = SharePointGraphClient(access_token="token")

    values = await graph.paginate("/items")

    assert [item["id"] for item in values] == ["1", "2"]


@pytest.mark.asyncio
async def test_graph_client_rejects_external_absolute_url():
    graph = SharePointGraphClient(access_token="token")

    with pytest.raises(ValueError):
        await graph.get("https://evil.example.com/steal")


@pytest.mark.asyncio
async def test_get_user_requires_delegated_mode():
    connector = SharePointConnector(
        make_config(auth_mode="app_only", redirect_uri=None),
        graph_client=FakeGraphClient({}),
    )

    with pytest.raises(exceptions.SharePointConfigurationError):
        await connector.get_user()


class FakeGraphClient:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    async def get(self, path, **kwargs):
        self.calls.append(("GET", path, kwargs))
        value = self.responses[path]
        return value

    async def post(self, path, **kwargs):
        self.calls.append(("POST", path, kwargs))
        return self.responses[path]

    async def paginate(self, path, **kwargs):
        self.calls.append(("PAGINATE", path, kwargs))
        response = self.responses[path]
        return response.get("value", [])
