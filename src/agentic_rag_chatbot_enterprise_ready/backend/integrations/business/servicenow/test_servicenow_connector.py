import importlib.util
import sys
import types
from pathlib import Path

import pytest


ROOT = Path("/mnt/data/servicenow_integration/backend/integration")


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


backend = types.ModuleType("backend")
integration = types.ModuleType("backend.integration")
servicenow = types.ModuleType("backend.integration.servicenow")
backend.__path__ = [str(ROOT.parent.parent)]
integration.__path__ = [str(ROOT.parent)]
servicenow.__path__ = [str(ROOT / "servicenow")]
sys.modules["backend"] = backend
sys.modules["backend.integration"] = integration
sys.modules["backend.integration.servicenow"] = servicenow

exceptions = load_module(
    "backend.integration.servicenow.exceptions",
    ROOT / "servicenow" / "exceptions.py",
)
models = load_module(
    "backend.integration.servicenow.models",
    ROOT / "servicenow" / "models.py",
)
auth = load_module(
    "backend.integration.servicenow.auth",
    ROOT / "servicenow" / "auth.py",
)
client = load_module(
    "backend.integration.servicenow.client",
    ROOT / "servicenow" / "client.py",
)
connector_module = load_module(
    "backend.integration.servicenow_connector",
    ROOT / "servicenow_connector.py",
)

ServiceNowAuthConfig = models.ServiceNowAuthConfig
ServiceNowTokenProvider = auth.ServiceNowTokenProvider
ServiceNowRESTClient = client.ServiceNowRESTClient
ServiceNowConnector = connector_module.ServiceNowConnector


class FakeResponse:
    def __init__(self, status_code=200, payload=None, headers=None):
        self.status_code = status_code
        self._payload = payload
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
        return self.responses.pop(0)

    async def post(self, url, **kwargs):
        return await self.request("POST", url, **kwargs)


httpx = types.ModuleType("httpx")
httpx.AsyncClient = FakeAsyncClient
httpx.TimeoutException = type("TimeoutException", (Exception,), {})
httpx.NetworkError = type("NetworkError", (Exception,), {})
sys.modules["httpx"] = httpx


def config(**kwargs):
    values = dict(
        instance_url="https://example.service-now.com",
        client_id="client-id",
        client_secret="secret",
        redirect_uri="https://app.example.com/servicenow/callback",
        auth_mode="delegated",
    )
    values.update(kwargs)
    return ServiceNowAuthConfig(**values)


class FakeRESTClient:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    async def get(self, path, **kwargs):
        self.calls.append(("GET", path, kwargs))
        return self.responses[path]


def test_config_normalizes_instance_url():
    cfg = config(instance_url="https://example.service-now.com/")
    assert cfg.instance_url == "https://example.service-now.com"


def test_config_requires_https():
    with pytest.raises(ValueError):
        ServiceNowAuthConfig(
            instance_url="http://example.service-now.com",
            client_id="client",
            redirect_uri="https://example.com/callback",
        )


def test_config_requires_redirect_uri_for_delegated():
    with pytest.raises(ValueError):
        ServiceNowAuthConfig(
            instance_url="https://example.service-now.com",
            client_id="client",
            auth_mode="delegated",
        )


def test_config_requires_secret_for_client_credentials():
    with pytest.raises(ValueError):
        ServiceNowAuthConfig(
            instance_url="https://example.service-now.com",
            client_id="client",
            auth_mode="client_credentials",
        )


def test_config_rejects_invalid_auth_mode():
    with pytest.raises(ValueError):
        ServiceNowAuthConfig(
            instance_url="https://example.service-now.com",
            client_id="client",
            redirect_uri="https://example.com/callback",
            auth_mode="invalid",
        )


def test_pkce_is_deterministic():
    verifier = "A" * 64
    assert (
        ServiceNowTokenProvider.create_pkce_challenge(verifier)
        == ServiceNowTokenProvider.create_pkce_challenge(verifier)
    )


def test_authorization_url_contains_required_parameters():
    provider = ServiceNowTokenProvider(config())
    url, state = provider.build_authorization_url(state="state123")

    assert "response_type=code" in url
    assert "client_id=client-id" in url
    assert "redirect_uri=" in url
    assert "state=state123" in url
    assert state == "state123"


def test_authorization_url_adds_pkce():
    provider = ServiceNowTokenProvider(config(require_pkce=True))
    verifier = provider.create_pkce_verifier()
    url, _ = provider.build_authorization_url(
        state="state",
        pkce_verifier=verifier,
    )

    assert "code_challenge=" in url
    assert "code_challenge_method=S256" in url


