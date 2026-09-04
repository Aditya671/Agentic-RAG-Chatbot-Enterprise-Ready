# Changelog

All notable changes to this project will be documented in this file. This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.12] - 2026-09-04

### Changed

- Promoted `backend.orchestration.llm_models` to the canonical model registry.
- Added GPT-5.6 as an opt-in supported model without changing the GPT-5.1 application default.
- Separated model context-window limits from maximum output-token limits.
- Added explicit reasoning capability metadata, normalization, accessors, and validation.
- Moved model-registry regression coverage into the maintained top-level test suite.
- Removed the duplicate `llm_models_upgraded.py` implementation and its migration-era test/report.

---

## [0.2.11] - 2026-09-04

### Removed

- Removed E2B and remote sandbox code execution from the application runtime.
- Removed the coding-assistant agent tool and related runtime wiring.
- Removed obsolete E2B implementation, upgrade-report, and regression-test files.
- Retained only an explicit compatibility placeholder that rejects attempts to instantiate the removed sandbox capability.

### Changed

- Simplified the agent prompt/tool surface so arbitrary Python execution is no longer advertised or exposed.
- Defined retrieval, uploaded-file indexing, internet search, GraphRAG, and structured CSV analysis as the supported agent capabilities.

---

## [0.2.10] - 2026-09-04

### Changed

- Made `backend.orchestration.llm_loader` the canonical implementation surface for LLM and embedding loading.
- Reduced `llm_loader_upgraded.py` to a compatibility re-export instead of a second implementation.
- Preserved Azure OpenAI, Microsoft Entra ID, API-key, Key Vault, and non-Azure OpenAI loading behavior.
- Added a regression guard preventing the upgraded loader from becoming a second implementation surface.

---

## [0.2.9] - 2026-09-04

### Changed

- Made the upgraded user-uploaded file indexer the canonical implementation behind the historical import path.
- Removed the duplicate legacy upload-indexer implementation from the maintained import surface.
- Preserved the public `backend.user_uploaded_file_indexer` compatibility path.
- Added regression coverage preventing the legacy surface from reintroducing a second implementation.

---
