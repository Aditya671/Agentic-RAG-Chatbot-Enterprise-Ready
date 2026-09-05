# Agentic RAG — End-to-End Development Plan

**Status:** Active engineering roadmap  
**Current implemented frontier:** Phase 73 — Background Processing & Idempotency  
**Primary goal:** Build a complete Agentic RAG application together with the engineering system required to observe, replay, evaluate, benchmark, and improve it.

> This roadmap supersedes the previous application-only phase sequence. The repository has progressed beyond basic runtime hardening: it now contains a reliability foundation, observability, provenance, harness/replay, retrospective analysis, scenario-aware evaluation, regression promotion, durable reliability storage, claim/evidence grounding, a canonical application runtime, canonical document ingestion, a retrieval-to-grounded-answer boundary, an end-to-end RAG scenario, provider-neutral conversation persistence, and a background processing/idempotency boundary. Future work must build on those capabilities rather than restarting the project from application plumbing.

---

## 1. What We Are Building

The project has two tightly connected products:

### A. The Agentic RAG Application

A user-facing system that can:

`question/upload → understand request → retrieve/use capabilities → execute bounded tools → gather evidence → answer → persist state`

### B. The Agent Engineering System

A development and evaluation layer that can:

`observe → trace provenance → replay → retrospect → evaluate → benchmark → promote regressions → improve architecture`

The second system is not a side project. It is what allows the first system to become reliable rather than merely functional.

---

# 2. Engineering Model

```text
                         Agent Application
                                │
                                ▼
                         Agent Runtime
                                │
                  ┌─────────────┼─────────────┐
                  ▼             ▼             ▼
            Observability  Provenance     Evidence
                  └─────────────┼─────────────┘
                                ▼
                         Harness + Replay
                                │
                                ▼
                          Retrospective
                                │
                                ▼
                           Evaluation
                                │
                                ▼
                     Architecture Benchmark
                                │
                                ▼
                    Regression / Improvement
                                │
                                └──────► Runtime
```

The feedback loop is the core architecture of the project.

---

# 3. Completed Engineering Foundation

The roadmap must preserve the work already implemented.

## Phase 55 — Agent Reliability Foundation

Established common reliability contracts and execution facts:

- execution traces;
- evidence records;
- provenance records;
- structured execution events;
- reliability-store boundary;
- observability foundation;
- harness foundation;
- retrospective foundation;
- monitoring foundation.

Reliability facts are structured data, not an agent's self-description.

## Phase 56 — Reliability Replay / Deterministic Harness

Established deterministic scenario execution and replay:

- `HarnessCase`;
- `ScenarioCatalog`;
- `HarnessEngine.run_case()`;
- `HarnessEngine.replay()`;
- `HarnessEngine.replay_all()`;
- persisted execution traces;
- explicit response assertions.

## Phase 57 — Durable Reliability Persistence

Extended the reliability layer with durable storage and clarified the boundary between in-memory testing and persisted execution history.

## Phase 58 — Reliability Evaluation

Established evaluation as a first-class layer over execution facts, including the path toward metrics for retrieval, grounding, tool use, latency, cost, and recovery/failure behavior.

## Phase 59 — Scenario-Aware Evaluation

Extended evaluation so scenarios can assert not only the response but also retrieved evidence and scenario-specific expectations.

## Phase 60 — Reviewed Retrospective → Regression

Established the governance loop in which retrospective findings can become reviewed regression scenarios:

`execution → retrospective finding → review → regression scenario → replay`

## Phase 61 — Claim → Evidence Grounding

Established an explicit claim/evidence relationship layer for grounding evaluation.

`claim_coverage` is a deterministic relationship-coverage metric, not semantic entailment or an LLM judgement of truth.

## Phase 62 — Agent Architecture Benchmark

Established the controlled benchmark foundation for comparing architecture implementations under equivalent scenarios, evidence, tools, and evaluation rules.

## Phase 63 — Benchmark Dataset & Scenario Governance

Established durable, versionable scenario and benchmark fixture concepts for reproducible benchmark execution.

## Phase 64 — Benchmark Reporting & Comparison

Established deterministic benchmark reporting and explicit architecture-to-architecture comparison without hidden composite scoring.

## Phase 65 — Agent Observability Productization

Established a coherent operational trace surface over meaningful agent execution stages.

