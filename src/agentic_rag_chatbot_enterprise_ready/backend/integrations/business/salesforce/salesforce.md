# Salesforce Integration

## Scope

This integration is part of the independent enterprise integrations layer.
It is not part of the Sun Life hackathon architecture.

Initial target:

```text
Salesforce External Client App
        ↓
OAuth 2.0
        ↓
Salesforce Platform REST API v67.0
        ↓
SalesforceConnector
```

Salesforce's Summer '26 platform API is v67.0, and Salesforce currently
supports API versions 31.0 through 67.0. citeturn0search4turn0search15

## Repository structure

```text
backend/
└── integration/
    ├── salesforce_connector.py
    └── salesforce/
        ├── __init__.py
        ├── auth.py
        ├── client.py
        ├── models.py
        └── exceptions.py

tests/
└── integration/
    └── test_salesforce_connector.py

docs/
└── integrations/
    └── salesforce.md
```

## Authentication

### User-opt-in mode

The primary mode is OAuth 2.0 authorization-code flow through a Salesforce
External Client App.

The flow is:

```text
Application
    ↓
Salesforce authorize endpoint
    ↓
User authenticates / consents
    ↓
Authorization code
    ↓
Application callback
    ↓
Salesforce token endpoint
    ↓
Access + refresh token
```

Salesforce's current Connect REST documentation describes External Client Apps
as the REST entry point and OAuth as the mechanism used to authenticate the
application. citeturn0search10

Salesforce's current External Client App documentation also supports OAuth
flow configuration and PKCE for suitable web integrations. citeturn0search3turn0search13

### Service-to-service mode

A separate `client_credentials` mode is supported for enterprise service
accounts. It must not be treated as equivalent to user authorization.

Salesforce documents client credentials as a server-to-server pattern where
the flow runs as a configured Salesforce user. citeturn0search11

## Current API strategy

The connector uses REST API v67.0.

The API version is configurable through `SalesforceAuthConfig`, but v67.0 is
the project default.

We should not hard-code an older version such as v59 or v60.

## Why REST instead of the Salesforce GraphQL API

GraphQL is supported by current Salesforce API versions and has useful
capabilities, but the first integration is intentionally REST/ SOQL based.

The first business requirements are:

- CRM record retrieval
- deterministic search
- record lookup
- simple pagination
- compatibility with standard Salesforce objects

Salesforce documents that GraphQL authorization uses the same Salesforce
OAuth model, but GraphQL has its own object/query limitations. citeturn0search7turn0search14

GraphQL can therefore be introduced later behind the same capability boundary
if it materially improves a specific use case.

## Initial capabilities

### Connection

- build OAuth authorization URL
- state generation
- optional PKCE
- authorization-code exchange
- client-credentials authentication
- connection health check
- disconnect
- capability discovery

### CRM read operations

- generic controlled SELECT/SOQL query
- query pagination
- search Accounts
- search Contacts
- search Opportunities
- search Cases
- retrieve Salesforce identity

### Explicitly disabled

- create
- update
- delete
- bulk mutation
- metadata mutation
- permission administration
- user administration
- Apex execution
- arbitrary REST endpoint execution

Write capabilities are deliberately false by default.

## SOQL safety

The connector exposes a controlled `query_soql()` capability because some
enterprise workflows will require fields/objects not known when the connector
is implemented.

However, agent-facing tools should preferentially use:

```text
search_accounts()
search_contacts()
search_opportunities()
search_cases()
```

rather than generating arbitrary SOQL.

The connector:

- allows only SELECT statements
- rejects multiple statements
- validates object identifiers
- validates field identifiers
- escapes user-provided string literals
- bounds search limits
- rejects arbitrary external URLs

This is defense-in-depth. Authorization remains the primary security boundary.

## Agent boundary

The agent should eventually receive tools like:

```text
search_salesforce_accounts
search_salesforce_contacts
search_salesforce_opportunities
search_salesforce_cases
get_salesforce_record
```

It should not receive:

```text
execute_http
execute_arbitrary_soql
use_access_token
```

unless a future explicitly authorized enterprise-admin capability requires
them.

## Data handling

