# SharePoint Integration

## Scope

This integration targets **SharePoint Online through Microsoft Graph v1.0**.

It is intentionally independent from the hackathon architecture.

The integration is an enterprise capability that can later be exposed to the
agent through an integration manager.

## Repository placement

Recommended repository layout:

```text
backend/
└── integration/
    ├── sharepoint_connector.py
    └── sharepoint/
        ├── __init__.py
        ├── auth.py
        ├── client.py
        ├── models.py
        └── exceptions.py

tests/
└── integration/
    └── test_sharepoint_connector.py

docs/
└── integrations/
    └── sharepoint.md
```

The existing `sharepoint_connector.py` remains the public application-facing
entry point. The provider-specific internals are isolated under
`integration/sharepoint/`.

## Why Microsoft Graph

For SharePoint Online, Microsoft recommends using Microsoft Graph for modern
SharePoint REST operations. Graph exposes SharePoint sites, drives, files and
lists through the Microsoft Graph resource model. citeturn0search10turn0search13

The implementation therefore does not introduce the legacy SharePoint ACS
authentication model.

## Authentication model

The connector supports two explicit modes.

### Delegated — user opt-in

```text
User
 ↓
Application
 ↓
Microsoft Entra authorization
 ↓
Authorization code
 ↓
Access token
 ↓
Microsoft Graph
 ↓
SharePoint
```

This is the intended first-class model for "user opts in to SharePoint".

Microsoft documents delegated access as calling Graph on behalf of a signed-in
user, bounded by both the granted Graph permissions and the user's own
permissions. citeturn0search1

The authorization-code flow is used for the web application boundary. Microsoft
documents authorization code as the web-app flow for obtaining an access token
after the user signs in and consents. citeturn0search5

PKCE support is included in the connector.

### App-only — controlled enterprise service mode

```text
Application identity
       ↓
Microsoft Entra
       ↓
Application permission
       ↓
Microsoft Graph
       ↓
SharePoint
```

This mode is intentionally explicit because it has materially broader access
semantics. Microsoft states that application permissions operate without a
signed-in user and require administrator consent. citeturn0search1

## Permission strategy

Do **not** start with:

```text
Sites.ReadWrite.All
Files.ReadWrite.All
```

unless a concrete business capability requires them.

Microsoft recommends least-privilege Graph permissions. citeturn0search0turn0search4

For the first read-only MVP, the connector uses:

```text
Delegated:
    User.Read
    Sites.Read.All
    Files.Read
```

The exact tenant registration should be finalized against the application's
real capabilities before production consent.

For enterprise app-only deployments, prefer resource-scoped permissions such
as `Sites.Selected` where the deployment model permits it. Microsoft documents
Selected permissions for restricting application access to specific SharePoint
resources. citeturn0search14

## Initial business capabilities

### Connection

- build authorization URL
- PKCE support
- authorization-code exchange
- app-only authentication
- health check
- disconnect
- capability discovery

### SharePoint navigation

- resolve site by hostname/path
- retrieve site
- list document libraries/drives
- retrieve drive
- list folder children
- retrieve file/folder metadata

### Document operations

- download file
- search files
- optional site-scoped search

### Explicitly NOT enabled yet

- file upload
- file deletion
- file overwrite
- permission administration
- site creation
- list mutation
- sharing-link creation
- tenant-wide administration

This keeps the first integration read-only and reduces blast radius.

## Agent boundary

The agent should not receive:

```text
raw access token
Graph URL builder
arbitrary HTTP method
arbitrary Graph endpoint
```

It should eventually receive only bounded capabilities:

```text
search_sharepoint_files
get_sharepoint_file
list_sharepoint_files
get_sharepoint_site
list_sharepoint_document_libraries
```

The connector is therefore a deterministic capability layer.

## RAG boundary

Connecting SharePoint does **not** automatically mean copying SharePoint
documents into the existing RAG index.

There are two distinct capabilities:

```text
LIVE QUERY
    SharePoint → Graph → current result

INDEXED KNOWLEDGE
    SharePoint → ingestion → parser → chunker → index → retrieval
```

The first implementation provides live access.

SharePoint-to-RAG ingestion should be a later explicit capability with its own
authorization, sync, checksum, deletion detection, and audit requirements.

## Security rules

1. Never log access tokens.
2. Never put tokens in agent-visible tool output.
3. Never accept arbitrary absolute Graph URLs.
4. Validate provider configuration before connecting.
5. Keep permissions least-privileged.
6. Prefer resource-scoped application permissions where appropriate.
7. Treat SharePoint content as untrusted data.
8. Do not send retrieved documents to an LLM unless the calling workflow
   explicitly requires interpretation.
9. Keep read and write capabilities separately gated.
10. Audit every external operation once the application-level integration
    manager is added.

## Current implementation dependencies

The provider implementation is intentionally small:

```text
msal
httpx
```

Current stable versions checked during implementation:

```text
msal      1.37.0
httpx     0.28.1
```

MSAL is Microsoft's Python authentication library for Microsoft identity
platform/OAuth2/OpenID Connect. citeturn1search0

The Microsoft Graph Python SDK is also available, but the current Microsoft
Python tutorial describes it as preview. citeturn1search1turn1search7

For this project, the connector therefore uses the stable Graph HTTP API
boundary through `httpx` rather than coupling the core integration to the
preview SDK's generated request-builder surface.

If the repository already standardizes on a Graph SDK version later, the
low-level client can be replaced without changing the business capability
interface.

## Connection lifecycle

```text
NOT_CONNECTED
      │
      ▼
AUTHORIZATION_REQUIRED
      │
      ▼
AUTHORIZING
      │
      ▼
AUTHORIZED
      │
      ▼
VALIDATING
      │
      ▼
CONNECTED
      │
      ├──────────────► DISCONNECTED
      │
      └──────────────► RECONNECT_REQUIRED
```

## Production persistence requirement

The connector deliberately does not persist access tokens.

The application should provide a secure connection store containing:

```text
connection_id
provider
tenant_id
user/workspace identity
auth_mode
encrypted token cache
scopes
connected_at
last_health_check
status
```

Raw tokens should be encrypted at rest and never returned to the agent.

The existing application's Cosmos DB and Azure credential infrastructure can
later host this lifecycle, but that should be implemented as an application
integration-manager concern rather than hidden inside the provider adapter.

## Test strategy

The regression suite must remain deterministic and must not call Microsoft
Graph.

It covers:

- configuration validation
- delegated authorization URL
- PKCE
- authentication mode separation
- disconnected-state behavior
- health checks
- site resolution
- drive listing
- file/folder listing
- file download
- site-scoped search
- Graph error normalization
- rate-limit retry
- pagination
- external URL rejection
- capability validation

Real tenant tests are a separate integration-test stage.

## Real tenant acceptance tests

Before production enablement:

1. Register Microsoft Entra application.
2. Configure redirect URI.
3. Grant only required delegated permissions.
4. Complete user consent.
5. Resolve a known SharePoint site.
6. List its document libraries.
7. List a known folder.
8. Download a known test document.
9. Search for a known document.
10. Verify access is denied to an unauthorized site/resource.
11. Verify token expiry/refresh behavior.
12. Verify disconnect removes local token state.
13. Verify audit events.
14. Verify no secrets appear in logs.

## Future extension

The next layers should be:

```text
SharePointConnector
       ↓
IntegrationManager
       ↓
Authorization/Connection Store
       ↓
Agent Tool Adapter
       ↓
Optional SharePoint Ingestion Worker
       ↓
Existing indexing pipeline
```

The provider itself should remain independent of the agent framework.
