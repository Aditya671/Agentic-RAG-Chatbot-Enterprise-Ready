import importlib.util
import sys
import types
from pathlib import Path

import pytest


ROOT = Path("/mnt/data/salesforce_integration/backend/integration")


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


backend = types.ModuleType("backend")
integration = types.ModuleType("backend.integration")
salesforce = types.ModuleType("backend.integration.salesforce")
backend.__path__ = [str(ROOT.parent.parent)]
integration.__path__ = [str(ROOT.parent)]
salesforce.__path__ = [str(ROOT / "salesforce")]
sys.modules["backend"] = backend
sys.modules["backend.integration"] = integration
sys.modules["backend.integration.salesforce"] = salesforce

exceptions = load_module(
    "backend.integration.salesforce.exceptions",
    ROOT / "salesforce" / "exceptions.py",
)
models = load_module(
    "backend.integration.salesforce.models",
    ROOT / "salesforce" / "models.py",
)
auth = load_module(
    "backend.integration.salesforce.auth",
    ROOT / "salesforce" / "auth.py",
)
client = load_module(
    "backend.integration.salesforce.client",
    ROOT / "salesforce" / "client.py",
)
connector_module = load_module(
    "backend.integration.salesforce_connector",
    ROOT / "salesforce_connector.py",
)

SalesforceAuthConfig = models.SalesforceAuthConfig
SalesforceTokenProvider = auth.SalesforceTokenProvider
SalesforceRESTClient = client.SalesforceRESTClient
SalesforceConnector = connector_module.SalesforceConnector


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
        return response

    async def post(self, url, **kwargs):
        return await self.request("POST", url, **kwargs)


httpx = types.ModuleType("httpx")
httpx.AsyncClient = FakeAsyncClient
httpx.TimeoutException = type("TimeoutException", (Exception,), {})
httpx.NetworkError = type("NetworkError", (Exception,), {})
sys.modules["httpx"] = httpx


def config(**kwargs):
    values = dict(
        client_id="client-id",
        client_secret="secret",
        redirect_uri="https://app.example.com/salesforce/callback",
        auth_mode="delegated",
    )
    values.update(kwargs)
    return SalesforceAuthConfig(**values)


class FakeRESTClient:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    async def get(self, path, **kwargs):
        self.calls.append(("GET", path, kwargs))
        return self.responses[path]


def test_config_defaults_to_current_api_version():
    cfg = config()
    assert cfg.api_version == "v67.0"


def test_config_requires_redirect_uri_for_delegated():
    with pytest.raises(ValueError):
        SalesforceAuthConfig(
            client_id="client",
            auth_mode="delegated",
        )


def test_config_requires_secret_for_client_credentials():
    with pytest.raises(ValueError):
        SalesforceAuthConfig(
            client_id="client",
            auth_mode="client_credentials",
        )


def test_config_rejects_non_https_login_url():
    with pytest.raises(ValueError):
        SalesforceAuthConfig(
            client_id="client",
            redirect_uri="https://example.com/callback",
            login_url="http://login.salesforce.com",
        )


def test_pkce_is_deterministic():
    verifier = "A" * 64
    first = SalesforceTokenProvider.create_pkce_challenge(verifier)
    second = SalesforceTokenProvider.create_pkce_challenge(verifier)
    assert first == second


def test_authorization_url_has_required_parameters():
    provider = SalesforceTokenProvider(config())
    url, state = provider.build_authorization_url(state="state123")

    assert "response_type=code" in url
    assert "client_id=client-id" in url
    assert "redirect_uri=" in url
    assert "state=state123" in url
    assert state == "state123"


def test_authorization_url_requires_pkce_when_configured():
    provider = SalesforceTokenProvider(config(require_pkce=True))

    with pytest.raises(exceptions.SalesforceAuthenticationError):
        provider.build_authorization_url(state="state")


def test_authorization_url_adds_pkce_when_configured():
    provider = SalesforceTokenProvider(config(require_pkce=True))
    verifier = provider.create_pkce_verifier()
    url, _ = provider.build_authorization_url(
        state="state",
        pkce_verifier=verifier,
    )

    assert "code_challenge=" in url
    assert "code_challenge_method=S256" in url


def test_connector_starts_disconnected():
    connector = SalesforceConnector(config())

    assert connector.is_authenticated is False
    assert connector.get_capabilities()["write_records"] is False


@pytest.mark.asyncio
async def test_health_check_uses_sobjects():
    fake = FakeRESTClient(
        {
            "/sobjects": {"sobjects": []},
        }
    )
    connector = SalesforceConnector(config(), rest_client=fake)

    status = await connector.health_check()

    assert status.connected is True
    assert fake.calls[0][1] == "/sobjects"


@pytest.mark.asyncio
async def test_query_soql_returns_typed_records():
    fake = FakeRESTClient(
        {
            "/query": {
                "totalSize": 1,
                "done": True,
                "records": [
                    {
                        "attributes": {"type": "Account", "url": "/Account/1"},
                        "Id": "001",
                        "Name": "Acme",
                        "Industry": "Technology",
                    }
                ],
            }
        }
    )
    connector = SalesforceConnector(config(), rest_client=fake)

    result = await connector.query_soql(
        "SELECT Id, Name, Industry FROM Account"
    )

    assert result.total_size == 1
    assert result.records[0].id == "001"
    assert result.records[0].type == "Account"
    assert result.records[0].fields["Name"] == "Acme"


@pytest.mark.asyncio
async def test_query_soql_rejects_empty():
    connector = SalesforceConnector(
        config(),
        rest_client=FakeRESTClient({}),
    )

    with pytest.raises(exceptions.SalesforceQueryError):
        await connector.query_soql("")


