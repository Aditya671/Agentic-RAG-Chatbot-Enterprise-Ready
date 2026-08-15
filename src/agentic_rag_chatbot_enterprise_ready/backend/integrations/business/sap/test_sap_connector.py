import importlib.util
import sys
import types
from pathlib import Path

import pytest


ROOT = Path("/mnt/data/sap_integration/backend/integration")


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


backend = types.ModuleType("backend")
integration = types.ModuleType("backend.integration")
sap = types.ModuleType("backend.integration.sap")
backend.__path__ = [str(ROOT.parent.parent)]
integration.__path__ = [str(ROOT.parent)]
sap.__path__ = [str(ROOT / "sap")]
sys.modules["backend"] = backend
sys.modules["backend.integration"] = integration
sys.modules["backend.integration.sap"] = sap

exceptions = load_module(
    "backend.integration.sap.exceptions",
    ROOT / "sap" / "exceptions.py",
)
models = load_module(
    "backend.integration.sap.models",
    ROOT / "sap" / "models.py",
)
auth = load_module(
    "backend.integration.sap.auth",
    ROOT / "sap" / "auth.py",
)
client = load_module(
    "backend.integration.sap.client",
    ROOT / "sap" / "client.py",
)
connector_module = load_module(
    "backend.integration.sap_connector",
    ROOT / "sap_connector.py",
)

SAPAuthConfig = models.SAPAuthConfig
SAPConnector = connector_module.SAPConnector
SAPODataClient = client.SAPODataClient


class FakeResponse:
    def __init__(self, status_code=200, payload=None, headers=None):
        self.status_code = status_code
        self._payload = payload
        self.headers = headers or {"content-type": "application/json"}

    def json(self):
        return self._payload


class FakeAsyncClient:
    responses = []

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def request(self, method, url, **kwargs):
        return self.responses.pop(0)

    async def post(self, url, **kwargs):
        return await self.request("POST", url, **kwargs)


httpx = types.ModuleType("httpx")
httpx.AsyncClient = FakeAsyncClient
httpx.TimeoutException = type("TimeoutException", (Exception,), {})
httpx.NetworkError = type("NetworkError", (Exception,), {})
sys.modules["httpx"] = httpx


def oauth_config(**kwargs):
    values = dict(
        base_url="https://sap.example.com/odata",
        auth_mode="oauth2_client_credentials",
        client_id="client",
        client_secret="secret",
        token_url="https://auth.example.com/oauth/token",
        api_version="v4",
    )
    values.update(kwargs)
    return SAPAuthConfig(**values)


class FakeClient:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []
        self.access_token = "token"

    def set_access_token(self, token):
        self.access_token = token

    async def get(self, path, **kwargs):
        self.calls.append(("GET", path, kwargs))
        return self.responses[path]


def test_config_normalizes_url():
    cfg = oauth_config(base_url="https://sap.example.com/odata/")
    assert cfg.base_url == "https://sap.example.com/odata"


def test_config_requires_https():
    with pytest.raises(ValueError):
        SAPAuthConfig(
            base_url="http://sap.example.com/odata",
            auth_mode="bearer",
            api_version="v4",
        )


def test_config_requires_oauth_fields():
    with pytest.raises(ValueError):
        SAPAuthConfig(
            base_url="https://sap.example.com/odata",
            auth_mode="oauth2_client_credentials",
        )


def test_config_supports_basic_auth():
    cfg = SAPAuthConfig(
        base_url="https://sap.example.com/odata",
        auth_mode="basic",
        username="user",
        password="pass",
    )
    assert cfg.auth_mode == "basic"


def test_config_rejects_invalid_api_version():
    with pytest.raises(ValueError):
        SAPAuthConfig(
            base_url="https://sap.example.com/odata",
            auth_mode="bearer",
            api_version="v3",
        )


def test_connector_capabilities_are_read_only():
    connector = SAPConnector(oauth_config())

    capabilities = connector.get_capabilities()

    assert capabilities["read_odata"] is True
    assert capabilities["write_records"] is False
    assert capabilities["delete_records"] is False
    assert capabilities["execute_actions"] is False


