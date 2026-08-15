# `pdf_indexer.py` — Upgrade Report

## Status

**Complete — 34/34 regression tests passing.**

The original file is a PDF-specific LlamaIndex ingestion pipeline. It computes a
checksum, extracts PDF text with PyMuPDF, chunks the text, creates LlamaIndex
`Document` objects, initializes Azure OpenAI embeddings and Azure AI Search,
and indexes the resulting chunks. fileciteturn39file0 fileciteturn39file2

## Current API verification

The upgrade was checked against current public documentation.

- Azure AI Search's Python SDK separates index management through
  `SearchIndexClient` and document operations/search through `SearchClient`.
  citeturn0search0turn0search2turn0search10
- PyMuPDF documents support context-manager usage and explicit `close()`;
  `Page.get_text()` remains the current text extraction API. citeturn0search1turn0search3turn0search4

## Critical defect #1 — legacy LlamaIndex APIs

The original imports:

```text
GPTVectorStoreIndex
ServiceContext
```

and creates the index through:

```python
GPTVectorStoreIndex.from_documents(...)
```

This has been migrated to:

```text
Settings
StorageContext
VectorStoreIndex
```

The compatibility parameter `service_context` is retained in public functions
where useful, but it is no longer used as a LlamaIndex runtime object.

## Critical defect #2 — old Azure AI Search vector-store construction

The original uses:

```python
AzureAISearchVectorStore(
    service_name=...,
    api_key=...,
    index_name=...,
    embedding=...,
)
```

The upgraded implementation constructs an Azure `SearchIndexClient` and passes it
to the vector store, with explicit field mappings and index management.

This matches the current Azure SDK's client separation: `SearchIndexClient`
manages indexes, while `SearchClient` operates on indexed documents. citeturn0search0turn0search2

## Critical defect #3 — `force_reindex` was only a parameter

The original accepted `force_reindex` but did not use a real metadata/checksum
store. The source itself explicitly left checksum persistence as a TODO.
fileciteturn39file2

The upgraded implementation adds a local atomic JSON manifest containing:

```text
doc_id
checksum
index_version
source_path
filename
page_count
chunks_indexed
indexed_at
```

The flow is now:

```text
PDF
 ↓
SHA-256
 ↓
manifest
 ↓
unchanged?
 ├── yes → SKIP
 └── no  → INDEX
```

The manifest is intentionally local for this file-by-file upgrade. The final
architecture should later replace this with the project's durable metadata
store if that is selected as the canonical source of indexing state.

## Critical defect #4 — stale chunks during reindex

When a changed PDF generates a different number of chunks, inserting new chunks
without deleting old ones can leave stale data in the vector index.

The upgraded pipeline attempts to delete the previous document by `doc_id`
before reindexing.

## Critical defect #5 — broken chunking logic

The original implementation contained unnecessarily complex start-offset
calculation:

```text
start = max(...)
start = start + (...) if start == 0 else end - overlap
```

The upgraded implementation uses a deterministic step:

```text
step = chunk_size - overlap
```

and validates:

```text
chunk_size > 0
0 <= overlap < chunk_size
```

## Critical defect #6 — no page-aware chunk metadata

The original explicitly set:

```text
chunk_start_page = None
chunk_end_page = None
```

The upgraded implementation tracks page character ranges while extracting the
PDF and derives:

```text
chunk_start_page
chunk_end_page
```

This materially improves citation/provenance capability for PDF retrieval.

## Critical defect #7 — PDF resource leak

The original opened the document but did not explicitly close it.
fileciteturn39file0

The upgraded implementation closes the PyMuPDF document in `finally`.

PyMuPDF's current documentation explicitly supports closing documents and
context-manager usage. citeturn0search1turn0search4

## Critical defect #8 — checksum memory behavior

The upgraded implementation reads the file in 1 MiB blocks rather than loading
the complete PDF into memory.

## Critical defect #9 — naive UTC timestamps

The original used:

```python
datetime.utcnow()
datetime.utcfromtimestamp(...)
```

The upgraded implementation uses timezone-aware UTC timestamps.

## Critical defect #10 — empty PDF behavior

A PDF producing no text now returns:

```text
status = skipped
reason = empty_document
```

instead of attempting to create an empty vector index.

## Critical defect #11 — deterministic chunk IDs

Chunks now use:

```text
<doc_id>::chunk::<index>
```

as the LlamaIndex `id_`, rather than relying on implicit document IDs.

This makes ingestion/reindexing easier to reason about.

## Critical defect #12 — embedding dimension is configurable

The default is:

```text
3072
```

for:

```text
text-embedding-3-large
```

but production configuration can override:

```text
AZURE_OPENAI_EMBED_DIMENSION
```

This prevents silently hard-coding the vector dimension into the application.

## Configuration

Expected environment variables:

```text
AZURE_OPENAI_API_KEY
AZURE_OPENAI_ENDPOINT
AZURE_OPENAI_API_VERSION
AZURE_OPENAI_EMBED_MODEL
AZURE_OPENAI_EMBED_DEPLOYMENT
AZURE_OPENAI_EMBED_DIMENSION

AZURE_SEARCH_ENDPOINT
AZURE_SEARCH_SERVICE_NAME
AZURE_SEARCH_API_KEY
AZURE_SEARCH_INDEX_NAME
AZURE_SEARCH_VECTOR_ALGORITHM

PDF_INDEX_CHUNK_SIZE
PDF_INDEX_CHUNK_OVERLAP
PDF_INDEX_EMBED_BATCH_SIZE
PDF_INDEX_VERSION
PDF_INDEX_METADATA_PATH
```

`AZURE_SEARCH_ENDPOINT` takes precedence over deriving the endpoint from
`AZURE_SEARCH_SERVICE_NAME`.

## Regression suite

Added **34 tests** covering:

- SHA-256 checksums
- deterministic chunk offsets
- invalid chunk configuration
- empty input
- PDF resource cleanup
- PDF extension validation
- page extraction offsets
- page-range mapping
- stable document IDs
- deterministic chunk IDs
- metadata immutability
- current embedding initialization
- current Azure Search client initialization
- current `VectorStoreIndex`
- empty upsert behavior
- missing/non-PDF validation
- new PDF indexing
- unchanged-file skipping
- forced reindex
- changed-file reindex
- empty-PDF behavior
- absence of legacy LlamaIndex imports/calls
- timezone-aware timestamps
- streaming checksum
- PDF document cleanup

## Verification

Final test result:

```text
34 passed
```

No live Azure/OpenAI service was contacted.

## Architectural boundary

This file remains intentionally PDF-specific.

`llama_indexer.py` already provides a more general ingestion pipeline for:

```text
PDF
DOCX
TXT
Markdown
CSV
DataFrame
```

and therefore overlaps with this module. fileciteturn39file14

**I have not merged `pdf_indexer.py` into `llama_indexer.py` yet.**

The correct consolidation decision should be made only after
`user_uploaded_file_indexer.py` is independently upgraded.

## Deliverables

- `pdf_indexer_upgraded.py`
- `test_pdf_indexer.py`
- `pdf_indexer_upgrade_report.md`

## Batch status

```text
azure_search_initializer.py     COMPLETE
index_engine.py                 COMPLETE
llama_indexer.py               COMPLETE
pdf_indexer.py                 COMPLETE
user_uploaded_file_indexer.py  NEXT
```
