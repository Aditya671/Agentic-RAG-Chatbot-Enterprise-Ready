# Runtime Correctness — Phase 25

## Canonical frontend surface

Phase 25 makes `frontend/app.py` the maintained Chainlit application entry point.
The former `app_upgraded.py` implementation was moved onto that stable path rather
than preserving two competing frontend implementations.

### Architecture

The frontend now follows the same canonicalization pattern established for the
model registry, GraphRAG, user-uploaded indexing, and orchestration runtime:

- `frontend/app.py` is the application implementation surface.
- The obsolete `frontend/app_upgraded.py` implementation is removed.
- The migration-era frontend regression module under `src/` is removed from the
  repository's maintained test surface.
- A small top-level boundary test verifies that the canonical file exists and
  that the obsolete upgraded implementation does not return.

### Compatibility

Deployment commands and imports already target `frontend/app.py`, so moving the
implementation onto that path removes an unnecessary compatibility indirection
rather than changing the public application entry point.

### Packaging correction

The phase also restores valid TOML syntax in `pyproject.toml` after the previous
PandasAI cleanup left the setuptools requirement without its closing quote. The
package version is advanced to `0.2.15`.

### Verification boundary

No local test suite was executed in this session. CI remains authoritative.
The frontend boundary test is intentionally dependency-light and does not claim
live Chainlit, Azure, Microsoft Graph, Cosmos DB, Blob Storage, or OpenAI
integration coverage.
