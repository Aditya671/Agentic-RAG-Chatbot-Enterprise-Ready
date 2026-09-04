# Changelog

All notable changes to this project will be documented in this file. This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.16] - 2026-09-04

### Changed

- Consolidated PDF ingestion onto the canonical multi-format `llama_indexer` pipeline.
- Reduced `pdf_indexer.py` to a compatibility adapter with no independent indexing implementation.
- Removed the duplicate `pdf_indexer_upgraded.py` implementation.
- Removed the migration-era PDF indexer regression suite and upgrade report.
- Preserved the historical PDF helper surface through delegation to canonical ingestion contracts.

---

## [0.2.15] - 2026-09-04

### Changed

- Promoted `frontend/app.py` to the canonical Chainlit implementation surface.
- Removed the duplicate `frontend/app_upgraded.py` implementation.
- Moved frontend regression coverage to the maintained top-level test boundary.
- Restored valid `pyproject.toml` TOML syntax and preserved the canonical CLI entry point.

---

## [0.2.14] - 2026-09-04

### Changed

- Removed the obsolete PandasAI CSV execution surface.
- Removed the duplicate PandasAI adapter implementation and migration-era test/report.
- Kept structured CSV analysis behind the maintained LlamaIndex query boundary.

---

## [0.2.13] - 2026-09-04

### Changed

- Promoted `backend.orchestration.graph_rag` to the canonical GraphRAG implementation surface.
- Replaced the deprecated `KnowledgeGraphIndex`/`SimpleGraphStore` architecture with `PropertyGraphIndex`/`SimplePropertyGraphStore`.
- Kept graph storage and vector retrieval as explicit, injectable dependencies.
- Preserved explicit Nebula configuration and prevented silent fallback from configured persistent GraphRAG to in-memory storage.
- Added incremental graph insertion, existing-graph loading, stable GraphRAG errors, and resource lifecycle management.
- Moved GraphRAG regression coverage into the maintained top-level test suite and removed the obsolete external `/mnt/data` test dependency.
- Reduced `graph_rag_upgraded.py` to a compatibility re-export and removed its migration-era upgrade report.

---

## [0.2.12] - 2026-09-04

### Changed

- Promoted `backend.orchestration.llm_models` to the canonical model registry.
- Added GPT-5.6 as an opt-in supported model without changing the GPT-5.1 application default.
- Separated model context-window limits from maximum output-token limits.
- Added explicit reasoning capability metadata, normalization, accessors, and validation.
- Moved model-registry regression coverage into the maintained top-level test suite.
- Removed the duplicate `llm_models_upgraded.py` implementation and its migration-era test/report.

---
