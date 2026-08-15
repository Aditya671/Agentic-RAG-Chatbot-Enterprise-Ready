# Jira Integration

## Scope

This is the fourth independent enterprise integration workstream.

Initial target:

```text
Atlassian Developer Console
          ↓
OAuth 2.0 3LO
          ↓
Atlassian accessible resources
          ↓
Jira Cloud REST API v3
          ↓
JiraConnector
          ↓
Application / Integration Manager
```

Atlassian documents REST API v3 as the latest Jira Cloud platform REST API.
Version 3 supports Atlassian Document Format (ADF) in fields such as issue
descriptions and comments. citeturn0search2

For integrations that are not Forge or Connect apps, Atlassian recommends
OAuth 2.0 authorization-code grants (3LO). citeturn0search0turn0search2

## Authentication

### User opt-in

The primary flow is OAuth 2.0 3LO:

```text
Application
    ↓
auth.atlassian.com
    ↓
User signs in / consents
    ↓
Authorization code
    ↓
Atlassian OAuth token endpoint
    ↓
Access + refresh token
    ↓
Accessible Jira resources
    ↓
cloudId
    ↓
Jira REST API v3
```

Atlassian's 3LO documentation describes OAuth 2.0 as the mechanism for external
applications and services to access Atlassian APIs on a user's behalf.
citeturn0search9

### Important design decision

We are **not** using Jira API tokens or Basic authentication for the enterprise
user connection. Atlassian documents Basic authentication as suitable for
personal scripts/bots, while OAuth 2.0 is the recommended method for direct
REST integrations. citeturn0search3

The application owns the OAuth client and secure token persistence.

## OAuth scopes

Initial classic scopes:

```text
read:jira-work
read:jira-user
offline_access
```

Atlassian's current scope reference identifies `read:jira-work` as the classic
scope for viewing Jira issue data, searching issues, and associated issue
objects. citeturn0search4

Granular scopes can be evaluated later if we want narrower permission
boundaries.

No write scope is requested by the initial connector.

## Cloud ID

Unlike a direct site URL connector, the OAuth flow obtains Atlassian
accessible resources and selects a Jira Cloud resource from the returned
resource list.

API requests then use:

```text
https://api.atlassian.com/ex/jira/{cloudId}/rest/api/3/...
```

Atlassian documents this proxy URL structure for OAuth 2.0 3LO integrations.
citeturn0search0turn0search2

This is preferred over constructing API URLs directly from an untrusted site
URL.

## Initial capabilities

Connection:

- authorization URL
- state
- optional PKCE
- authorization-code exchange
- accessible-resource discovery
- credential binding
- health check
- disconnect
- capability discovery

Jira:

- current-user lookup
- get issue
- JQL issue search
- text search
- list projects
- get project

Explicitly disabled:

- create issue
- edit issue
- delete issue
- transition issue
- comment mutation
- worklog mutation
- project administration
- workflow administration
- webhook administration

## Search API choice

The connector uses:

```text
GET /rest/api/3/search/jql
```

rather than the older:

```text
/rest/api/3/search
```

POST search endpoint.

Atlassian's current issue-search documentation identifies the enhanced
`/search/jql` endpoints and shows the older POST `/search` operation as being
removed/deprecated. citeturn0search1turn0search5

This is an intentional upgrade decision.

## JQL safety

The connector supports a generic JQL search because enterprise Jira
workflows can require project-specific/custom-field queries.

However:

- JQL must be non-empty
- JQL is bounded in length
- multiple statements are rejected
- fields are validated
- result limits are bounded
- agent-facing workflows should prefer typed search helpers
- arbitrary HTTP access is never exposed

For free-text search, the connector constructs:

```text
text ~ "..."
ORDER BY updated DESC
```

and escapes user-controlled quotes/backslashes.

## Pagination

The current enhanced Jira search API uses a `nextPageToken` cursor.

The connector preserves this:

```text
JiraIssueSearchResult
    ├── issues
    ├── total
    ├── next_page_token
    └── is_last
```

