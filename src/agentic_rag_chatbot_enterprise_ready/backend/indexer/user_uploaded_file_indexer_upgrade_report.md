# `user_uploaded_file_indexer.py` — Upgrade Report

## Status

**Complete — 34 regression tests passing.**

This file is the user-uploaded-document ingestion/query boundary. The original
implementation handled local uploads, persistent LlamaIndex vector storage,
document summaries, citation chat, and optional Azure Blob backup. fileciteturn41file1

This was the most important file in the current data-indexer batch because it
sits directly between the agent/Celery upload flow and the persistent user-file
index.

## Current LlamaIndex research

The current LlamaIndex architecture still supports the core pattern used here:
`VectorStoreIndex`, `StorageContext`, persisted indexes, and reloading persisted
storage. The current project README shows `VectorStoreIndex` + `StorageContext`
as the standard vector-index pattern. citeturn1search8turn1search5

Persisting a storage context to disk is the supported mechanism for the local
storage path used by this component. citeturn1search0turn1search9

`CondensePlusContextChatEngine` remains the appropriate abstraction for
conversation-aware retrieval followed by contextual response generation. Its
API accepts a retriever, LLM, memory, context prompt, and streaming/verbosity
configuration. citeturn1search3

## Critical defect #1 — mutable `Memory` default

Original:

```python
memory: Memory = Memory.from_defaults(...)
```

This creates state at function-definition time.

The upgraded constructor uses:

```python
memory: Optional[Memory] = None
```

and creates memory per instance.

This is essential because the class is used by a web application and Celery
workers.

## Critical defect #2 — task contract mismatch

The application already upgraded its Celery boundary to pass serialization-safe
file paths, while the original indexer primarily expected uploaded-file objects.
The original `index_uploaded_files()` calls:

```python
uploaded_file.name
uploaded_file.read()
```

even though the upgraded task boundary passes file paths. fileciteturn40file14

The upgraded indexer now accepts:

```text
file path
uploaded-file object
dictionary {name, content}
```

This makes the web upload path and Celery worker path compatible.

## Critical defect #3 — path traversal

The original writes:

```python
os.path.join(self.index_data_dir, uploaded_file.name)
```

without sanitizing the filename.

The upgraded implementation:

1. strips directory components,
2. removes control characters,
3. resolves the resulting path,
4. verifies the path remains inside the upload directory.

This closes the obvious `../` upload-path traversal class.

## Critical defect #4 — broken directory indexing

The original directory loop contains:

```python
file_paths = [os.path.join(input_dir, fname)]
```

inside the loop, replacing the previous value each time. It also attempts:

```python
os.makedirs(os.path.join(input_dir, fname), exist_ok=True)
```

for files discovered by `os.path.isfile()`. fileciteturn40file8

The upgraded implementation correctly collects every supported file:

```text
directory
  ├── file A
  ├── file B
  └── file C
        ↓
[file A, file B, file C]
```

and never creates directories at file paths.

## Critical defect #5 — vector and summary index were conflated

The original builds a `DocumentSummaryIndex`, but the query path subsequently
loads the same persisted storage context and calls:

```python
load_index_from_storage(...)
```

again for the summary path. fileciteturn42file0

That is not a reliable separation of vector and summary indexes.

The upgraded implementation persists:

```text
index_data/
├── vector_index/
│   ├── docstore.json
│   ├── index_store.json
│   └── vector store...
│
└── summary_index/
    ├── docstore.json
    ├── index_store.json
    └── ...
```

The query engine loads the correct index according to:

```text
query_type = vector_store
query_type = summary
```

## Critical defect #6 — existing files triggered unnecessary summary work

The original re-checks non-indexed files and constructs a summary index again
for already indexed documents. fileciteturn41file0

The upgraded path treats unchanged files as:

```text
SKIPPED
```

and does not rebuild their index.

## Critical defect #7 — naive timestamp comparison

Original:

```python
datetime.now() - datetime.fromisoformat(...)
```

The upgraded metadata uses timezone-aware UTC timestamps.

This avoids local-time/UTC ambiguity across development machines and Celery
workers.

## Critical defect #8 — metadata persistence was not atomic

Original:

```python
with open(metadata_path, "w") as f:
    json.dump(...)
```

A process crash during the write can leave corrupted metadata.

The upgraded implementation writes:

```text
metadata.json.tmp
       ↓
atomic replace
       ↓
metadata.json
```

## Critical defect #9 — no index-version invalidation

A checksum alone cannot detect a changed indexing algorithm.

The upgraded metadata includes:

```text
index_version
```

Therefore a future change to:

- chunk size,
- parser,
- metadata contract,
- embedding model,
- index format,

can intentionally invalidate previous entries.

## Critical defect #10 — file type and size validation

The upgraded component explicitly rejects unsupported file types and files
above the configured size limit before ingestion.

Default supported formats:

```text
.pdf
.docx
.doc
.txt
.md
.csv
.json
.xlsx
.xls
.pptx
.ppt
```

The exact parser availability remains dependent on the LlamaIndex reader
dependencies installed by the application.

## Critical defect #11 — duplicated LLM credential/deployment logic

