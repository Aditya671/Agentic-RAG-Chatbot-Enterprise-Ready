# Agentic RAG — End-to-End Development Plan

**Status:** Active engineering roadmap  
**Current implemented frontier:** Phase 77 — Deployment & Release Readiness (deterministic release-validation evidence implemented; target-environment validation remains)  
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

## 2. Engineering Model

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

## 3. Completed Engineering Foundation

Phases 55–67 remain complete as previously documented: reliability contracts, deterministic replay, durable persistence, evaluation, scenario-aware evaluation, reviewed regression promotion, claim/evidence grounding, architecture benchmarking, benchmark governance/reporting, observability productization, retrospective analysis, and the reliability improvement loop.

## 4. Completed Application Integration Gates

Phases 68–74 remain complete as previously documented: canonical runtime, document ingestion, retrieval→grounded-answer boundary, end-to-end RAG journey, conversation persistence, background processing/idempotency, and frontend/API integration.

## 5. Enterprise & Operational Readiness

### Phase 75 — Security & Governance

**Implemented frontier.** The phase has deterministic implementation coverage across the planned security gates, with the remaining live authenticated ownership/security run reserved for the target deployment environment.

### Phase 76 — Production Observability & Operations

**Implementation frontier complete.** Phase 76 contains provider-neutral health/readiness, bounded telemetry and retention, canonical runtime metrics, deterministic alerting, failure triage, safe dashboard/export, and the production operational runbook.

### Phase 77 — Deployment & Release Readiness

**Current implementation frontier.** The repository now has:

- a Python 3.12 production container definition;
- a non-root container user and explicit deployment context exclusions;
- canonical `agentic-rag --frontend` launch behavior;
- deterministic `agentic-rag --check` startup diagnostics used for container health;
- deterministic `agentic-rag --preflight` release preflight checks for packaging assets, repository-local secret/config hygiene, and startup imports;
- external runtime configuration and secret handling rules;
- immutable `ReleaseManifest` identity containing release ID, exact source commit SHA, image digest, configuration version, and creation timestamp;
- deterministic validation of release-manifest identity fields without storing secrets or raw configuration values;
- immutable `ReleaseValidationReport` / `ValidationGate` contracts for recording target-environment promotion and rollback evidence with explicit `pass`, `fail`, `blocked`, or `not_run` states;
- deployment and rollback documentation requiring immutable image/configuration artifacts and validation evidence.

Remaining Phase 77 gates:

- build and execute the image in the target environment;
- validate startup/readiness and real Azure dependency configuration;
- execute the Phase 75 live authenticated actor/tenant ownership and security procedure;
- perform smoke validation through the real Chainlit/Cosmos/data-layer path;
- validate immutable release promotion and rollback in the target production-like environment;
- record deployment-specific telemetry/alert transport and release evidence.

GitHub Actions is **not** a required validation mechanism. Local deterministic validation and explicit cloud-integration validation remain authoritative.

## 6. Post-MVP Provider Expansion

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

## 7. Definition of Done

### Application

- [x] User can ask questions through the maintained runtime.
- [x] User can upload supported documents.
- [x] Documents can be indexed and retrieved.
- [x] Structured analysis is bounded and deterministic.
- [x] Conversation state works through the canonical persistence contract where configured.
- [x] Frontend/API supports the complete user journey.

### Reliability

- [x] Every meaningful run has a trace.
- [x] Evidence and provenance survive the execution path.
- [x] Harness scenarios are replayable.
- [x] Retrospectives are generated from execution facts.
- [x] Reviewed findings can become regression scenarios.
- [x] Claim/evidence grounding is measurable.
- [x] Architecture variants can be benchmarked under equivalent conditions.
- [x] Benchmark results are reproducible and comparable.

### Safety & operations

- [x] No arbitrary remote code execution surface is reintroduced.
- [x] Security implementation boundaries are deterministically tested.
- [x] Security audit persistence and retention are explicit and bounded.
- [x] Production telemetry contracts are safe and bounded.
- [x] Runtime request/error/duration telemetry is emitted at the canonical boundary when configured.
- [x] Deterministic alert thresholds exist over monitored health facts.
- [x] Operational failure triage is deterministic and linked to existing findings.
- [x] Operational runbook and escalation guidance are documented.
- [x] Safe dashboard/export contract exists without vendor lock-in.
- [x] Production packaging and canonical container startup are defined.
- [x] Immutable release identity contract exists for promotion/rollback evidence.
- [x] Deterministic release preflight gate exists and is exposed through the canonical CLI.
- [x] Deterministic release-validation evidence contract exists with explicit blocked/not-run states.
- [ ] Live authenticated identity/tenant ownership validation executed against the target cloud deployment.
- [ ] Deployment image built and executed in the target production-like environment.
- [ ] Azure/configuration dependency mapping validated with real deployment settings.
- [ ] Release promotion and rollback validated against immutable artifacts.

## 8. Immediate Execution Order

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
76 Production Observability & Operations         ✓* 
        ↓
77 Deployment & Release Readiness                ◐
        ↓
Provider Expansion
```

`*` Source implementation and deterministic validation are complete; production-like live validation remains environment-gated.

## Immediate next task

**Phase 77 — Target-Environment Validation & Release Closure.**

Execute the existing preflight/container/startup path against the target non-production environment, validate real Azure and persistence dependencies, run the outstanding Phase 75 authenticated security procedure, exercise smoke and rollback paths, and record immutable `ReleaseManifest` plus `ReleaseValidationReport` evidence. Once those gates pass, the project reaches its production-release closure boundary before any post-MVP provider expansion.