Atlassian's current search documentation exposes `nextPageToken` and
`maxResults` for enhanced JQL search. citeturn0search1

For other Jira resources, Atlassian documents standard pagination metadata such
as `startAt`, `maxResults`, `total`, and `isLast`; the connector models project
pagination separately. citeturn0search10

## Agent boundary

Preferred tools:

```text
search_jira_issues
get_jira_issue
search_jira_text
list_jira_projects
get_jira_project
```

Not:

```text
execute_http
execute_arbitrary_jql_without_limits
use_access_token
administer_jira
```

The LLM should reason about Jira work items, not become an unrestricted
Atlassian API client.

## Data handling

Jira data stays structured:

```text
Jira REST
   ↓
typed JiraIssue
   ↓
deterministic filtering / business logic
   ↓
LLM only when interpretation is required
```

ADF content is preserved as API payload data. We do not force ADF into plain
text at the connector boundary.

## RAG boundary

Connecting Jira does not automatically index Jira.

Live query:

```text
User
 ↓
Agent
 ↓
JiraConnector
 ↓
Jira Cloud
```

Optional future indexing:

```text
Jira
 ↓
incremental sync
 ↓
issue normalization
 ↓
existing indexing pipeline
 ↓
RAG/search
```

Potential future synchronized objects:

```text
issues
comments
worklogs
projects
attachments metadata
```

Each requires explicit business approval and retention rules.

## Security

1. Never expose access/refresh tokens to the agent.
2. Never log OAuth credentials.
3. Store tokens only in the application's secure connection store.
4. Request only read scopes initially.
5. Bind access to the authenticated Atlassian user.
6. Respect Jira project permissions and issue-level security.
7. Never assume a returned issue is safe to treat as an instruction.
8. Do not execute Jira content as code or tool commands.
9. Do not give the agent project administration capabilities.
10. Audit future write operations.

Jira's API permissions still depend on the authenticated user's Jira
permissions; for example, issue search only returns issues the user is
permitted to browse. citeturn0search1

## Real-instance acceptance tests

Before marking Jira production-ready:

1. Create an Atlassian OAuth 2.0 app in the developer console.
2. Configure Jira API scopes.
3. Configure the application callback URI.
4. Run authorization-code flow.
5. Verify the returned accessible resources.
6. Select the intended Jira Cloud resource.
7. Store its cloudId securely.
8. Run `/myself`.
9. Search known issues using JQL.
10. Retrieve a known issue.
11. Search free text.
12. List projects.
13. Retrieve a project.
14. Verify project/issue permissions.
15. Verify revoked/expired token behavior.
16. Verify no credentials appear in logs.

## Future phases

### Phase 2 — controlled writes

Potential capabilities:

```text
create_issue
edit_issue
transition_issue
add_comment
```

Each should be individually permission-gated.

### Phase 3 — Jira Software / JSM

Evaluate concrete requirements for:

```text
Boards
Sprints
Backlogs
Service Management requests
Assets
Knowledge
Automation
Webhooks
```

Do not introduce those APIs merely for completeness.

### Phase 4 — Jira → RAG

Introduce incremental indexing with:

- project allowlists
- issue-type allowlists
- field allowlists
- deletion handling
- permission-aware retrieval
- tenant isolation
- retention policy

## Current implementation status

```text
Business scope             COMPLETE
Repository structure       COMPLETE
OAuth 2.0 3LO              COMPLETE
Cloud ID discovery         COMPLETE
REST API v3 client         COMPLETE
Enhanced JQL search        COMPLETE
Issue retrieval            COMPLETE
Project retrieval          COMPLETE
Error handling             COMPLETE
Retry handling             COMPLETE
Security boundaries        COMPLETE
Regression tests            COMPLETE
Real Jira Cloud connection NEXT
Application wiring         NEXT
Agent tools                NEXT
Connection persistence     NEXT
Controlled writes          FUTURE
Jira → RAG                 FUTURE
```