The original constructs `AzureOpenAI` directly inside the indexer and reads
deployment configuration itself. fileciteturn41file2

The application already has a shared `llm_loader.py` and
`AzureCredentialManager`.

The upgraded indexer therefore uses the application's shared `load_llm()`
contract instead of creating another independent model/credential path.

This is important for the architecture because model/deployment selection should
remain centralized.

## Critical defect #12 — unsafe debug dumping

The original debug routine serializes internal vector/image/graph stores
directly to JSON. fileciteturn41file11

That risks exposing:

- embeddings,
- internal identifiers,
- potentially sensitive metadata.

The upgraded debug output deliberately records:

```text
document ID
metadata
text length
index version
timestamp
```

but not document content or embeddings.

## Critical defect #13 — `top_k` was not a public query contract

The original class stores `similarity_top_k`, but the chat engine API did not
provide a direct per-call override.

The upgraded method supports:

```python
create_local_citation_chat_engine(top_k=...)
```

and validates it.

## Critical defect #14 — summary prompt injection

The original already attempted moderation/sanitization, which was good, but
the upgraded implementation keeps the concept and makes the contract explicit:
uploaded content is treated as **data**, never as instructions.

The summary prompt explicitly says not to follow instructions contained inside
the uploaded file.

## Critical defect #15 — Blob upload implementation

The original performed multiple list operations to simulate directory creation
and pre-check object existence. fileciteturn41file7

The upgraded implementation relies on the Blob API's `overwrite=False` behavior
for the actual create operation, sanitizes the user namespace, and closes the
Blob service when the client supports `close()`.

## Critical defect #16 — index loading during query

The original manually checks:

```text
index_store.json
```

and then loads a generic index.

The upgraded implementation has explicit:

```text
_load_vector_index()
_load_summary_index()
```

so the query path is tied to the index type rather than the presence of one
generic storage directory.

## Persistence architecture

The upgraded file establishes:

```text
User Upload
    │
    ▼
Safe Upload Directory
    │
    ├── SHA-256
    │
    ▼
Index Metadata
    │
    ├── unchanged → skip
    │
    └── changed/new
            │
            ▼
      SimpleDirectoryReader
            │
            ▼
       LlamaIndex Documents
            │
       ┌────┴────┐
       ▼         ▼
 Vector Index  Summary Index
       │         │
       ▼         ▼
 vector_index summary_index
```

The final application architecture can later replace the local vector store
with the canonical Azure AI Search adapter where appropriate. That decision is
intentionally deferred until the complete indexer batch is finished.

## Regression suite

**34 tests** cover:

- constructor validation
- per-instance memory creation
- filename sanitization
- path containment
- file-size enforcement
- extension validation
- uploaded-object handling
- uploaded-dictionary handling
- metadata persistence
- atomic metadata writes
- checksum-based reindexing
- index-age reindexing
- chunk configuration
- path-based Celery compatibility
- dictionary-based Celery compatibility
- file limits
- invalid source combinations
- missing source validation
- unchanged-file skipping
- vector-index loading
- summary-index loading
- response-mode validation
- query-type validation
- top-k validation
- safe debug output
- legacy mutable-memory detection
- timezone-aware timestamps
- path-safety source checks
- separate summary persistence
- vector persistence

## Verification

Final regression run:

```text
34 passed
```

No Azure, Blob Storage, Key Vault, or LLM service was contacted.

## Important integration finding

This file revealed a concrete cross-file contract issue:

```text
AgenticAiSystem
      │
      ▼
Celery task
      │
      ▼
UserUploadedFileIndexer
```

The upgraded Celery task passes **file paths**, while the original
`UserUploadedFileIndexer` was primarily written around uploaded-file objects.

The upgraded indexer now supports both, so the contract is stable.

## Repository-level follow-up

After this batch, there should be a consolidation pass across:

```text
azure_search_initializer.py
index_engine.py
llama_indexer.py
pdf_indexer.py
user_uploaded_file_indexer.py
tasks.py
```

The likely final architecture is:

```text
                 ┌────────────────────┐
                 │ Upload/API boundary│
                 └─────────┬──────────┘
                           │
                 ┌─────────▼──────────┐
                 │ Ingestion service  │
                 └─────────┬──────────┘
                           │
                 ┌─────────▼──────────┐
                 │ Canonical indexer  │
                 └──────┬───────┬─────┘
                        │       │
                 ┌──────▼──┐ ┌──▼────────┐
                 │ Parser  │ │ Metadata  │
                 └──────┬──┘ └──┬────────┘
                        │        │
                        └────┬───┘
                             ▼
                       ┌───────────┐
                       │ Retrieval │
                       └───────────┘
```

**That consolidation has NOT been performed yet.**

## Deliverables

- `user_uploaded_file_indexer_upgraded.py`
- `test_user_uploaded_file_indexer.py`
- `user_uploaded_file_indexer_upgrade_report.md`

## Batch status

```text
azure_search_initializer.py       COMPLETE
index_engine.py                   COMPLETE
llama_indexer.py                 COMPLETE
pdf_indexer.py                   COMPLETE
user_uploaded_file_indexer.py    COMPLETE
```

**The data-files/indexer batch is now individually complete.**
