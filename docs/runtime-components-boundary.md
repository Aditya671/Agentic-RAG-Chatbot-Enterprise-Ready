# Optional Runtime Component Boundary

The maintained architecture now has an explicit construction boundary for optional runtime capabilities.

`Runtime Orchestration → runtime_components → Provider Components`

The boundary covers:

- reranking
- GraphRAG
- isolated code execution

Construction is lazy with respect to feature flags: disabled capabilities return `None` without constructing the underlying provider component. Reranker candidate depth is bounded by the active retrieval depth and the established five-result ceiling.

This module is a migration seam. The historical private builders remain in `agentic_ai_system_upgraded.py` until the maintained runtime is fully routed through the new boundary.
