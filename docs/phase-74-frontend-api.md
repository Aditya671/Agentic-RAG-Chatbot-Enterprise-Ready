# Phase 74 — Frontend / API Integration

Expose the proven application journey through a client-facing boundary without creating a second application runtime.

`open application → upload → ingestion status → ask → grounded response → inspect evidence → continue conversation`

The maintained Chainlit application remains the presentation layer. `ApplicationRuntime` remains the execution boundary and `ApplicationSurface` is the thin UI/API projection layer.

## Completed implementation gate

The real Chainlit message callback delegates upload and question execution through `ApplicationSurface`. Upload submission uses the maintained asynchronous indexing boundary and preserves the stable returned task ID.

The upload confirmation exposes a user-triggered `check_indexing_status` action. The callback validates that the task ID belongs to the current Chainlit session before routing status through `ApplicationSurface.index_status`; arbitrary client-provided task IDs are rejected.

Question responses preserve run/conversation identity and evidence projections across the UI boundary. Evidence rendering consumes `ApplicationView.evidence`; the frontend no longer reparses the model response's citation payload to reconstruct source records. Legacy citation text may still be removed from the visible answer body for presentation, but source identity and citation metadata come from the application evidence contract.

Server-derived Chainlit session/user/thread identity is passed into the application surface. Client input cannot choose an arbitrary actor identity.

On chat resume, the frontend creates a persistence-aware application surface through the existing `ChainlitConversationStore` adapter and hydrates a separate `application_history` session projection through `ApplicationSurface.history()`. This restoration state is not injected into the LLM prompt automatically.

## Validation coverage

Deterministic source-level regression coverage verifies:

- the status action callback and task-ID ownership guard;
- propagation of the application-generated task ID into the action payload;
- explicit history-surface hydration on resume;
- persistence-aware application-runtime construction.

No client polling loop, automatic retry, duplicate indexing path, or automatic history injection was introduced.

## Non-goals

No second application runtime, replacement UI, provider-specific API models, automatic history injection, client-owned retries, fabricated evidence, or arbitrary client-driven tool execution.

## Exit criterion

The client-facing layer can invoke upload, status, question, evidence, and conversation-history capabilities through one canonical application boundary while preserving task identity, execution identity, evidence, explicit errors, and conversation isolation.

Phase 74 is complete. The next roadmap frontier is Phase 75 — Security & Governance.
