import importlib.util
import sys
import types
from pathlib import Path

import pytest


ROOT = Path("/mnt/data/jira_integration/backend/integration")


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


backend = types.ModuleType("backend")
integration = types.ModuleType("backend.integration")
jira = types.ModuleType("backend.integration.jira")
backend.__path__ = [str(ROOT.parent.parent)]
integration.__path__ = [str(ROOT.parent)]
jira.__path__ = [str(ROOT / "jira")]
sys.modules["backend"] = backend
sys.modules["backend.integration"] = integration
sys.modules["backend.integration.jira"] = jira

exceptions = load_module(
    "backend.integration.jira.exceptions",
    ROOT / "jira" / "exceptions.py",
)
models = load_module(
    "backend.integration.jira.models",
    ROOT / "jira" / "models.py",
)
auth = load_module(
    "backend.integration.jira.auth",
    ROOT / "jira" / "auth.py",
)
client = load_module(
    "backend.integration.jira.client",
    ROOT / "jira" / "client.py",
)
connector_module = load_module(
    "backend.integration.jira_connector",
    ROOT / "jira_connector.py",
)

JiraAuthConfig = models.JiraAuthConfig
JiraTokenProvider = auth.JiraTokenProvider
JiraRESTClient = client.JiraRESTClient
JiraConnector = connector_module.JiraConnector


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

    async def get(self, url, **kwargs):
        return await self.request("GET", url, **kwargs)

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
        redirect_uri="https://app.example.com/jira/callback",
    )
    values.update(kwargs)
    return JiraAuthConfig(**values)


class FakeRESTClient:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    async def get(self, path, **kwargs):
        self.calls.append(("GET", path, kwargs))
        return self.responses[path]


def test_config_defaults_to_delegated():
    cfg = config()
    assert cfg.auth_mode == "delegated"
    assert "read:jira-work" in cfg.scopes


def test_config_requires_redirect_uri():
    with pytest.raises(ValueError):
        JiraAuthConfig(client_id="client")


def test_config_requires_https_redirect():
    with pytest.raises(ValueError):
        JiraAuthConfig(
            client_id="client",
            redirect_uri="http://localhost/callback",
        )


def test_config_rejects_non_delegated_mode():
    with pytest.raises(ValueError):
        JiraAuthConfig(
            client_id="client",
            redirect_uri="https://example.com/callback",
            auth_mode="client_credentials",
        )


def test_authorization_url_contains_3lo_parameters():
    provider = JiraTokenProvider(config())
    url, state = provider.build_authorization_url(state="state123")

    assert "audience=api.atlassian.com" in url
    assert "response_type=code" in url
    assert "client_id=client-id" in url
    assert "redirect_uri=" in url
    assert "state=state123" in url
    assert state == "state123"


def test_pkce_challenge_is_deterministic():
    verifier = "A" * 64
    assert (
        JiraTokenProvider.create_pkce_challenge(verifier)
        == JiraTokenProvider.create_pkce_challenge(verifier)
    )


def test_authorization_url_requires_pkce_when_enabled():
    provider = JiraTokenProvider(config(require_pkce=True))

    with pytest.raises(exceptions.JiraAuthenticationError):
        provider.build_authorization_url(state="state")


def test_authorization_url_adds_pkce():
    provider = JiraTokenProvider(config(require_pkce=True))
    verifier = provider.create_pkce_verifier()
    url, _ = provider.build_authorization_url(
        state="state",
        pkce_verifier=verifier,
    )

    assert "code_challenge=" in url
    assert "code_challenge_method=S256" in url


def test_connector_starts_disconnected():
    connector = JiraConnector(config())

    assert connector.is_authenticated is False
    assert connector.get_capabilities()["write_issues"] is False
    assert connector.get_capabilities()["delete_issues"] is False


@pytest.mark.asyncio
async def test_health_check_uses_myself():
    fake = FakeRESTClient(
        {
            "/myself": {
                "accountId": "account-1",
                "displayName": "Test User",
            }
        }
    )
    connector = JiraConnector(
        config(),
        cloud_id="cloud-1",
        site_url="https://example.atlassian.net",
        rest_client=fake,
    )

    status = await connector.health_check()

    assert status.connected is True
    assert status.account_id == "account-1"
    assert fake.calls[0][1] == "/myself"


@pytest.mark.asyncio
async def test_get_current_user():
    fake = FakeRESTClient(
        {
            "/myself": {
                "accountId": "account-1",
                "displayName": "Test User",
            }
        }
    )
    connector = JiraConnector(
        config(),
        cloud_id="cloud-1",
        rest_client=fake,
    )

    user = await connector.get_current_user()

    assert user["accountId"] == "account-1"