def test_connector_starts_disconnected():
    connector = ServiceNowConnector(config())

    assert connector.is_authenticated is False
    assert connector.get_capabilities()["write_records"] is False
    assert connector.get_capabilities()["delete_records"] is False


@pytest.mark.asyncio
async def test_health_check_uses_minimal_incident_read():
    fake = FakeRESTClient(
        {
            "/table/incident": {"result": [{"sys_id": "1"}]},
        }
    )
    connector = ServiceNowConnector(config(), rest_client=fake)

    status = await connector.health_check()

    assert status.connected is True
    assert fake.calls[0][1] == "/table/incident"
    assert fake.calls[0][2]["params"]["sysparm_limit"] == 1


@pytest.mark.asyncio
async def test_query_table_returns_typed_records():
    fake = FakeRESTClient(
        {
            "/table/incident": {
                "result": [
                    {
                        "sys_id": "a" * 32,
                        "number": "INC001",
                        "short_description": "Network issue",
                    }
                ]
            }
        }
    )
    connector = ServiceNowConnector(config(), rest_client=fake)

    result = await connector.query_table(
        table="incident",
        encoded_query="active=true",
        fields=("sys_id", "number", "short_description"),
        limit=10,
    )

    assert result.count == 1
    assert result.records[0].sys_id == "a" * 32
    assert result.records[0].fields["number"] == "INC001"


@pytest.mark.asyncio
async def test_query_table_rejects_unsafe_table():
    connector = ServiceNowConnector(
        config(),
        rest_client=FakeRESTClient({}),
    )

    with pytest.raises(exceptions.ServiceNowQueryError):
        await connector.query_table(
            table="incident/../user",
        )


@pytest.mark.asyncio
async def test_query_table_rejects_unsafe_field():
    connector = ServiceNowConnector(
        config(),
        rest_client=FakeRESTClient({}),
    )

    with pytest.raises(exceptions.ServiceNowQueryError):
        await connector.query_table(
            table="incident",
            fields=("sys_id,sys_user",),
        )


@pytest.mark.asyncio
async def test_query_table_rejects_invalid_limit():
    connector = ServiceNowConnector(
        config(),
        rest_client=FakeRESTClient({}),
    )

    with pytest.raises(exceptions.ServiceNowQueryError):
        await connector.query_table(
            table="incident",
            limit=0,
        )


@pytest.mark.asyncio
async def test_query_table_rejects_oversized_query():
    connector = ServiceNowConnector(
        config(),
        rest_client=FakeRESTClient({}),
    )

    with pytest.raises(exceptions.ServiceNowQueryError):
        await connector.query_table(
            table="incident",
            encoded_query="x" * 2001,
        )


@pytest.mark.asyncio
async def test_search_incidents_constructs_controlled_query():
    fake = FakeRESTClient(
        {
            "/table/incident": {
                "result": [],
            }
        }
    )
    connector = ServiceNowConnector(config(), rest_client=fake)

    await connector.search_incidents("network^admin")

    params = fake.calls[0][2]["params"]
    assert params["sysparm_query"] == "short_descriptionLIKEnetwork^^admin"
    assert params["sysparm_display_value"] == "true"


@pytest.mark.asyncio
async def test_search_requests_constructs_request_table():
    fake = FakeRESTClient(
        {
            "/table/sc_request": {
                "result": [],
            }
        }
    )
    connector = ServiceNowConnector(config(), rest_client=fake)

    await connector.search_requests("laptop")

    assert fake.calls[0][1] == "/table/sc_request"


@pytest.mark.asyncio
async def test_search_changes_constructs_change_table():
    fake = FakeRESTClient(
        {
            "/table/change_request": {
                "result": [],
            }
        }
    )
    connector = ServiceNowConnector(config(), rest_client=fake)

    await connector.search_changes("database")

    assert fake.calls[0][1] == "/table/change_request"


@pytest.mark.asyncio
async def test_get_record_requires_valid_sys_id():
    connector = ServiceNowConnector(
        config(),
        rest_client=FakeRESTClient({}),
    )

    with pytest.raises(exceptions.ServiceNowQueryError):
        await connector.get_record(
            table="incident",
            sys_id="not-a-sys-id",
        )


