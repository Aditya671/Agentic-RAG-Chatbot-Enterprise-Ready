# Optional Runtime Component Boundary — Phase 18

`Runtime Orchestration → runtime_components → Provider Components`

The new boundary covers reranking, GraphRAG, and isolated code execution. Disabled capabilities return `None` without constructing their provider components. Reranker depth remains bounded by the active retrieval depth and the established five-result ceiling.

The historical private builders remain in `agentic_ai_system_upgraded.py` during migration. The next convergence phase will route the maintained runtime through these factories before reducing the compatibility builders.
