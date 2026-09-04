# Changelog

All notable changes to this project will be documented in this file. This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

## [0.2.6] - 2026-09-04

### Changed

- Extracted `similarity_top_k` validation into a provider-neutral runtime policy boundary.
- Prevented silent coercion of booleans, strings, floats, and other invalid retrieval settings.
- Wired the converged runtime to the shared retrieval-policy validator before constructing `RetrievalConfig`.
- Added dependency-light regression coverage for the retrieval policy.

---

## [0.2.5] - 2026-09-04

### Changed

- Ported retained legacy-runtime regression checks into the maintained top-level `tests/` boundary.
- Removed the dependency of the maintained regression checks on `/mnt/data` or other machine-specific temporary source paths.
- Documented the remaining compatibility inheritance and the next extraction boundary.
- Bumped the package version to `0.2.5` for the maintained runtime/test-boundary cleanup.

---

## [0.2.4] - 2026-09-04

### Changed

- Removed active runtime coupling to legacy private tool-builder helpers.
- Added provider-neutral tool factories for function and retriever tools.
- Preserved legacy private builders for compatibility callers.
