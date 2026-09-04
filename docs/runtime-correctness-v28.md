# Runtime Correctness — Phase 28

## Scope

Phase 28 makes `backend.indexer.index_engine` the canonical Azure AI Search
and LlamaIndex initialization boundary.

## Changes

- The maintained implementation now lives in `index_engine.py`.
- `index_engine_upgraded.py` is compatibility-only.
- No second Azure Search provider implementation remains behind the upgraded
  filename.
- The historical sync and async client behavior is preserved.
- Existing and legacy Azure Search field mappings remain explicit.
- `VALIDATE_INDEX` remains the default index-management mode.
- Credential selection remains caller-owned.
- No module-level Azure credential construction or asyncio patching is used.
- The explicit `close_index()` lifecycle remains available.

## Test boundary

The migration-era source-embedded `test_index_engine.py` was removed because it
loaded `/mnt/data/index_engine_upgraded.py`. Maintained boundary coverage now
lives under the repository-level `tests/` directory and verifies canonical
ownership, compatibility direction, API shape, validation, and lifecycle
presence without requiring Azure credentials.

## Compatibility

Existing imports from `backend.indexer.index_engine_upgraded` continue to
resolve through the compatibility module. New application code should import
from `backend.indexer.index_engine`.

## Verification

No local test suite was executed in this session. CI remains authoritative for
syntax, linting, maintained tests, and package build verification. Azure live
integration remains a deployment/environment validation concern.
