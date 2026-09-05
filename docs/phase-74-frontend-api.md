# Phase 74 — Frontend / API Integration

Expose the proven application journey through a client-facing boundary without creating a second application runtime.

`open application → upload → ingestion status → ask → grounded response → inspect evidence → continue conversation`

The maintained Chainlit application remains the presentation layer. `ApplicationRuntime` remains the execution boundary and `ApplicationSurface` is the thin UI/API projection layer.

```text
Chainlit / future HTTP API
          ↓
ApplicationSurface
          ↓
ApplicationRuntime
          ↓
┌─────────┼──────────┐
Upload   Question   Status
  ↓         ↓          ↓
existing maintained services
```

The client-facing projection exposes response text, capability, run ID, conversation ID, evidence projections, and normalized metadata. Conversation history exposes role, content, timestamps, message identity, and run linkage.

Evidence remains separately renderable from the answer. The surface never fabricates evidence or copies raw source content into evidence metadata.

Upload is separated from completion status. The client submits files and subsequently requests the existing indexing task status. The surface does not poll, retry, or duplicate worker execution; Phase 73 remains authoritative for background task identity and idempotency.

Question requests use the Phase 72 identity boundary when persistence is configured: `actor_id + session_id + conversation_id`. Persisted history is not automatically injected into the model; persistence and model-context consumption remain separate decisions.

Client-facing layers preserve bounded, actionable errors and must not turn failed indexing, missing evidence, authorization failures, or runtime failures into successful-looking answers.

### Non-goals

- No second HTTP application runtime.
- No replacement Chainlit UI.
- No provider-specific API models.
- No automatic conversation-history injection into prompts.
- No client-owned retries for background jobs.
- No fabricated source/evidence links.
- No arbitrary tool execution from client payloads.

### Exit criterion

The client-facing layer can invoke upload, status, question, evidence, and conversation-history capabilities through one canonical application boundary while preserving task identity, execution identity, evidence, explicit errors, and conversation isolation.