@pytest.mark.asyncio
async def test_health_check_uses_metadata():
    fake = FakeClient({"$metadata": "<edmx:Edmx/>"})
    connector = SAPConnector(oauth_config(), client=fake, access_token="token")

    status = await connector.health_check()

    assert status.connected is True
    assert fake.calls[0][1] == "$metadata"


@pytest.mark.asyncio
async def test_query_entity_set_v4():
    fake = FakeClient(
        {
            "A_BusinessPartner": {
                "@odata.count": 1,
                "value": [
                    {
                        "BusinessPartner": "100000",
                        "BusinessPartnerFullName": "Example",
                    }
                ],
            }
        }
    )
    connector = SAPConnector(oauth_config(), client=fake, access_token="token")

    result = await connector.query_entity_set(
        entity_set="A_BusinessPartner",
        select=("BusinessPartner", "BusinessPartnerFullName"),
        filter_expression="BusinessPartner eq '100000'",
        order_by=("BusinessPartner asc",),
        top=10,
        count=True,
    )

    assert result.count == 1
    assert result.records[0]["BusinessPartner"] == "100000"

    params = fake.calls[0][2]["params"]
    assert params["$top"] == 10
    assert params["$count"] == "true"


@pytest.mark.asyncio
async def test_query_entity_set_v2():
    cfg = oauth_config(api_version="v2")
    fake = FakeClient(
        {
            "BusinessPartnerSet": {
                "d": {
                    "__count": "1",
                    "results": [{"BusinessPartner": "100000"}],
                }
            }
        }
    )
    connector = SAPConnector(cfg, client=fake, access_token="token")

    result = await connector.query_entity_set(
        entity_set="BusinessPartnerSet",
        top=10,
        count=True,
    )

    assert result.records[0]["BusinessPartner"] == "100000"


@pytest.mark.asyncio
async def test_query_rejects_unsafe_entity_set():
    connector = SAPConnector(
        oauth_config(),
        client=FakeClient({}),
        access_token="token",
    )

    with pytest.raises(exceptions.SAPQueryError):
        await connector.query_entity_set(
            entity_set="A_BusinessPartner/../secret"
        )


@pytest.mark.asyncio
async def test_query_rejects_unsafe_property():
    connector = SAPConnector(
        oauth_config(),
        client=FakeClient({}),
        access_token="token",
    )

    with pytest.raises(exceptions.SAPQueryError):
        await connector.query_entity_set(
            entity_set="A_BusinessPartner",
            select=("BusinessPartner,secret",),
        )


@pytest.mark.asyncio
async def test_query_rejects_invalid_top():
    connector = SAPConnector(
        oauth_config(),
        client=FakeClient({}),
        access_token="token",
    )

    with pytest.raises(exceptions.SAPQueryError):
        await connector.query_entity_set(
            entity_set="A_BusinessPartner",
            top=1001,
        )


@pytest.mark.asyncio
async def test_query_rejects_negative_skip():
    connector = SAPConnector(
        oauth_config(),
        client=FakeClient({}),
        access_token="token",
    )

    with pytest.raises(exceptions.SAPQueryError):
        await connector.query_entity_set(
            entity_set="A_BusinessPartner",
            skip=-1,
        )


@pytest.mark.asyncio
async def test_query_rejects_unsafe_filter():
    connector = SAPConnector(
        oauth_config(),
        client=FakeClient({}),
        access_token="token",
    )

    with pytest.raises(exceptions.SAPQueryError):
        await connector.query_entity_set(
            entity_set="A_BusinessPartner",
            filter_expression="x\nmalicious",
        )


@pytest.mark.asyncio
async def test_query_rejects_invalid_order_direction():
    connector = SAPConnector(
        oauth_config(),
        client=FakeClient({}),
        access_token="token",
    )

    with pytest.raises(exceptions.SAPQueryError):
        await connector.query_entity_set(
            entity_set="A_BusinessPartner",
            order_by=("BusinessPartner sideways",),
        )


@pytest.mark.asyncio
async def test_get_entity():
    fake = FakeClient(
        {
            "A_BusinessPartner('100000')": {
                "BusinessPartner": "100000",
                "BusinessPartnerFullName": "Example",
            }
        }
    )
    connector = SAPConnector(oauth_config(), client=fake, access_token="token")

    result = await connector.get_entity(
        entity_set="A_BusinessPartner",
        key="'100000'",
    )

    assert result["BusinessPartner"] == "100000"


