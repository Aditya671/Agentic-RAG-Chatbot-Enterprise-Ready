# Phase 38 Status

This phase removes the retired coding-assistant option from the user-facing Chainlit configuration and compatibility construction layer.

The application no longer advertises a capability that has already been removed from the execution runtime. Retrieval, GraphRAG, reranking, file indexing, CSV querying, and internet-search paths remain unchanged.

Canonical runtime cleanup is intentionally kept separate so that the compatibility surface can be removed without mixing it with unrelated runtime refactoring.

Local test execution is not claimed; repository CI remains authoritative.
