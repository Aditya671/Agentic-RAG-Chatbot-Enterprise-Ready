# Runtime Correctness — Phase 32

## Retrieval ownership

The maintained agent builder no longer constructs the provider retriever directly.
It delegates retriever construction to `IntegratedAsyncAgenticAiSystem` through
`build_provider_retriever()`.

The ownership path is:

```text
RetrievalConfig
      ↓
AgentRuntimeBoundary
      ↓
IntegratedAsyncAgenticAiSystem.build_provider_retriever()
      ↓
provider_boundaries.build_retriever()
      ↓
LlamaIndex / Azure retriever
```

This prevents the agent builder from becoming a second provider integration
point. Retrieval policy and provider translation now remain behind the runtime
integration boundary.

## What changed

- `agent_builder.py` delegates retriever creation to the integrated runtime.
- Reranker configuration remains an agent-builder concern and is passed as an
  optional provider postprocessor.
- Retrieval policy continues to come from the validated `RetrievalConfig` owned
  by the runtime boundary.
- Builder tests now validate the runtime-owned seam rather than duplicating
  provider-boundary behavior.
- Obsolete expectations for a removed arbitrary code-execution tool were removed
  from the maintained builder tests.

## Preserved behavior

- semantic/hybrid retrieval remains the configured query mode;
- configured `similarity_top_k` continues to flow through `RetrievalConfig`;
- reranking, GraphRAG, and structured CSV tools remain available where enabled;
- the public agent construction surface is unchanged.

## Verification

Focused builder tests were updated for the new ownership boundary. They do not
require Azure or LLM resources. Full repository CI remains authoritative for the
complete test, lint, and build suite.
