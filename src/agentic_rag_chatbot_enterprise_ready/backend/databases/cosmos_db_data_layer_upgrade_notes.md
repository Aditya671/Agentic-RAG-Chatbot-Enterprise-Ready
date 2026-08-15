# CosmosDBDataLayer upgrade and regression coverage

## Baseline problems found

- Dynamic string interpolation in every Cosmos SQL query.
- `create_user()` checked `isinstance(existing_user, User)` even though `get_user()` returns `PersistedUser`.
- `delete_user_session()` passed the partition-key field name rather than the partition-key value.
- `delete_element()` treated a single element dictionary as an iterable of items.
- `updatedAt` for existing users incorrectly reused `createdAt`.
- Duplicate `list_threads()` definitions meant the first implementation was silently overwritten.
- Thread queries used cross-partition querying while also supplying a partition key.
- Full thread listings were materialized into memory.
- `list_threads()` did not use Cosmos continuation tokens.
- `hasNextPage` was inferred from page length rather than the server continuation token.
- `get_thread()` performed one cross-partition feedback query per step.
- `print()` was used instead of structured logging.
- Exceptions were swallowed and returned as false values without useful context.
- The custom data layer lacked the current `close()` lifecycle method.
- The current Chainlit custom data-layer contract also includes `get_favorite_steps()`.
- The implementation mixed Chainlit's current data-layer contract with legacy method signatures.
- `indexing_policy` was defined in application code but was not actually applied to the container.

## Upgrade decisions

### Cosmos SDK

As of August 2026, `azure-cosmos` 4.16.2 is the current stable PyPI release. Microsoft recommends using at least 4.15.0; 4.16.x contains current reliability fixes and features.

The code remains compatible with the synchronous `CosmosClient`, but all blocking operations are isolated through `asyncio.to_thread()`.

A future repository-wide migration to `azure.cosmos.aio.CosmosClient` can be done as a separate architectural change once the entire application dependency graph is ready.

### Query safety

All user-controlled values are now Cosmos SQL parameters. This removes query construction/injection risks and improves maintainability.

### Partitioning

The existing `partition_thread_id` schema is preserved. Thread-scoped operations use `partition_key=thread_id`, avoiding unnecessary cross-partition scans.

### Pagination

`list_threads()` now exposes the Cosmos continuation token through Chainlit's `PageInfo` cursor fields instead of loading every thread into memory.

### Chainlit contract

The custom layer now implements:
- `get_user`
- `create_user`
- `upsert_feedback`
- `delete_feedback`
- `create_element`
- `get_element`
- `delete_element`
- `create_step`
- `update_step`
- `delete_step`
- `get_thread_author`
- `delete_thread`
- `list_threads`
- `get_thread`
- `update_thread`
- `delete_user_session`
- `get_favorite_steps`
- `close`

## Regression suite

The supplied regression suite contains 15 focused tests for the defects and behaviors observable at this component boundary.

Run:

```bash
pytest -q test_cosmos_db_date_layer.py
```

The tests are dependency-isolated and do not contact Azure.

## Production integration tests still required

Once the full repository is available, add integration coverage for:

- real Cosmos authentication with `DefaultAzureCredential`
- real partition-key schema
- continuation-token resume
- 429 throttling behavior
- transient network failures
- concurrent writes
- thread resume through Chainlit
- element persistence/retrieval
- feedback persistence
- hard-delete completeness
- guest TTL expiration
- cross-region behavior
- RU/query metrics
- shutdown/close behavior