Salesforce data should remain structured for as long as possible:

```text
Salesforce REST
      ↓
typed records
      ↓
business logic
      ↓
LLM only when interpretation/reasoning is needed
```

For example, filtering opportunities by amount or close date should be
performed deterministically rather than asking the LLM to inspect a large
unstructured response.

## RAG boundary

A Salesforce connection does not automatically index Salesforce records.

Live integration:

```text
User
 ↓
Agent
 ↓
SalesforceConnector
 ↓
Salesforce REST
```

Optional future indexing:

```text
Salesforce
 ↓
sync worker
 ↓
normalization
 ↓
existing indexing pipeline
 ↓
search / RAG
```

The sync pipeline requires its own:

- incremental strategy
- deletion detection
- object/field allowlist
- data retention rules
- tenant isolation
- audit policy

## Security

1. Never log access or refresh tokens.
2. Never expose tokens to the agent.
3. Store token material only through the application's secure connection store.
4. Use least-privilege Salesforce scopes.
5. Prefer External Client Apps for new registrations.
6. Use admin-approved users / permission-set restrictions where enterprise
   policy requires pre-authorization.
7. Keep read and write capabilities separately gated.
8. Never treat Salesforce records as trusted instructions.
9. Do not send Salesforce records to an LLM unless the workflow explicitly
   requires interpretation.
10. Audit external actions once the central integration manager is connected.

Salesforce's current External Client App documentation supports restricting
access through permission sets and OAuth policies. citeturn0search5

## API limits and retries

The transport client handles:

```text
401 → authorization error
403 → authorization error
404 → not found
400 → query error
429 → retry / rate-limit error
408/5xx → bounded retry
```

The implementation uses exponential backoff with a maximum retry delay.

Salesforce's Summer '26 documentation notes changes to Connect REST API rate
limits, so the connector deliberately does not hard-code an old per-user
hourly limit. citeturn0search4

## Pagination

Salesforce query responses can return:

```text
done
nextRecordsUrl
```

The connector preserves this contract and exposes `query_more()`.

We do not automatically download unlimited result sets. The calling workflow
controls pagination.

## Production connection persistence

The connector does not persist tokens.

The application-level integration manager should own:

```text
connection_id
provider
salesforce_org_id
user/workspace
auth_mode
encrypted token cache
scopes
instance_url
connected_at
last_health_check
status
```

The provider adapter should remain stateless with respect to durable secrets.

## Real-org acceptance tests

Before calling Salesforce production-ready:

1. Create Salesforce External Client App.
2. Configure OAuth authorization-code flow.
3. Configure callback URL.
4. Select minimum required scopes.
5. Optionally enable PKCE and verify the callback.
6. Authenticate with a test Salesforce user.
7. Verify `instance_url`.
8. Run health check.
9. Query Account.
10. Search an Account.
11. Search a Contact.
12. Search an Opportunity.
13. Search a Case.
14. Follow a `nextRecordsUrl`.
15. Verify access restrictions.
16. Verify expired-token behavior.
17. Verify disconnect/revocation behavior.
18. Verify no credentials appear in application logs.

## Future phases

### Phase 2 — controlled writes

```text
create_case
update_case
create_task
update_opportunity
```

Only after explicit business approval.

### Phase 3 — richer Salesforce APIs

Evaluate:

```text
GraphQL
Bulk API 2.0
Composite API
Change Data Capture
Platform Events
```

based on concrete application requirements rather than adding APIs for
completeness.

### Phase 4 — Salesforce → RAG

Add explicit synchronization for approved objects and fields.

## Current implementation status

```text
Business scope             COMPLETE
Repository structure       COMPLETE
OAuth model                COMPLETE
External Client App target COMPLETE
REST v67.0 client          COMPLETE
SOQL boundary              COMPLETE
CRM search capabilities    COMPLETE
Error handling             COMPLETE
Retry handling             COMPLETE
Pagination                 COMPLETE
Security boundaries        COMPLETE
Regression tests            COMPLETE
Real Salesforce connection NEXT
Application wiring         NEXT
Agent tools                NEXT
Connection persistence     NEXT
```
