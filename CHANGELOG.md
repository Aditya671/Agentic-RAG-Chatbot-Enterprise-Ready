# Changelog

All notable changes to this project will be documented in this file. This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.9] - 2026-09-04

### Changed

- Made the upgraded user-uploaded file indexer the canonical implementation behind the historical import path.
- Removed the duplicate legacy upload-indexer implementation from the maintained import surface.
- Preserved the public `backend.user_uploaded_file_indexer` compatibility path.
- Added regression coverage preventing the legacy surface from reintroducing a second implementation.

---

## [0.2.8] - 2026-09-04

### Changed

- Added a provider-neutral runtime component boundary for optional reranking, GraphRAG, and code execution.
- Preserved fail-open behavior when optional providers cannot initialize.
- Added dependency-isolated regression coverage for optional component construction.

---

## [0.2.7] - 2026-09-04

### Changed

- Extracted structured CSV prompt construction and provider invocation into a dedicated runtime boundary.
- Made the maintained converged runtime delegate CSV engine construction instead of assembling provider prompts inline.
- Added dependency-light regression coverage for the structured CSV runtime boundary.
- Kept the legacy upgraded runtime compatible while the maintained path owns the new boundary.

---
