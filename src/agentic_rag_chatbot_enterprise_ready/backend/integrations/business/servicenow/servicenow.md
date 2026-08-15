# ServiceNow Integration

## Scope

This is the third independent enterprise integration workstream after
SharePoint and Salesforce.

Initial target:

```text
ServiceNow instance
      ↓
OAuth 2.0
      ↓
ServiceNow Table API
      ↓
ServiceNowConnector
      ↓
Application / Integration Manager
```

The current ServiceNow Australia API reference documents the Table API as the
standard REST interface for CRUD access to existing tables. The calling
identity must have sufficient roles to access the table. citeturn0search0

## Authentication

### Delegated user-opt-in

The primary application model is OAuth authorization-code flow:

```text
Application
    ↓
ServiceNow OAuth authorize endpoint
    ↓
User login / consent
    ↓
Authorization code
    ↓
Application callback
    ↓
oauth_token.do
    ↓
Access token
    ↓
Table API
```

ServiceNow documents authorization-code flow for end users who own protected
resources in the ServiceNow instance. citeturn0search7

ServiceNow's current inbound REST documentation confirms OAuth 2.0 support for
external clients and the OAuth application registry. citeturn0search1

### Client credentials

A separate client-credentials mode is supported for controlled enterprise
service integrations.

ServiceNow's current documentation requires an OAuth Application User for
client-credentials integrations and specifically notes that REST API Auth
Scope should be used to control the access provided to the third-party
client. citeturn0search13

This is therefore not treated as a shortcut around user authorization.

## Authorization and scopes

ServiceNow supports REST API Auth Scope to restrict which REST APIs an OAuth
entity can access. Without configured auth scopes, valid OAuth entities may
otherwise access APIs not protected by a scope. citeturn0search4

Production configuration should therefore establish explicit scopes rather
than relying on broad default access.

## Initial capabilities

Connection:

- authorization URL
- state
- optional PKCE
- authorization-code exchange
- client credentials
- health check
- disconnect
- capability discovery

ITSM read operations:

- generic read-only Table API query
- record retrieval
- incident search
- request search
- change search
- pagination through offset

Explicitly disabled:

- POST/create
- PATCH/update
- PUT
- DELETE
- user administration
- ACL/security administration
- arbitrary Scripted REST execution
- arbitrary HTTP endpoint execution

ServiceNow's Table API supports CRUD, but the application intentionally starts
with read-only capabilities. citeturn0search0

## Agent boundary

Preferred future tools:

```text
search_servicenow_incidents
get_servicenow_incident
search_servicenow_requests
search_servicenow_changes
```

The agent should not receive:

```text
access_token
execute_http
arbitrary_table_mutation
arbitrary_script_execution
```

## Query safety

The generic read boundary validates:

- table identifiers
- field identifiers
- result limits
- offset
- display-value mode
- encoded-query size

Typed search methods do not accept arbitrary encoded queries from the agent.
They construct the query themselves.

The `^` character is escaped for the typed search phrase so user input cannot
silently add ServiceNow query clauses.

## Health check

The initial health check performs a minimal read against the Incident table
and requests only `sys_id`.

This intentionally verifies:

```text
token valid
   ↓
instance reachable
   ↓
REST API available
   ↓
identity has required ITSM read access
```

If the application's actual tenant does not grant incident access to the
connection identity, the health check should fail rather than reporting a
false "connected" state.

## Error handling

The transport layer normalizes:

```text
401 → authentication/authorization failure
403 → authorization failure
404 → not found
400 → query error
429 → bounded retry / rate-limit error
408/5xx → bounded retry
```

Timeouts and network failures also receive bounded retries.

## Data handling

ServiceNow records remain structured:

```text
ServiceNow
    ↓
Table API
    ↓
typed records
    ↓
deterministic business logic
    ↓
LLM only if interpretation is required
```

The connector does not automatically send retrieved incidents, requests, or
changes to an LLM.

## RAG boundary

ServiceNow connection does not automatically index ITSM records.

Live:

```text
Question
 ↓
ServiceNowConnector
 ↓
current ITSM data
```

Future optional sync:

```text
ServiceNow
 ↓
incremental synchronization
 ↓
normalization
 ↓
existing indexing pipeline
 ↓
search / RAG
```

The sync layer would need explicit object/field allowlists, retention,
deletion detection, tenant isolation, and audit requirements.

## Security rules

1. Never log OAuth access or refresh tokens.
2. Never expose tokens to the agent.
3. Keep secrets outside provider code.
4. Use explicit ServiceNow OAuth scopes.
5. Prefer least-privilege ServiceNow roles for the integration identity.
6. Use REST API Auth Scope for service-to-service access.
7. Keep write capabilities disabled until explicitly approved.
8. Treat incident descriptions and other ServiceNow fields as untrusted data.
9. Do not execute scripts supplied by retrieved records.
10. Audit external operations when the central Integration Manager is added.

## Repository structure

```text
backend/
└── integration/
    ├── servicenow_connector.py
    └── servicenow/
        ├── __init__.py
        ├── auth.py
        ├── client.py
        ├── models.py
        └── exceptions.py

tests/
└── integration/
    └── test_servicenow_connector.py

docs/
└── integrations/
    └── servicenow.md
```

## Real-instance acceptance tests

Before marking ServiceNow production-ready:

1. Create/configure ServiceNow OAuth endpoint for external clients.
2. Configure redirect URI.
3. Configure minimum OAuth scopes.
4. Configure required ServiceNow roles.
5. Complete user authorization.
6. Verify token exchange.
7. Run health check.
8. Search a known Incident.
9. Retrieve a known Incident by `sys_id`.
10. Search a known Request.
11. Search a known Change.
12. Verify unauthorized tables are inaccessible.
13. Verify token expiry/refresh behavior.
14. Verify disconnect removes local token state.
15. Verify no secrets appear in logs.
16. Verify client-credentials mode uses an explicitly configured OAuth
    Application User and REST API Auth Scope if service mode is enabled.

## Future phases

### Phase 2 — controlled writes

Potential capabilities:

```text
create_incident
update_incident
create_request
update_request
create_change
```

Each must be individually permission-gated and audited.

### Phase 3 — richer ServiceNow APIs

Evaluate only when justified:

```text
CMDB APIs
Knowledge APIs
Attachment APIs
Service Catalog APIs
Change APIs
Scripted REST APIs
```

### Phase 4 — ServiceNow → RAG

Build explicit synchronization for approved tables/fields only.

## Current implementation status

```text
Business scope             COMPLETE
Repository structure       COMPLETE
OAuth model                COMPLETE
Table API client            COMPLETE
Read-only capabilities      COMPLETE
Error handling              COMPLETE
Retry handling              COMPLETE
Query validation            COMPLETE
Security boundaries         COMPLETE
Regression tests             NEXT
Real ServiceNow connection  NEXT
Application wiring          NEXT
Agent tools                 NEXT
Connection persistence      NEXT
```
