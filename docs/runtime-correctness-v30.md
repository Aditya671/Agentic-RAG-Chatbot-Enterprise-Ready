# Runtime Correctness — Phase 30

## Execution-contract ownership

The converged `IntegratedAsyncAgenticAiSystem` now delegates response-text normalization to the dependency-light `execution_contract` module.

The maintained runtime path is:

```text
public agent surface
        ↓
IntegratedAsyncAgenticAiSystem
        ↓
AgentRuntimeBoundary
        ↓
execution_contract / provider boundaries
```

The integration class no longer carries a second implementation of response-text extraction. This matters because LlamaIndex response objects can expose text through nested or provider-specific attributes; application code should have one normalization rule rather than several subtly different copies.

## Preserved behavior

- `AsyncAgenticAiSystem` public compatibility surface
- existing provider execution and tool orchestration
- `get_response()` dictionary contract
- retriever metadata extraction
- synchronous and asynchronous response-stream collection
- retrieval policy through `RetrievalConfig`

## Verification

Focused tests cover:

- nested response normalization through the integrated runtime;
- preservation of retriever metadata;
- sync/async stream collection;
- retrieval-policy refresh without provider calls.

The Azure/LLM integration remains outside the unit-test boundary. CI is authoritative for the full repository test, lint, and package-build checks.

## Next cleanup boundary

The internal historical runtime still contains compatibility-only capability/configuration code, including retired code-execution references. That cleanup should be performed as a dedicated migration rather than by silently changing the public API in this phase.
