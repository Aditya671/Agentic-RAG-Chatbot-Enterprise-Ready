# Refactor baseline and audit

This branch is an enhancement-only modernization of the existing Agentic RAG Chatbot. The business workflow remains unchanged: users can chat against enterprise documents, route structured CSV questions to tabular analysis, search the internet, upload files for indexing, persist conversation state, and optionally use GraphRAG/coding capabilities.

## Initial audit findings

1. **Package/runtime drift** — `pyproject.toml` used very broad minimum versions and several stale package names/versions. This made environments non-reproducible and allowed incompatible dependency combinations.
2. **Import topology mismatch** — the source is packaged under `src/agentic_rag_chatbot_enterprise_ready`, while application modules import `backend.*` as though `backend` were a top-level package. Compatibility shims are being introduced rather than forcing a disruptive rewrite.
3. **Entrypoint mismatch** — the CLI referenced files such as `src/frontend/app.py` and `src/backend/app.py` that do not match the repository layout. The frontend entrypoint is now rooted at `/frontend/app.py` and a runtime check is exposed as `agentic-rag --check`.
4. **Configuration fragility** — configuration defaults to `./config.yml`, but the repository does not contain that file. Configuration loading therefore silently falls back to an empty configuration and later fails deep inside initialization.
5. **Mutable defaults** — the agent constructor and thread summarizer use mutable default arguments (`list`/`dict`), which can leak state between instances.
6. **Async correctness** — `nest_asyncio` plus repeated `asyncio.run()` calls make execution context dependent and can fail when the Chainlit event loop is already running.
7. **Response handling** — the current agent code mixes `AgentRunResponse`, response blocks, dictionaries, and strings, making streaming and citation extraction brittle.
8. **UI/runtime coupling** — the old frontend performs network/storage work at module import time, which makes startup fragile and prevents clean test isolation.
9. **Upgrade debris** — the repository contains parallel `*_upgraded.py` files and upgrade reports beside canonical modules. This obscures which implementation is authoritative and increases regression risk.
10. **Missing verification gate** — there was no repository-level CI gate that validates imports, compilation, linting, and tests on supported Python versions.

## Refactor principles

- Preserve the existing business behavior and Azure-native direction.
- Prefer stable releases over previews unless a business feature explicitly requires preview functionality.
- Make dependencies reproducible.
- Keep public/import compatibility while the internal modules are consolidated.
- Fail fast on configuration errors instead of failing after partial initialization.
- Keep cloud calls out of module import time.
- Make async boundaries explicit.
- Add tests around deterministic behavior before changing integration behavior.
- Do not silently replace Azure services or the existing RAG/agent architecture with unrelated frameworks.

## Dependency baseline verified against PyPI on 2026-09-04

- Chainlit 2.12.0
- LlamaIndex 0.14.24
- LlamaIndex Azure OpenAI LLM 0.5.5
- LlamaIndex Azure OpenAI embeddings 0.5.2
- LlamaIndex Azure AI Search vector store 0.5.0
- Azure AI Projects 2.5.0
- Azure Search Documents 12.0.0 (latest stable; 12.1.x is still beta)
- Azure Cosmos 4.16.3
- Azure Storage Blob 12.30.1
- Azure Identity 1.25.3
- Azure Key Vault Secrets 4.11.2
- pandas 3.0.5
- python-dotenv 1.2.3
- pytest 9.1.1

## Important validation limitation

This environment can modify the GitHub repository, but it cannot authenticate to the user's Azure tenant or execute the cloud-backed Chainlit application against their real Azure AI Search, Cosmos DB, Blob Storage, Key Vault, or Foundry resources. CI therefore validates the deterministic/local contract; cloud integration validation must run with the repository's configured Azure credentials and services.

## Next refactor passes

1. Consolidate canonical modules and retire duplicate `*_upgraded.py` implementations.
2. Modernize the agent execution/streaming contract.
3. Harden configuration and credential handling.
4. Refactor ingestion/indexing into deterministic stages with explicit status/error models.
5. Harden Cosmos persistence and Chainlit resume behavior.
6. Add integration-test seams for Azure AI Search, Blob Storage, Cosmos DB, and Foundry.
7. Validate the complete upload -> index -> retrieve -> tool -> answer -> citation -> persistence flow.
8. Remove dead dependencies and stale documentation after tests prove they are unused.