@pytest.mark.asyncio
async def test_get_issue_returns_typed_issue():
    fake = FakeRESTClient(
        {
            "/issue/PROJ-123": {
                "id": "10001",
                "key": "PROJ-123",
                "fields": {
                    "summary": "Broken build",
                    "status": {"name": "Open"},
                },
            }
        }
    )
    connector = JiraConnector(
        config(),
        cloud_id="cloud-1",
        rest_client=fake,
    )

    issue = await connector.get_issue("PROJ-123")

    assert issue.key == "PROJ-123"
    assert issue.fields["summary"] == "Broken build"


@pytest.mark.asyncio
async def test_get_issue_rejects_invalid_identifier():
    connector = JiraConnector(
        config(),
        cloud_id="cloud-1",
        rest_client=FakeRESTClient({}),
    )

    with pytest.raises(exceptions.JiraQueryError):
        await connector.get_issue("../issue/secret")


@pytest.mark.asyncio
async def test_search_jql_uses_enhanced_endpoint():
    fake = FakeRESTClient(
        {
            "/search/jql": {
                "issues": [
                    {
                        "id": "1",
                        "key": "PROJ-1",
                        "fields": {"summary": "Test"},
                    }
                ],
                "total": 1,
                "isLast": True,
            }
        }
    )
    connector = JiraConnector(
        config(),
        cloud_id="cloud-1",
        rest_client=fake,
    )

    result = await connector.search_issues(
        "project = PROJ ORDER BY updated DESC"
    )

    assert result.issues[0].key == "PROJ-1"
    assert fake.calls[0][1] == "/search/jql"


@pytest.mark.asyncio
async def test_search_jql_preserves_next_page_token():
    fake = FakeRESTClient(
        {
            "/search/jql": {
                "issues": [],
                "nextPageToken": "next-token",
                "isLast": False,
            }
        }
    )
    connector = JiraConnector(
        config(),
        cloud_id="cloud-1",
        rest_client=fake,
    )

    result = await connector.search_issues(
        "project = PROJ",
        next_page_token="previous-token",
    )

    assert result.next_page_token == "next-token"
    assert fake.calls[0][2]["params"]["nextPageToken"] == "previous-token"


@pytest.mark.asyncio
async def test_search_rejects_empty_jql():
    connector = JiraConnector(
        config(),
        cloud_id="cloud-1",
        rest_client=FakeRESTClient({}),
    )

    with pytest.raises(exceptions.JiraQueryError):
        await connector.search_issues("")


@pytest.mark.asyncio
async def test_search_rejects_multiple_jql_statements():
    connector = JiraConnector(
        config(),
        cloud_id="cloud-1",
        rest_client=FakeRESTClient({}),
    )

    with pytest.raises(exceptions.JiraQueryError):
        await connector.search_issues(
            "project = PROJ; project = OTHER"
        )


@pytest.mark.asyncio
async def test_search_rejects_oversized_jql():
    connector = JiraConnector(
        config(),
        cloud_id="cloud-1",
        rest_client=FakeRESTClient({}),
    )

    with pytest.raises(exceptions.JiraQueryError):
        await connector.search_issues("x" * 4001)


@pytest.mark.asyncio
async def test_search_rejects_invalid_max_results():
    connector = JiraConnector(
        config(),
        cloud_id="cloud-1",
        rest_client=FakeRESTClient({}),
    )

    with pytest.raises(exceptions.JiraQueryError):
        await connector.search_issues("project = PROJ", max_results=101)


@pytest.mark.asyncio
async def test_search_text_escapes_quotes():
    fake = FakeRESTClient(
        {
            "/search/jql": {
                "issues": [],
                "isLast": True,
            }
        }
    )
    connector = JiraConnector(
        config(),
        cloud_id="cloud-1",
        rest_client=fake,
    )

    await connector.search_text('release "critical"')

    jql = fake.calls[0][2]["params"]["jql"]
    assert '\\"critical\\"' in jql


@pytest.mark.asyncio
async def test_search_validates_fields():
    fake = FakeRESTClient(
        {
            "/search/jql": {
                "issues": [],
                "isLast": True,
            }
        }
    )
    connector = JiraConnector(
        config(),
        cloud_id="cloud-1",
        rest_client=fake,
    )

    await connector.search_issues(
        "project = PROJ",
        fields=("summary", "customfield_10001"),
    )

    fields = fake.calls[0][2]["params"]["fields"]
    assert fields == "summary,customfield_10001"


@pytest.mark.asyncio
async def test_search_rejects_unsafe_field():
    connector = JiraConnector(
        config(),
        cloud_id="cloud-1",
        rest_client=FakeRESTClient({}),
    )

    with pytest.raises(exceptions.JiraQueryError):
        await connector.search_issues(
            "project = PROJ",
            fields=("summary,evil",),
        )