@pytest.mark.asyncio
async def test_get_record_returns_result():
    sys_id = "b" * 32
    fake = FakeRESTClient(
        {
            f"/table/incident/{sys_id}": {
                "result": {
                    "sys_id": sys_id,
                    "number": "INC002",
                }
            }
        }
    )
    connector = ServiceNowConnector(config(), rest_client=fake)

    result = await connector.get_record(
        table="incident",
        sys_id=sys_id,
    )

    assert result["number"] == "INC002"


@pytest.mark.asyncio
async def test_query_more_is_represented_by_offset():
    fake = FakeRESTClient(
        {
            "/table/incident": {
                "result": [{"sys_id": str(i)} for i in range(25)]
            }
        }
    )
    connector = ServiceNowConnector(config(), rest_client=fake)

    result = await connector.query_table(
        table="incident",
        limit=25,
        offset=50,
    )

    assert result.count == 25
    assert result.next_offset == 75


@pytest.mark.asyncio
async def test_unconnected_operation_fails():
    connector = ServiceNowConnector(config())

    with pytest.raises(exceptions.ServiceNowConfigurationError):
        await connector.query_table(table="incident")


@pytest.mark.asyncio
async def test_disconnect_clears_connection():
    connector = ServiceNowConnector(
        config(),
        access_token="secret-token",
    )

    assert connector.is_authenticated is True

    connector.disconnect()

    assert connector.is_authenticated is False


@pytest.mark.asyncio
async def test_rest_client_rejects_external_absolute_url():
    client = ServiceNowRESTClient(
        access_token="token",
        instance_url="https://example.service-now.com",
    )

    with pytest.raises(ValueError):
        await client.get("https://evil.example.com/steal")


@pytest.mark.asyncio
async def test_rest_client_normalizes_401():
    FakeAsyncClient.responses = [
        FakeResponse(
            status_code=401,
            payload={"error": {"message": "invalid token"}},
        )
    ]
    client = ServiceNowRESTClient(
        access_token="token",
        instance_url="https://example.service-now.com",
    )

    with pytest.raises(exceptions.ServiceNowAuthorizationError):
        await client.get("/table/incident")


@pytest.mark.asyncio
async def test_rest_client_normalizes_403():
    FakeAsyncClient.responses = [
        FakeResponse(
            status_code=403,
            payload={"error": {"message": "forbidden"}},
        )
    ]
    client = ServiceNowRESTClient(
        access_token="token",
        instance_url="https://example.service-now.com",
    )

    with pytest.raises(exceptions.ServiceNowAuthorizationError):
        await client.get("/table/incident")


@pytest.mark.asyncio
async def test_rest_client_normalizes_404():
    FakeAsyncClient.responses = [
        FakeResponse(
            status_code=404,
            payload={"error": {"message": "missing"}},
        )
    ]
    client = ServiceNowRESTClient(
        access_token="token",
        instance_url="https://example.service-now.com",
    )

    with pytest.raises(exceptions.ServiceNowNotFoundError):
        await client.get("/table/missing")


@pytest.mark.asyncio
async def test_rest_client_normalizes_400():
    FakeAsyncClient.responses = [
        FakeResponse(
            status_code=400,
            payload={"error": {"message": "bad query"}},
        )
    ]
    client = ServiceNowRESTClient(
        access_token="token",
        instance_url="https://example.service-now.com",
    )

    with pytest.raises(exceptions.ServiceNowQueryError):
        await client.get("/table/incident")


@pytest.mark.asyncio
async def test_rest_client_retries_429():
    FakeAsyncClient.responses = [
        FakeResponse(
            status_code=429,
            payload={"error": {"message": "slow down"}},
            headers={
                "content-type": "application/json",
                "Retry-After": "0",
            },
        ),
        FakeResponse(
            status_code=200,
            payload={"result": []},
        ),
    ]

    client = ServiceNowRESTClient(
        access_token="token",
        instance_url="https://example.service-now.com",
        max_retries=1,
    )

    result = await client.get("/table/incident")

    assert result["result"] == []


def test_write_capabilities_are_disabled():
    connector = ServiceNowConnector(config())
    capabilities = connector.get_capabilities()

    assert capabilities["write_records"] is False
    assert capabilities["delete_records"] is False


def test_instance_cannot_escape_with_absolute_url():
    client = ServiceNowRESTClient(
        access_token="token",
        instance_url="https://example.service-now.com",
    )

    with pytest.raises(ValueError):
        client._url("https://other.service-now.com/api/now/table/incident")