@pytest.mark.asyncio
async def test_get_entity_rejects_path_characters():
    connector = SAPConnector(
        oauth_config(),
        client=FakeClient({}),
        access_token="token",
    )

    with pytest.raises(exceptions.SAPQueryError):
        await connector.get_entity(
            entity_set="A_BusinessPartner",
            key="../../secret",
        )


@pytest.mark.asyncio
async def test_follow_next_link():
    next_link = "https://sap.example.com/odata/A_BusinessPartner?$skip=10"
    fake = FakeClient(
        {
            next_link: {
                "value": [{"BusinessPartner": "100010"}],
            }
        }
    )
    connector = SAPConnector(oauth_config(), client=fake, access_token="token")

    result = await connector.follow_next_link(next_link)

    assert result.records[0]["BusinessPartner"] == "100010"


@pytest.mark.asyncio
async def test_disconnect_clears_token():
    fake = FakeClient({"$metadata": {}})
    connector = SAPConnector(oauth_config(), client=fake, access_token="token")

    assert connector.is_authenticated is True
    connector.disconnect()

    assert connector.is_authenticated is False
    assert fake.access_token is None


def test_bearer_mode_requires_token_at_runtime():
    cfg = SAPAuthConfig(
        base_url="https://sap.example.com/odata",
        auth_mode="bearer",
    )
    connector = SAPConnector(cfg)

    assert connector.is_authenticated is False


def test_external_absolute_url_is_rejected():
    client = SAPODataClient(
        oauth_config(),
        access_token="token",
    )

    with pytest.raises(ValueError):
        client._url("https://evil.example.com/secret")


@pytest.mark.asyncio
async def test_rest_client_normalizes_401():
    FakeAsyncClient.responses = [
        FakeResponse(
            401,
            {"error": {"message": "invalid token"}},
        )
    ]
    client = SAPODataClient(
        oauth_config(),
        access_token="token",
    )

    with pytest.raises(exceptions.SAPAuthenticationError):
        await client.get("$metadata")


@pytest.mark.asyncio
async def test_rest_client_normalizes_403():
    FakeAsyncClient.responses = [
        FakeResponse(
            403,
            {"error": {"message": "forbidden"}},
        )
    ]
    client = SAPODataClient(
        oauth_config(),
        access_token="token",
    )

    with pytest.raises(exceptions.SAPAuthorizationError):
        await client.get("$metadata")


@pytest.mark.asyncio
async def test_rest_client_normalizes_404():
    FakeAsyncClient.responses = [
        FakeResponse(
            404,
            {"error": {"message": "not found"}},
        )
    ]
    client = SAPODataClient(
        oauth_config(),
        access_token="token",
    )

    with pytest.raises(exceptions.SAPNotFoundError):
        await client.get("$metadata")


@pytest.mark.asyncio
async def test_rest_client_normalizes_400():
    FakeAsyncClient.responses = [
        FakeResponse(
            400,
            {"error": {"message": "bad request"}},
        )
    ]
    client = SAPODataClient(
        oauth_config(),
        access_token="token",
    )

    with pytest.raises(exceptions.SAPQueryError):
        await client.get("A_BusinessPartner")


@pytest.mark.asyncio
async def test_rest_client_retries_429():
    FakeAsyncClient.responses = [
        FakeResponse(
            429,
            {"error": {"message": "rate limited"}},
            {"Retry-After": "0"},
        ),
        FakeResponse(
            200,
            {"value": []},
        ),
    ]
    client = SAPODataClient(
        oauth_config(),
        access_token="token",
        max_retries=1,
    )

    result = await client.get("A_BusinessPartner")

    assert result["value"] == []


@pytest.mark.asyncio
async def test_basic_auth_does_not_require_token():
    cfg = SAPAuthConfig(
        base_url="https://sap.example.com/odata",
        auth_mode="basic",
        username="user",
        password="pass",
    )
    fake = FakeClient({"$metadata": {}})
    connector = SAPConnector(cfg, client=fake)

    assert connector.is_authenticated is True
    status = await connector.health_check()
    assert status.connected is True