## Phase 66 — Agent Retrospective Engine

Established structured engineering findings over recorded execution facts.

## Phase 67 — Regression Promotion & Reliability Loop

Established the governed flow from execution findings to reviewed regression cases and replay.

---

# 4. Completed Application Integration Gates

## Phase 68 — Canonical Application Runtime

Finalized the canonical request boundary:

`request → normalization → capability decision → handler → evidence → response`

The runtime owns deterministic request normalization, capability selection, lifecycle instrumentation, evidence validation, and response shaping. Provider-specific implementations remain behind injected application contracts.

## Phase 69 — Document Ingestion → RAG Journey

Connected the canonical upload capability to the maintained uploaded-file indexer without creating a competing ingestion implementation.

The canonical boundary is:

`upload → validation → staging/processing → metadata → indexing → retrieval/evidence`

New, unchanged, and failed indexing outcomes remain distinguishable, and evidence is still created only from actual retrieval metadata rather than ingestion metadata.

## Phase 70 — Retrieval → Grounded Answer Boundary

Added the provider-neutral `RetrievalService` / `RetrievalResult` contract and routed the canonical question capability through it.

The maintained agent remains responsible for retrieval strategy, tools, reranking, graph-RAG behavior, model selection, and answer generation. Returned source metadata is normalized into `Evidence`; raw source content is not copied into evidence metadata. Answers without returned sources remain explicitly ungrounded.

## Phase 71 — Deterministic Upload → Index → Retrieve → Grounded Answer Journey

Proved the complete application RAG journey as a reusable deterministic harness scenario rather than as disconnected ingestion and retrieval tests.

The scenario binds an uploaded fixture to the later question step, requires returned source evidence for that artifact, validates relevance and grounding through the existing `ScenarioEvaluationEngine`, and confirms evidence/provenance survive the canonical runtime boundary.

### Exit criterion

A named scenario can deterministically exercise upload, indexing, retrieval, grounded answer generation, evidence handoff, and application observability through the existing harness and can be replayed as a future regression or architecture benchmark case.

## Phase 72 — Persistence & Conversation State

Finalized provider-neutral conversation and message contracts and integrated them into the canonical application runtime.

The persistence boundary is:

`request identity → conversation ownership → handler execution → successful turn persistence → history retrieval`

Implemented capabilities include:

- immutable `Conversation` and `ConversationMessage` contracts;
- `ConversationStore` provider boundary;
- deterministic `InMemoryConversationStore` for local tests;
- `ConversationService` application facade;
- `ChainlitConversationStore` adapter for the existing Chainlit-compatible data layers;
- canonical runtime persistence for successful question turns;
- explicit actor/session/conversation identity requirements;
- conversation identity on execution traces;
- durable JSONL preservation of conversation/session/actor identity;
- bounded history retrieval;
- actor/session isolation and duplicate message protection;
- explicit persistence failures rather than false-success responses.

The existing Azure Cosmos DB and MongoDB data layers remain the provider implementations. Phase 72 does not duplicate their SDK, indexing, partition, or connection behavior.

### Exit criterion

The canonical runtime can persist and retrieve conversation turns through a provider-neutral contract, existing Cosmos/Mongo data layers can be used through an adapter, actor/session isolation is enforced, execution traces retain conversation identity, and deterministic tests cover the persistence lifecycle.

## Phase 73 — Background Processing & Idempotency

Finalized the asynchronous ingestion boundary around stable artifact identities, task correlation, deterministic failure classification, compatibility-safe task payload handling, and explicit idempotency contracts.

Implemented capabilities include:

- immutable `ArtifactIdentity` and `BackgroundTask` contracts;
- deterministic artifact IDs derived from identity version, logical filename, and SHA-256 content checksum;
- operation-scoped idempotency keys;
- provider-neutral `BackgroundTaskStore` and `ArtifactIdempotencyStore` boundaries;
- deterministic in-memory stores for contract/local testing;
- deterministic retryable vs terminal failure classification;
- Celery task ID, optional run ID, and artifact ID correlation in worker telemetry;
- compatibility normalization for legacy `{"path": ...}` task payloads;
- validation that supplied artifact IDs match current file content;
- preservation of the maintained `tasks.index_files` task and `UserUploadedFileIndexer` implementation;
- explicit retention of no automatic Celery retries and no late acknowledgements until durable artifact-level concurrency semantics are demonstrated.

