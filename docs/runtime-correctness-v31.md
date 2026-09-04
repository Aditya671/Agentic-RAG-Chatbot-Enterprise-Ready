# Runtime Correctness — Phase 31

## Azure Search ownership

Azure AI Search initialization now has one production implementation:

```text
backend.indexer.index_engine
        ↓
AzureAISearchVectorStore
        ↓
Azure AI Search
```

The historical `azure_search_initializer.py` path remains available only as a
compatibility adapter. The former `azure_search_initializer_upgraded.py`
implementation and its migration-era regression suite/report are removed.

## Preserved contract

- `initialize_index(...)` remains available through the historical initializer path.
- `close_index(...)` remains available through that path as well.
- Current and legacy Azure Search field mappings are unchanged.
- Sync and async client behavior is unchanged.
- Explicit index-management behavior is unchanged.
- Caller-owned Azure credentials remain the responsibility of the application.

## Why this matters

`index_engine.py` had already become the canonical implementation in Phase 28.
Leaving another full implementation under `azure_search_initializer_upgraded.py`
created two potential sources of truth. This phase removes that final duplicate
provider implementation and makes the compatibility direction explicit.

## Verification boundary

No local test suite was executed in this session. CI remains authoritative for
syntax, linting, maintained tests, and package build verification.
