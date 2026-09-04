# Runtime Correctness — Phase 26

## Canonical PDF ingestion

PDF processing is now owned by the canonical multi-format `llama_indexer`
pipeline. The historical `pdf_indexer.py` path remains only as a compatibility
adapter for callers that still import PDF-specific helpers.

### Removed duplication

- Removed `pdf_indexer_upgraded.py`.
- Removed the migration-era PDF test that loaded code from `/mnt/data`.
- Removed the PDF upgrade report describing the superseded implementation.
- Removed the old LlamaIndex `GPTVectorStoreIndex`/`ServiceContext` execution path.

### Compatibility

`pdf_indexer.py` preserves the common PDF-facing helpers:

- checksum calculation;
- PDF text extraction;
- chunking;
- document metadata construction;
- document creation;
- embedding/vector-store initialization;
- PDF indexing.

These helpers delegate to `llama_indexer`, so there is one ingestion lifecycle,
one chunking contract, and one Azure AI Search integration surface.

### Canonical behavior

The maintained ingestion pipeline supports PDF alongside DOCX, TXT, Markdown,
and CSV. It uses current `VectorStoreIndex`/`Settings` APIs, deterministic
identifiers, checksum-based idempotency, bounded-memory checksum reads, and
explicit PDF resource cleanup.

### Verification boundary

The maintained regression test checks that the PDF path contains no independent
provider implementation and delegates indexing to the canonical multi-format
pipeline. CI remains authoritative; live Azure OpenAI and Azure AI Search
integration remains deployment validation.
