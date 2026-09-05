# Phase 74 — Frontend / API Integration

Expose the proven application journey through a client-facing boundary without creating a second application runtime.

`open application → upload → ingestion status → ask → grounded response → inspect evidence → continue conversation`

The maintained Chainlit application remains the presentation layer. `ApplicationRuntime` remains the execution boundary and `ApplicationSurface` is the thin UI/API projection layer.

## Current implementation gate

The real Chainlit message callback now delegates upload and question execution through `ApplicationSurface` rather than calling the maintained agent execution methods directly. Upload submission uses the existing asynchronous indexing boundary and preserves the returned task ID. Question responses preserve run/conversation identity and evidence projections across the UI boundary.

Evidence rendering consumes `ApplicationView.evidence`; the frontend no longer reparses the model response's citation payload to reconstruct source records. Legacy citation text may still be removed from the visible answer body for presentation, but source identity and citation metadata come from the application evidence contract.

Server-derived Chainlit session/user/thread identity is passed into the application surface. Client input cannot choose an arbitrary actor identity.

## Remaining Phase 74 exit work

The surface contract already exposes upload, status, question, evidence, and conversation-history capabilities. The remaining UI integration is deliberately small:

- expose a user-triggered Chainlit status action for the returned indexing task ID;
- use the surface history projection when restoring/continuing a persisted conversation;
- add callback-level deterministic coverage for those two interactions.

No client polling loop, automatic retry, duplicate indexing path, or automatic history injection should be introduced.

## Non-goals

No second application runtime, replacement UI, provider-specific API models, automatic history injection, client-owned retries, fabricated evidence, or arbitrary client-driven tool execution.

## Exit criterion

The client-facing layer can invoke upload, status, question, evidence, and conversation-history capabilities through one canonical application boundary while preserving task identity, execution identity, evidence, explicit errors, and conversation isolation.

The roadmap remains at Phase 73 until the remaining status/history callback wiring is complete.
