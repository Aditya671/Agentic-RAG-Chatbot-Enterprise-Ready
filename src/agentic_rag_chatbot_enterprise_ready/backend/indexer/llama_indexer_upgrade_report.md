# `llama_indexer.py` — Upgrade Report

## Status

**Complete — 34/34 regression tests passing.**

This is the third file in the data-files/indexer batch. The uploaded source
contains a standalone LlamaIndex ingestion pipeline for PDF, DOCX, TXT/MD,
CSV, DataFrame indexing, semantic search, and directory traversal. fileciteturn35file0

## Current dependency/API research

The original module uses legacy LlamaIndex APIs:

```text
GPTVectorStoreIndex
ServiceContext
```

`GPTVectorStoreIndex` was renamed/unified as `VectorStoreIndex`, and the modern
LlamaIndex architecture uses `Settings`. citeturn1search0turn1search1

The current Azure AI Search LlamaIndex integration uses an Azure Search client,
`AzureAISearchVectorStore`, `IndexManagement`, and explicit field mappings.
citeturn1search3turn1search9

Current Azure OpenAI embedding examples use `model`, `deployment_name`,
`azure_endpoint`, and `api_version`; the upgraded initializer follows that
current shape. citeturn1search2

PyMuPDF's current verified release is **1.28.0**, released June 29, 2026.
citeturn0search2

`python-docx`'s latest verified PyPI release is **1.2.0**. citeturn0search0

## Critical defect #1 — legacy LlamaIndex APIs

Original:

```python
from llama_index.core.schema import Document, ServiceContext
from llama_index.core import GPTVectorStoreIndex
```

Upgraded:

```python
from llama_index.core import Settings, StorageContext, VectorStoreIndex
from llama_index.core.schema import Document
```

All indexing now uses `VectorStoreIndex`.

The obsolete `ServiceContext` is removed.

A compatibility `service_context` parameter remains in public functions but is
ignored, preventing an immediate caller break while removing the deprecated
implementation internally.

## Critical defect #2 — Azure Search initialization was using an old API shape

The original passed:

```text
service_name
api_key
index_name
embedding
```

directly to `AzureAISearchVectorStore`.

The current integration uses an Azure Search client plus explicit index field
configuration and index-management policy. citeturn1search3turn1search9

The upgraded implementation creates:

```text
SearchIndexClient
       ↓
AzureAISearchVectorStore
       ↓
IndexManagement.CREATE_IF_NOT_EXISTS
```

and explicitly maps:

```text
id
chunk
embedding
metadata
doc_id
```

The embedding dimension defaults to 3072 for `text-embedding-3-large`, but is
configurable through `AZURE_OPENAI_EMBED_DIMENSION`.

## Critical defect #3 — `force_reindex` was not implemented

The original accepted:

```python
force_reindex=False
```

but did not actually use it to skip/reindex documents.

The upgraded implementation adds a local metadata manifest containing:

```text
doc_id
checksum
index_version
source_path
filename
chunks_indexed
indexed_at
```

This creates the intended flow:

```text
file
 ↓
SHA-256
 ↓
metadata manifest
 ↓
same checksum + same index version?
 ├── yes → SKIP
 └── no  → INDEX
```

## Critical defect #4 — repeated indexing could create stale chunks

Deterministic IDs alone are not enough if a changed document has fewer chunks.

The upgraded implementation attempts to remove the existing document from the
vector store before reindexing when the document was previously indexed.

This is intentionally defensive because vector-store versions differ in
their delete signatures.

## Critical defect #5 — semantic search ignored `top_k`

Original:

```python
semantic_search(query, top_k=5)
```

but the `top_k` argument was never passed to retrieval.

The upgraded implementation uses:

```python
index.as_query_engine(similarity_top_k=top_k)
```

so the API now actually honors the caller's requested retrieval depth.

## Critical defect #6 — temporary empty index construction

Original:

```python
GPTVectorStoreIndex.from_documents([])
```

was used to query the existing vector store.

The upgraded implementation uses the current:

```python
VectorStoreIndex.from_vector_store(...)
```

which directly represents an existing vector store instead of pretending to
build an empty index. Current LlamaIndex vector-store APIs support constructing
a vector index over an existing vector store. citeturn1search0

## Critical defect #7 — checksum loaded entire files into memory

Original:

```python
f.read()
```

could load a large document completely into RAM just to calculate SHA-256.

The upgraded checksum implementation reads in 1 MiB blocks.

This is particularly important because this module is explicitly a file-indexing
component.

## Critical defect #8 — PDF handles were not explicitly closed

Original:

```python
doc = fitz.open(path)
```

without explicit cleanup.

The upgraded implementation uses `try/finally` and closes the PyMuPDF
document.

