# Phase 38 Status

This phase removes the retired coding-assistant option from the user-facing Chainlit configuration and stops the integrated compatibility runtime from accepting a frontend-only coding-assistant setting.

The application no longer advertises a capability that has already been removed from the execution runtime. Retrieval, GraphRAG, reranking, file indexing, CSV querying, and internet-search paths remain unchanged.

The canonical runtime's internal compatibility boundary is intentionally kept for a separate cleanup phase so this change does not mix frontend contract removal with larger runtime refactoring.

Local test execution is not claimed; repository CI remains authoritative.
