# Indexer Canonicalization — Phase 19

## Current ownership

- Azure Search index creation: `backend.indexer.index_engine_upgraded`
- Document ingestion: `backend.indexer.llama_indexer_upgraded`
- User-uploaded file indexing: `backend.indexer.user_uploaded_file_indexer_upgraded`

Historical import paths remain thin compatibility surfaces and must not contain a second production implementation.

## Migration rule

When an indexer needs a behavior change, modify the upgraded implementation first. Compatibility modules should only preserve import names and re-export the canonical API.

This keeps application behavior deterministic while allowing downstream callers to migrate gradually.