The maintained indexer's existing hash/version-aware unchanged-file behavior remains the canonical sequential idempotency mechanism. Phase 73 does not claim distributed concurrent-worker idempotency without a durable claim/lease implementation.

### Exit criterion

Background indexing has stable artifact identity, task/artifact correlation, deterministic failure classification, compatibility-safe payload handling, and explicit idempotency boundaries. Automatic retries remain gated until durable concurrent idempotency is demonstrated.

---

# 5. Remaining Application Completion Roadmap

## Phase 74 — Frontend / API Integration

Complete the real journey:

`open application → upload → ingestion status → ask → grounded response → inspect evidence → continue conversation`

The frontend/API must expose useful evidence and bounded errors rather than hiding execution state behind a final answer.

---

# 6. Enterprise & Operational Readiness

## Phase 75 — Security & Governance

Implement and test authentication, authorization/RBAC, tenant/user isolation where applicable, secret handling, upload validation, tool/input boundaries, PII-sensitive logging, audit events, and dependency/configuration hardening.

## Phase 76 — Production Observability & Operations

Extend the reliability model into production operations: health/readiness, metrics, alert adapters, trace retention, operational dashboards, failure triage, runbooks, and safe telemetry/data retention.

## Phase 77 — Deployment & Release Readiness

Validate Docker/runtime packaging, production configuration, Azure dependency mapping, startup/readiness, scaling assumptions, rollback, release validation, and the operational runbook.

GitHub Actions is **not** a required validation mechanism. Local deterministic validation and explicit cloud-integration validation remain authoritative.

---

# 7. Post-MVP Provider Expansion

Only after the core application + engineering feedback loop is reliable should provider expansion begin.

Potential extensions include:

- additional cloud storage providers;
- GCP/AWS/IBM/Oracle integrations;
- SharePoint/OneDrive;
- PostgreSQL/Oracle;
- additional search/vector providers;
- Salesforce/SAP/ServiceNow;
- enterprise SSO providers;
- specialized multi-agent architectures;
- advanced GraphRAG;
- Kubernetes/serverless variants.

Every provider follows:

**requirement → contract → implementation → deterministic tests → integration validation → benchmark scenario → documentation**.

Technology is not added merely because it is enterprise-branded.

---

# 8. Definition of Done

## Application

- [ ] User can ask questions through the maintained runtime.
- [ ] User can upload supported documents.
- [ ] Documents can be indexed and retrieved.
- [ ] Structured analysis is bounded and deterministic.
- [x] Conversation state works through the canonical persistence contract where configured.
- [ ] Frontend/API supports the complete user journey.

## Reliability

- [x] Every meaningful run has a trace.
- [x] Evidence and provenance survive the execution path.
- [x] Harness scenarios are replayable.
- [x] Retrospectives are generated from execution facts.
- [x] Reviewed findings can become regression scenarios.
- [x] Claim/evidence grounding is measurable.
- [x] Architecture variants can be benchmarked under equivalent conditions.
- [x] Benchmark results are reproducible and comparable.

## Safety & operations

- [x] No arbitrary remote code execution surface is reintroduced.
- [ ] Security boundaries are fully tested.
- [ ] Errors are explicit and diagnosable across all production paths.
- [ ] Production telemetry is safe and bounded.
- [ ] Deployment and rollback are documented.

---

# 9. Immediate Execution Order

The project continues from the **actual implemented frontier**, not from repository cleanup:

```text
55–67 Reliability / Benchmark Foundation
        ↓
68 Canonical Application Runtime                 ✓
        ↓
69 Document Ingestion → RAG Journey              ✓
        ↓
70 Retrieval → Grounded Answer Boundary          ✓
        ↓
71 Deterministic End-to-End RAG Journey          ✓
        ↓
72 Persistence & Conversation State              ✓
        ↓
73 Background Processing & Idempotency           ✓
        ↓
74 Frontend / API Integration                    ← NEXT
        ↓
75–77 Enterprise / Production Readiness
        ↓
Provider Expansion
```

## Immediate next task

**Phase 74 — Frontend / API Integration.**

The next gate should expose the proven application journey through the real frontend/API: upload, background ingestion status, grounded question answering, evidence inspection, and conversation continuation. It should build on the canonical runtime, conversation persistence, and background task boundaries rather than introducing another application path.