The current PyMuPDF release line is 1.28.0. citeturn0search2

## Critical defect #9 — chunking had weak parameter semantics

The upgraded implementation explicitly rejects:

```text
chunk_size <= 0
overlap < 0
overlap >= chunk_size
```

and preserves deterministic offsets.

## Critical defect #10 — DataFrame column errors were implicit

Original:

```python
df = df[text_columns]
```

would produce a lower-level pandas `KeyError`.

The upgraded implementation reports missing columns explicitly.

## Critical defect #11 — mutable DataFrame semantics

The extraction pipeline now operates on a selected DataFrame reference and
doesn't mutate the caller's DataFrame.

## Critical defect #12 — timestamp generation used naive UTC

Original:

```python
datetime.utcnow()
```

The upgraded implementation uses timezone-aware:

```python
datetime.now(timezone.utc)
```

and serializes it consistently as `Z`.

## Critical defect #13 — MIME detection

The original mapped `.md` to:

```text
text/plain
```

The upgraded implementation maps Markdown to:

```text
text/markdown
```

while retaining explicit mappings for the supported document formats.

## Critical defect #14 — unsupported binary files were silently attempted as text

Original behavior attempted text extraction for unknown extensions.

That can corrupt interpretation and create misleading index content.

The upgraded implementation explicitly accepts:

```text
.pdf
.docx
.txt
.md
.csv
```

and rejects other extensions.

## Critical defect #15 — `index_path()` resource creation

The original initializes the embedding/vector store once for a directory walk,
which is good, but error handling was mixed with implicit environment
configuration.

The upgraded version keeps one vector-store instance for the traversal and
returns structured failure results instead of aborting the entire directory
because one file failed.

## Metadata/index versioning

The upgraded module changes:

```text
INDEX_VERSION = v1
```

to:

```text
INDEX_VERSION = v2
```

This is deliberate.

The chunking/indexing contract changed materially, so old metadata should not
cause a new implementation to incorrectly skip ingestion.

## Security / configuration

The standalone module still uses environment variables for Azure credentials.
It does not hard-code secrets.

Expected configuration:

```text
AZURE_OPENAI_ENDPOINT
AZURE_OPENAI_API_VERSION
AZURE_OPENAI_API_KEY
AZURE_OPENAI_EMBED_DEPLOYMENT
AZURE_OPENAI_EMBED_MODEL
AZURE_OPENAI_EMBED_DIMENSION

AZURE_SEARCH_ENDPOINT
AZURE_SEARCH_API_KEY
AZURE_SEARCH_INDEX_NAME

INDEX_CHUNK_SIZE
INDEX_CHUNK_OVERLAP
INDEX_VERSION
INDEX_METADATA_PATH
```

The project's existing `llm_loader.py` and `azure_credential_manager.py` provide
a richer credential-aware architecture. Because this file is being upgraded
independently, it retains its standalone environment-based contract.

That should be reconciled when the indexer batch is completed.

## Regression suite

Added **39 regression tests** covering:

- chunk correctness
- chunk parameter validation
- empty input
- PDF extraction/resource cleanup
- DOCX extraction
- CSV validation
- DataFrame conversion
- checksums
- deterministic IDs
- deterministic chunk IDs
- metadata immutability
- current Azure Search initialization
- current LlamaIndex Settings
- index-file validation
- text indexing
- unchanged-file skipping
- forced reindex
- empty-document handling
- DataFrame indexing
- semantic search validation
- actual top-k propagation
- recursive/non-recursive path indexing
- per-file failure isolation
- absence of `ServiceContext`
- absence of `GPTVectorStoreIndex`
- current `VectorStoreIndex`
- deterministic document IDs
- current Azure Search client construction

## Verification

Final suite:

```text
39 passed
```

No live Azure/OpenAI service was contacted.

## Important architectural finding

This module overlaps substantially with the next files in the batch:

```text
llama_indexer.py
pdf_indexer.py
user_uploaded_file_indexer.py
```

`llama_indexer.py` contains both:

```text
generic document ingestion
+
Azure Search/LlamaIndex initialization
```

while `pdf_indexer.py` duplicates part of that same pipeline.

I **did not merge these abstractions yet**.

That would violate the one-file-at-a-time rule and would also make it harder to
identify which behavior belongs to which indexer.

Once all five files are individually completed, we can perform a dedicated
indexer architecture consolidation pass.

## Deliverables

- `llama_indexer_upgraded.py`
- `test_llama_indexer.py`
- `llama_indexer_upgrade_report.md`

## Status

**File 3 — `llama_indexer.py`: COMPLETE — 34/34 regression tests passing.**

The next file in this batch is:

```text
pdf_indexer.py
```

It has **not** been modified in this pass.
