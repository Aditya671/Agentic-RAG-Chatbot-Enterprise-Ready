# `index_engine.py` — Upgrade Report

## File status

**Complete.** This was handled as the second file in the data-files/indexer
batch.

The uploaded `index_engine.py` is functionally identical to the previously
processed `azure_search_initializer.py`; the only source-level difference is
trailing whitespace/newline formatting. fileciteturn33file0

That matters because this file is effectively a duplicate implementation of
the same Azure AI Search/LlamaIndex initializer. I therefore applied the same
modernization contract rather than creating two divergent implementations.

## Current-version research

Verified against current public documentation on 2026-08-08:

- `llama-index` latest stable: **0.14.23**. citeturn0search6
- Azure AI Search Python client: **12.0.0**. citeturn0search0
- Azure AI Search exposes separate `SearchClient` and `SearchIndexClient`
  responsibilities and supports complete async APIs. citeturn0search0turn0search5
- Current Azure Search SDK uses the `2026-04-01` API by default in the current
  Python async index client documentation. citeturn0search2

## Findings

### 1. Global event-loop mutation

Original:

```python
nest_asyncio.apply()
```

Removed.

A reusable indexing module should not globally mutate the application's
asyncio event loop.

### 2. Global Azure credential creation

Original:

```python
credential = DefaultAzureCredential()
```

Removed.

The function already receives `search_service_credential`, so creating a second
credential at module import time was unnecessary and made dependency/lifecycle
behavior less predictable.

Azure's current SDK supports both key and Microsoft Entra credentials; the
application should own credential selection. citeturn0search0

### 3. Legacy LlamaIndex patterns

The upgraded implementation uses the current `Settings` + `VectorStoreIndex`
architecture and does not introduce `ServiceContext` or
`GPTVectorStoreIndex`.

Current `llama-index` 0.14.23 is the verified stable release. citeturn0search6

### 4. Index management is now explicit

Default:

```python
IndexManagement.VALIDATE_INDEX
```

Creation must be explicit:

```python
IndexManagement.CREATE_IF_NOT_EXISTS
```

This prevents a typo or deployment mistake from silently creating a differently
shaped index.

### 5. Sync and async clients are explicit

Sync:

```python
SearchIndexClient
```

Async:

```python
azure.search.documents.aio.SearchClient
```

Azure documents both client types and their async support. citeturn0search0

### 6. Legacy schema retained

The existing schema is preserved.

New/current:

```text
id
embedding
metadata
chunk
doc_id
```

Legacy:

```text
id
embedding
metadata
content
sourcepage
sourcefile
category
filepath
```

No database/index migration is silently performed.

### 7. Input validation

The upgraded implementation validates:

- index name
- endpoint
- credential
- LLM
- embedding model
- embedding dimension
- index-management mode
- supported keyword arguments

Unknown keyword arguments now fail instead of being silently ignored.

### 8. Azure client lifecycle

The returned index receives an explicit client lifecycle reference and exposes:

```python
await close_index(index)
```

The current Azure SDK exposes `close()` on Search clients. citeturn0search10

### 9. Exhaustive KNN intentionally preserved

The original uses:

```python
vector_algorithm_type="exhaustiveKnn"
```

This remains unchanged.

HNSW may be preferable at larger scale, but changing retrieval algorithm here
would be a performance/recall architecture decision. It should be evaluated
with a golden retrieval set rather than changed speculatively.

### 10. `use_azure` retained

The parameter remains for caller compatibility.

The supplied embedding model already determines whether Azure OpenAI or OpenAI
is being used, so `use_azure` does not need to control Azure Search client
construction.

## Regression suite

The regression suite contains **30 tests** covering:

- importability
- removal of `nest_asyncio`
- removal of global credential construction
- sync client construction
- async client construction
- index-management defaults
- explicit index creation mode
- enum/string compatibility
- invalid configuration
- unexpected kwargs
- missing LLM
- missing embedding
- invalid embedding dimension
- empty index name
- empty endpoint
- missing credentials
- current schema mapping
- legacy schema mapping
- LlamaIndex Settings
- vector-store binding
- client lifecycle
- async close
- sync close
- current LlamaIndex APIs
- absence of `GPTVectorStoreIndex`
- absence of `ServiceContext`
- current Azure async SDK usage
- removal of obsolete constants

The tests are dependency-isolated and do not contact Azure.

## Verification

Final complete-suite result:

```text
30 passed
```

Exit status:

```text
0
```

## Important architecture finding

There are now **two separate source files implementing the same initializer
logic**:

```text
azure_search_initializer.py
index_engine.py
```

They were effectively duplicates before this turn.

I intentionally did **not** delete, merge, redirect, or rename either file because
that would cross the strict one-file-at-a-time boundary.

After the full indexer batch is completed, this duplication should be addressed
as a separate repository-level cleanup decision.

The next file should therefore be analyzed independently rather than assuming
that all indexer modules share one contract.

## Deliverables

- `index_engine_upgraded.py`
- `test_index_engine.py`
- `index_engine_upgrade_report.md`

## Status

**File 2 — `index_engine.py`: COMPLETE — 30/30 regression tests passing.**

No other file in this batch was modified.