@pytest.mark.asyncio
async def test_query_soql_rejects_non_select():
    connector = SalesforceConnector(
        config(),
        rest_client=FakeRESTClient({}),
    )

    with pytest.raises(exceptions.SalesforceQueryError):
        await connector.query_soql("DELETE FROM Account")


@pytest.mark.asyncio
async def test_query_soql_rejects_multiple_statements():
    connector = SalesforceConnector(
        config(),
        rest_client=FakeRESTClient({}),
    )

    with pytest.raises(exceptions.SalesforceQueryError):
        await connector.query_soql(
            "SELECT Id FROM Account; SELECT Id FROM Contact"
        )


@pytest.mark.asyncio
async def test_search_accounts_builds_safe_soql():
    fake = FakeRESTClient(
        {
            "/query": {
                "totalSize": 0,
                "done": True,
                "records": [],
            }
        }
    )
    connector = SalesforceConnector(config(), rest_client=fake)

    await connector.search_accounts("O'Reilly")

    request = fake.calls[0]
    soql = request[2]["params"]["q"]

    assert "O\\'Reilly" in soql
    assert "FROM Account" in soql
    assert "LIMIT 25" in soql


@pytest.mark.asyncio
async def test_search_accounts_rejects_invalid_limit():
    connector = SalesforceConnector(
        config(),
        rest_client=FakeRESTClient({}),
    )

    with pytest.raises(exceptions.SalesforceQueryError):
        await connector.search_accounts("Acme", limit=0)


@pytest.mark.asyncio
async def test_search_records_rejects_unsafe_object_name():
    connector = SalesforceConnector(
        config(),
        rest_client=FakeRESTClient({}),
    )

    with pytest.raises(exceptions.SalesforceQueryError):
        await connector.search_records(
            object_name="Account FROM Contact",
            search_field="Name",
            query="x",
        )


@pytest.mark.asyncio
async def test_search_records_rejects_unsafe_field():
    connector = SalesforceConnector(
        config(),
        rest_client=FakeRESTClient({}),
    )

    with pytest.raises(exceptions.SalesforceQueryError):
        await connector.search_records(
            object_name="Account",
            search_field="Name FROM Contact",
            query="x",
        )


@pytest.mark.asyncio
async def test_query_more_requires_same_instance():
    fake = FakeRESTClient({})
    connector = SalesforceConnector(
        config(),
        instance_url="https://myorg.my.salesforce.com",
        rest_client=fake,
    )

    with pytest.raises(exceptions.SalesforceQueryError):
        await connector.query_more(
            "https://other.salesforce.com/services/data/v67.0/query/next"
        )


@pytest.mark.asyncio
async def test_disconnect_clears_credentials():
    connector = SalesforceConnector(
        config(),
        access_token="secret-token",
        instance_url="https://myorg.my.salesforce.com",
    )

    assert connector.is_authenticated is True

    connector.disconnect()

    assert connector.is_authenticated is False
    assert connector.instance_url is None


@pytest.mark.asyncio
async def test_rest_client_rejects_external_absolute_url():
    client = SalesforceRESTClient(
        access_token="token",
        instance_url="https://myorg.my.salesforce.com",
    )

    with pytest.raises(ValueError):
        await client.get("https://evil.example.com/steal")


@pytest.mark.asyncio
async def test_rest_client_normalizes_401():
    FakeAsyncClient.responses = [
        FakeResponse(
            status_code=401,
            payload=[{"message": "invalid session", "errorCode": "INVALID_SESSION_ID"}],
        )
    ]
    client = SalesforceRESTClient(
        access_token="token",
        instance_url="https://myorg.my.salesforce.com",
    )

    with pytest.raises(exceptions.SalesforceAuthorizationError):
        await client.get("/sobjects")


@pytest.mark.asyncio
async def test_rest_client_normalizes_404():
    FakeAsyncClient.responses = [
        FakeResponse(
            status_code=404,
            payload=[{"message": "not found", "errorCode": "NOT_FOUND"}],
        )
    ]
    client = SalesforceRESTClient(
        access_token="token",
        instance_url="https://myorg.my.salesforce.com",
    )

    with pytest.raises(exceptions.SalesforceNotFoundError):
        await client.get("/sobjects/missing")


@pytest.mark.asyncio
async def test_rest_client_normalizes_400_as_query_error():
    FakeAsyncClient.responses = [
        FakeResponse(
            status_code=400,
            payload=[{"message": "malformed query", "errorCode": "MALFORMED_QUERY"}],
        )
    ]
    client = SalesforceRESTClient(
        access_token="token",
        instance_url="https://myorg.my.salesforce.com",
    )

    with pytest.raises(exceptions.SalesforceQueryError):
        await client.get("/query")


@pytest.mark.asyncio
async def test_rest_client_retries_429():
    FakeAsyncClient.responses = [
        FakeResponse(
            status_code=429,
            payload=[{"message": "rate limited"}],
            headers={
                "content-type": "application/json",
                "Retry-After": "0",
            },
        ),
        FakeResponse(
            status_code=200,
            payload={"sobjects": []},
        ),
    ]

    client = SalesforceRESTClient(
        access_token="token",
        instance_url="https://myorg.my.salesforce.com",
        max_retries=1,
    )

    result = await client.get("/sobjects")

    assert result["sobjects"] == []


def test_source_uses_current_api_version():
    source = (
        ROOT / "salesforce_connector.py"
    ).read_text()
    assert "v67.0" in source


def test_connector_does_not_enable_write_by_default():
    connector = SalesforceConnector(config())
    capabilities = connector.get_capabilities()

    assert capabilities["write_records"] is False
