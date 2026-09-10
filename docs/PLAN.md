# Agentic RAG — End-to-End Development Plan

**Status:** Active engineering roadmap  
**Current implemented frontier:** Phase 75 — Security & Governance (implemented; live cloud validation remains environment-gated)  
**Primary goal:** Build a complete Agentic RAG application together with the engineering system required to observe, replay, evaluate, benchmark, and improve it.

> This roadmap supersedes the previous application-only phase sequence. The repository has progressed beyond basic runtime hardening: it now contains a reliability foundation, observability, provenance, harness/replay, retrospective analysis, scenario-aware evaluation, regression promotion, durable reliability storage, claim/evidence grounding, a canonical application runtime, canonical document ingestion, a retrieval-to-grounded-answer boundary, an end-to-end RAG scenario, provider-neutral conversation persistence, a background processing/idempotency boundary, the client-facing application surface, and the Phase 75 security/governance enforcement layers.

---

# 1. What We Are Building

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

Phases 55–67 remain complete as previously documented: reliability contracts, deterministic replay, durable persistence, evaluation, scenario-aware evaluation, reviewed regression promotion, claim/evidence grounding, architecture benchmarking, benchmark governance/reporting, observability productization, retrospective analysis, and the reliability improvement loop.

---

# 4. Completed Application Integration Gates

Phases 68–74 remain complete as previously documented: canonical runtime, document ingestion, retrieval→grounded-answer boundary, end-to-end RAG journey, conversation persistence, background processing/idempotency, and frontend/API integration.

---

# 5. Enterprise & Operational Readiness

## Phase 75 — Security & Governance

**Implemented frontier.** The phase now has deterministic implementation coverage across all planned security gates:

- provider-neutral `SecurityPrincipal` and deterministic capability authorization;
- authenticated actor/session requirements for protected runtime execution;
- bounded upload validation including extension, byte-content, size, and basename/path-component checks;
- tenant-aware conversation ownership across provider-neutral and Chainlit persistence boundaries;
- explicit tenant/role propagation through the application surface and runtime;
- provider-neutral authenticated context extraction containing only actor, tenant, and role attributes;
- live OAuth secret minimization at the maintained Chainlit boundary: access tokens, ID tokens, and raw claims are not persisted in user metadata;
- configurable deterministic RBAC policy with conservative built-in defaults and explicit capability-to-role validation;
- PII-bounded security authorization audit events with deterministic local sink support;
- durable JSONL security audit persistence with bounded recent reads, time-based retention, count-based retention, and atomic pruning;
- runtime configuration hardening for required index/LLM mappings and malformed entries;
- deterministic regression coverage for authorization, upload safety, tenant isolation, OAuth-secret resistance, RBAC, audit persistence, configuration hardening, and authenticated ownership propagation.

### Live validation boundary

The remaining Phase 75 verification is **environment-gated integration validation**, not another source-code implementation gate. The repository adapter already fails closed on actor and tenant ownership for existing Chainlit threads, including history and deletion, and the frontend propagates authenticated actor/tenant/roles through the canonical application surface. However, this GitHub engineering session does not have the deployment's real OAuth credentials, Chainlit runtime session, Cosmos database, or production data-layer endpoint, so it cannot honestly claim a live cloud-backed ownership run.

The authoritative live validation procedure is:

1. deploy the current `main` build into the target non-production environment;
2. authenticate through the configured OAuth provider;
3. verify the callback persists only `identifier`, `tenant_id`, and normalized `roles` (never access/ID tokens or raw claims);
4. create a conversation as actor A in tenant A;
5. verify actor A can read/append/delete only its own tenant-owned conversation;
6. verify actor B or tenant B receives an explicit ownership denial for the same thread;
7. inspect the actual Chainlit/Cosmos records and confirm tenant metadata and actor ownership match the authenticated context;
8. execute the security authorization paths and confirm durable audit records contain bounded identity/authorization facts only.

Phase 75 is therefore **code-complete and deterministic-test complete, with production-like live validation pending in the actual deployment environment**.

## Phase 76 — Production Observability & Operations

Extend the reliability model into production operations: health/readiness, metrics, alert adapters, trace retention, operational dashboards, failure triage, runbooks, and safe telemetry/data retention.

## Phase 77 — Deployment & Release Readiness

Validate Docker/runtime packaging, production configuration, Azure dependency mapping, startup/readiness, scaling assumptions, rollback, release validation, and the operational runbook.

GitHub Actions is **not** a required validation mechanism. Local deterministic validation and explicit cloud-integration validation remain authoritative.

---

# 6. Post-MVP Provider Expansion

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

# 7. Definition of Done

## Application

- [x] User can ask questions through the maintained runtime.
- [x] User can upload supported documents.
- [x] Documents can be indexed and retrieved.
- [x] Structured analysis is bounded and deterministic.
- [x] Conversation state works through the canonical persistence contract where configured.
- [x] Frontend/API supports the complete user journey.

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
- [x] Security implementation boundaries are deterministically tested.
- [x] Security audit persistence and retention are explicit and bounded.
- [ ] Live authenticated identity/tenant ownership validation executed against the target cloud deployment.
- [ ] Errors are explicit and diagnosable across all production paths.
- [ ] Production telemetry is safe and bounded.
- [ ] Deployment and rollback are documented.

---

# 8. Immediate Execution Order

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
74 Frontend / API Integration                    ✓
        ↓
75 Security & Governance                         ✓* 
        ↓
76 Production Observability & Operations
        ↓
77 Deployment & Release Readiness
        ↓
Provider Expansion
```

`*` Phase 75 source implementation and deterministic validation are complete; live authenticated cloud validation remains environment-gated and is not claimed from GitHub-only access.

## Immediate next task

**Phase 76 — Production Observability & Operations.**

Begin with health/readiness, production-safe metrics, bounded telemetry, operational trace retention, alerting adapters, and failure triage/runbooks, while carrying the Phase 75 live validation procedure into the deployment/release validation track.