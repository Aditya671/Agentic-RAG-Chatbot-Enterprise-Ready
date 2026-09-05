# Phase 74 — Frontend / API Integration

Expose the proven application journey through a client-facing boundary without creating a second application runtime.

`open application → upload → ingestion status → ask → grounded response → inspect evidence → continue conversation`

The maintained Chainlit application remains the presentation layer. `ApplicationRuntime` remains the execution boundary and `ApplicationSurface` is the thin UI/API projection layer.

The client-facing projection exposes response text, capability, run ID, conversation ID, evidence projections, and normalized metadata. Conversation history exposes role, content, timestamps, message identity, and run linkage.

Evidence remains separately renderable from the answer. Upload is separated from completion status. The surface does not poll, retry, or duplicate worker execution.

Question requests use the Phase 72 identity boundary when persistence is configured: `actor_id + session_id + conversation_id`. Persisted history is not automatically injected into the model.

## Non-goals

No second application runtime, replacement UI, provider-specific API models, automatic history injection, client-owned retries, fabricated evidence, or arbitrary client-driven tool execution.

## Exit criterion

The client-facing layer can invoke upload, status, question, evidence, and conversation-history capabilities through one canonical application boundary while preserving task identity, execution identity, evidence, explicit errors, and conversation isolation.