@pytest.mark.asyncio
async def test_list_projects():
    fake = FakeRESTClient(
        {
            "/project/search": {
                "values": [
                    {
                        "id": "100",
                        "key": "PROJ",
                        "name": "Project",
                        "projectTypeKey": "software",
                    }
                ]
            }
        }
    )
    connector = JiraConnector(
        config(),
        cloud_id="cloud-1",
        rest_client=fake,
    )

    projects = await connector.list_projects()

    assert projects[0].key == "PROJ"
    assert projects[0].project_type_key == "software"


@pytest.mark.asyncio
async def test_get_project():
    fake = FakeRESTClient(
        {
            "/project/PROJ": {
                "id": "100",
                "key": "PROJ",
                "name": "Project",
            }
        }
    )
    connector = JiraConnector(
        config(),
        cloud_id="cloud-1",
        rest_client=fake,
    )

    project = await connector.get_project("PROJ")

    assert project.name == "Project"


@pytest.mark.asyncio
async def test_disconnect_clears_connection():
    connector = JiraConnector(
        config(),
        access_token="token",
        cloud_id="cloud-1",
    )

    assert connector.is_authenticated is True

    connector.disconnect()

    assert connector.is_authenticated is False
    assert connector.cloud_id is None


@pytest.mark.asyncio
async def test_rest_client_uses_atlassian_cloud_proxy():
    client = JiraRESTClient(
        access_token="token",
        cloud_id="cloud-123",
    )

    assert (
        client.base_url
        == "https://api.atlassian.com/ex/jira/cloud-123/rest/api/3"
    )


@pytest.mark.asyncio
async def test_rest_client_rejects_external_absolute_url():
    client = JiraRESTClient(
        access_token="token",
        cloud_id="cloud-123",
    )

    with pytest.raises(ValueError):
        await client.get("https://evil.example.com/steal")


@pytest.mark.asyncio
async def test_rest_client_normalizes_401():
    FakeAsyncClient.responses = [
        FakeResponse(
            status_code=401,
            payload={"errorMessages": ["Unauthorized"]},
        )
    ]
    client = JiraRESTClient(
        access_token="token",
        cloud_id="cloud-123",
    )

    with pytest.raises(exceptions.JiraAuthorizationError):
        await client.get("/myself")


@pytest.mark.asyncio
async def test_rest_client_normalizes_403():
    FakeAsyncClient.responses = [
        FakeResponse(
            status_code=403,
            payload={"errorMessages": ["Forbidden"]},
        )
    ]
    client = JiraRESTClient(
        access_token="token",
        cloud_id="cloud-123",
    )

    with pytest.raises(exceptions.JiraAuthorizationError):
        await client.get("/myself")


@pytest.mark.asyncio
async def test_rest_client_normalizes_404():
    FakeAsyncClient.responses = [
        FakeResponse(
            status_code=404,
            payload={"errorMessages": ["Not found"]},
        )
    ]
    client = JiraRESTClient(
        access_token="token",
        cloud_id="cloud-123",
    )

    with pytest.raises(exceptions.JiraNotFoundError):
        await client.get("/issue/MISSING-1")


@pytest.mark.asyncio
async def test_rest_client_normalizes_400():
    FakeAsyncClient.responses = [
        FakeResponse(
            status_code=400,
            payload={"errorMessages": ["Bad JQL"]},
        )
    ]
    client = JiraRESTClient(
        access_token="token",
        cloud_id="cloud-123",
    )

    with pytest.raises(exceptions.JiraQueryError):
        await client.get("/search/jql")


@pytest.mark.asyncio
async def test_rest_client_retries_429():
    FakeAsyncClient.responses = [
        FakeResponse(
            status_code=429,
            payload={"errorMessages": ["Rate limited"]},
            headers={"Retry-After": "0"},
        ),
        FakeResponse(
            status_code=200,
            payload={"accountId": "account-1"},
        ),
    ]
    client = JiraRESTClient(
        access_token="token",
        cloud_id="cloud-123",
        max_retries=1,
    )

    result = await client.get("/myself")

    assert result["accountId"] == "account-1"


def test_write_capabilities_are_disabled():
    connector = JiraConnector(config())
    capabilities = connector.get_capabilities()

    assert capabilities["write_issues"] is False
    assert capabilities["delete_issues"] is False
    assert capabilities["manage_projects"] is False


def test_cloud_id_is_required_for_connected_client():
    with pytest.raises(ValueError):
        JiraRESTClient(
            access_token="token",
            cloud_id="",
        )
