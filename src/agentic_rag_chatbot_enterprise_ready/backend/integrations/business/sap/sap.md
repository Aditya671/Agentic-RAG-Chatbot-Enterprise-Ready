# SAP Integration

## Scope

SAP is the fifth enterprise integration workstream.

The initial connector is deliberately an **OData integration boundary**, not a
hard-coded S/4HANA business-module implementation.

```text
SAP S/4HANA / SAP product
          ↓
     OData service
          ↓
     SAPConnector
          ↓
Application / Integration Manager
```

SAP S/4HANA Cloud Public Edition currently documents OData APIs and supports
OAuth 2.0, certificate authentication, and Basic Authentication for supported
APIs. For example, the current Purchase Order OData V4 API documents Basic,
certificate, and OAuth 2.0 authentication. citeturn1search14

## Why generic OData first

SAP is not one API.

An enterprise SAP landscape may expose:

```text
S/4HANA
SuccessFactors
Ariba
Concur
SAP BTP services
custom OData services
on-premise SAP through BTP Connectivity / Cloud Connector
```

Hard-coding a single business object such as PurchaseOrder would therefore
make the integration brittle.

The stable first boundary is:

```text
authentication
      +
OData protocol
      +
safe entity querying
```

Business-specific adapters can sit above it.

## Authentication

### Primary: OAuth 2.0 client credentials

The first-class service-to-service model is:

```text
Application
    ↓
OAuth token endpoint
    ↓
client credentials
    ↓
access token
    ↓
SAP OData API
```

SAP BTP documents OAuth2ClientCredentials destinations for consuming
OAuth-protected resources and notes that access tokens can be cached and
automatically renewed by the Destination service. citeturn1search3

The connector supports direct OAuth token acquisition for environments where
the application owns the OAuth configuration.

### Basic authentication

Basic authentication is retained as a compatibility mode because supported SAP
OData APIs may expose it. The current S/4HANA Cloud Purchase Order OData V4
documentation explicitly lists Basic Authentication as a supported method for
that API. citeturn1search14

This is not the preferred enterprise default.

### Bearer token

A pre-acquired bearer token can also be injected when authentication is handled
by an external enterprise identity/connectivity layer.

### SAP BTP Destination Service

Destination Service is intentionally **not hard-coded into the connector**.

SAP documents Destinations as a recommended approach for BTP connectivity,
including OAuth client-credentials scenarios, with token caching and renewal.
citeturn1search6turn1search3

Future application infrastructure can provide:

```text
Application
    ↓
SAP Destination Manager
    ↓
BTP Destination
    ↓
Cloud Connector / Internet
    ↓
SAP system
```

The connector can remain unaware of whether the OData endpoint is reached
directly or through a destination/proxy.

## On-premise SAP

On-premise connectivity is not assumed to be direct internet access.

SAP BTP documents OAuth client-credentials destinations with both Internet and
OnPremise proxy types; OnPremise scenarios can use Cloud Connector. citeturn1search3

Therefore:

```text
SAP on-premise
     ↑
Cloud Connector
     ↑
SAP BTP Connectivity
     ↑
Application
```

is an infrastructure concern and should not be implemented as an unsafe
network bypass in `sap_connector.py`.

## OData versions

The connector supports:

```text
OData V2
OData V4
```

because SAP enterprise landscapes still expose both generations.

The response normalizer understands:

### V4

```json
{
  "value": []
}
```

and:

```text
@odata.nextLink
@odata.count
```

### V2

```json
{
  "d": {
    "results": [],
    "__next": "..."
  }
}
```

and:

```text
__count
```

## Initial capabilities

```text
metadata()
query_entity_set()
get_entity()
follow_next_link()
health_check()
authenticate()
disconnect()
get_capabilities()
```

Explicitly disabled:

```text
write_records
delete_records
execute_actions
```

## Query safety

The connector validates:

- entity-set names
- property names
- `$top`
- `$skip`
- `$filter` length
- `$filter` character set
- `$orderby`
- entity keys
- next-link host

The agent should not receive arbitrary SAP HTTP access.

Preferred future tools:

```text
search_sap_entity
get_sap_entity
get_sap_metadata
```

Business adapters can then provide safer domain-specific tools such as:

```text
search_purchase_orders
get_purchase_order
search_sales_orders
get_sales_order
```

only after the exact SAP API contract has been selected.

## Health check

The generic health check calls:

```text
$metadata
```

rather than assuming a particular business entity exists.

This validates:

```text
authentication
      +
network reachability
      +
OData service availability
```

without requiring the integration identity to have access to a particular
business object.

## Error handling

The transport layer normalizes:

```text
401 → authentication failure
403 → authorization failure
404 → not found
400 → query error
429 → bounded retry
408 → bounded retry
5xx → bounded retry
timeout → bounded retry
network error → bounded retry
```

## Agent boundary

The LLM must never receive:

```text
client_secret
access_token
password
```

and should not be allowed to choose:

```text
HTTP method
arbitrary URL
arbitrary action
```

The connector is a capability boundary.

## RAG boundary

SAP connectivity does not automatically mean SAP data gets indexed.

Live:

```text
User
 ↓
Agent
 ↓
SAPConnector
 ↓
SAP
```

Future optional synchronization:

```text
SAP
 ↓
incremental extraction
 ↓
normalization
 ↓
existing indexing pipeline
 ↓
RAG/search
```

Permission-aware synchronization is mandatory before indexing enterprise SAP
data because different users may have different business-data visibility.

## Business-module adapters

After the generic connector is proven against a real tenant, introduce
business adapters one at a time.

Potential examples:

```text
sap/s4hana/
    purchase_orders.py
    sales_orders.py
    business_partners.py
    products.py
```

These must be generated from the selected SAP API contract rather than invented
field names.

SAP provides API documentation and business API metadata through the SAP
Business Accelerator Hub and S/4HANA API documentation.

## Real-instance acceptance tests

Before marking SAP production-ready:

1. Identify the exact SAP product and tenant.
2. Identify the exact OData service.
3. Identify whether it is OData V2 or V4.
4. Configure the OAuth client or approved authentication mechanism.
5. Configure the minimum required SAP roles/scopes.
6. Connect.
7. Run `$metadata`.
8. Query a known read-only entity set.
9. Retrieve one known entity.
10. Follow an OData next link.
11. Verify 401/403 behavior.
12. Verify no credentials appear in logs.
13. Verify the integration identity cannot mutate data through the current
    connector.
14. If on-premise, validate the BTP/Cloud Connector route separately.
15. Validate permission behavior with a second appropriately restricted
    enterprise identity.

## Future phases

### Phase 2 — business API adapter

Select the first concrete SAP business domain.

### Phase 3 — controlled writes

Only after explicit business approval:

```text
create
update
action/function import
```

Each capability gets its own authorization and regression tests.

### Phase 4 — BTP Destination integration

Allow the central integration layer to resolve SAP destinations instead of
storing raw connectivity configuration inside the provider connector.

### Phase 5 — SAP → RAG

Implement incremental, permission-aware extraction.

## Current implementation status

```text
Business scope             COMPLETE
Repository structure       COMPLETE
OData V2/V4 boundary       COMPLETE
OAuth client credentials   COMPLETE
Basic compatibility        COMPLETE
Bearer compatibility       COMPLETE
Metadata                    COMPLETE
Entity-set query            COMPLETE
Entity retrieval            COMPLETE
Pagination next-link        COMPLETE
Error handling              COMPLETE
Retry handling              COMPLETE
Security boundaries         COMPLETE
Regression tests             NEXT
Real SAP connection         NEXT
Exact business API          NEXT
Application wiring          NEXT
SAP → RAG                   FUTURE
Controlled writes           FUTURE
```
