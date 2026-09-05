# Agentic RAG — End-to-End Development Plan

**Status:** Active engineering roadmap  
**Current implemented frontier:** Phase 61 — Claim → Evidence Grounding  
**Primary goal:** Build a complete Agentic RAG application together with the engineering system required to observe, replay, evaluate, benchmark, and improve it.

> This roadmap supersedes the previous application-only phase sequence. The repository has already progressed beyond basic runtime hardening: it now contains a reliability foundation, observability, provenance, harness/replay, retrospective analysis, scenario-aware evaluation, regression promotion, durable reliability storage, and claim/evidence grounding. Future work must build on those capabilities rather than restarting the project from application plumbing.

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

This is the current implemented frontier.

---

# 4. Next Engineering Roadmap

## Phase 62 — Agent Architecture Benchmark

**Objective:** Turn the existing harness and evaluation system into a controlled framework for comparing agent architectures.

The benchmark must compare architectures under the **same scenario, evidence, tool availability, and evaluation rules**.

### Benchmark dimensions

- task success;
- response correctness;
- claim/evidence coverage;
- retrieval quality;
- unnecessary retrieval/tool activity;
- tool selection and execution;
- failure classification;
- recovery behavior;
- latency;
- token/model cost where measurable;
- number of model calls;
- determinism/repeatability;
- provenance completeness.

### Architecture variants

The benchmark should support pluggable architectures such as:

1. direct RAG;
2. tool-aware agent;
3. retrieval-first agent;
4. planner/executor architecture;
5. multi-step agentic RAG;
6. future specialized/multi-agent variants.

Complexity must not be treated as quality.

### Exit criteria

Given the same scenario catalog, multiple architecture implementations can run and produce comparable records containing metrics, evidence, trace/provenance, failures, and configuration identity.

---

## Phase 63 — Benchmark Dataset & Scenario Governance

**Objective:** Make benchmark scenarios a durable engineering asset rather than ad-hoc test code.

### Work

- versioned scenario definitions;
- scenario metadata and expected capabilities;
- evidence fixtures;
- expected claims/evidence relationships;
- difficulty categories;
- failure/recovery scenarios;
- deterministic fixture isolation;
- scenario/version history;
- benchmark configuration identity.

### Exit criteria

A benchmark run can be reproduced from a named scenario/version and configuration without undocumented local state.

---

## Phase 64 — Benchmark Reporting & Comparison

**Objective:** Make architecture comparisons understandable to engineers.

### Outputs

- per-scenario results;
- aggregate metrics;
- pass/fail summaries;
- evidence/grounding results;
- latency/cost summaries;
- failure taxonomy;
- provenance completeness;
- architecture-to-architecture comparison;
- regression deltas against a baseline.

Reports should explain **why** behavior changed, not merely declare a winner.

---

## Phase 65 — Agent Observability Productization

**Objective:** Move observability from a developer utility into a coherent operational capability.

### Minimum trace

`request → session/user → agent decision → tool call → retrieval → evidence → model call → response → outcome`

### Work

- stable request/run identifiers;
- structured lifecycle events;
- tool-call records;
- retrieval diagnostics;
- model-call metadata;
- evidence/provenance linkage;
- latency/error measurements;
- safe telemetry boundaries;
- trace querying/filtering;
- operational health summaries.

### Exit criteria

An engineer can inspect a run and identify where behavior diverged from the intended execution path without reconstructing it from raw logs.

---

## Phase 66 — Agent Retrospective Engine

**Objective:** Convert observed execution facts into actionable engineering findings.

The retrospective engine reasons over recorded facts, not an agent's self-grade.

### Finding categories

- retrieval weakness;
- missing evidence;
- unsupported claim;
- unnecessary tool call;
- incorrect tool selection;
- excessive model calls;
- latency bottleneck;
- failure/recovery problem;
- provenance gap;
- scenario regression;
- configuration anomaly.

### Output

`execution facts → observations → findings → severity/confidence → recommended action`

### Exit criteria

A completed run can produce a structured retrospective whose findings can be reviewed and, when appropriate, promoted into regression scenarios.

---

## Phase 67 — Regression Promotion & Reliability Loop

**Objective:** Close the engineering feedback loop.

### Flow

`run → observe → retrospect → review → promote → replay → compare`

### Exit criteria

A known failure can become a deterministic regression case and be compared against later implementations through the harness.

---

# 5. Application Completion Roadmap

The engineering layer must eventually exercise the real application rather than only synthetic components.

## Phase 68 — Canonical Application Runtime

Finalize:

`user request → normalization → capability decision → retrieval/tool execution → evidence → response`

Requirements:

- one canonical agent construction path;
- explicit tool contracts;
- bounded retrieval configuration;
- provider boundaries;
- explicit failures;
- provenance preserved through runtime;
- observability emitted for meaningful execution stages.

## Phase 69 — Document Ingestion → RAG Journey

Complete:

`upload → validation → staging → extraction → chunking → metadata → indexing → retrieval → grounded answer`

Requirements include supported formats, stable identifiers, duplicate semantics, visible indexing failures, preserved source metadata, deterministic fixtures, and response-linked evidence.

## Phase 70 — Structured Data Analysis

Support bounded CSV/data analysis without arbitrary code execution.

Requirements include deterministic operations, schema validation, filters/aggregations, numeric validation, unsupported-operation behavior, reproducible results, and harness scenarios.

The retired E2B/code-interpreter surface and PandasAI-style arbitrary execution must remain retired.

## Phase 71 — Persistence & Conversation State

Finalize conversation/message contracts, Cosmos DB and MongoDB boundaries where used, serialization, lifecycle operations, provider failure handling, user/session isolation, and persistence scenarios in the harness.

## Phase 72 — Background Processing & Idempotency

Finalize asynchronous ingestion around stable artifact identities, duplicate protection, retryable vs terminal failures, task observability, and upload → task → indexing correlation.

**Celery retries remain disabled until artifact-level idempotency is demonstrated.**

## Phase 73 — Frontend / API Integration

Complete the real journey:

`open application → upload → ingestion status → ask → grounded response → inspect evidence → continue conversation`

The frontend/API must expose useful evidence and bounded errors rather than hiding execution state behind a final answer.

---

# 6. Enterprise & Operational Readiness

## Phase 74 — Security & Governance

Implement and test authentication, authorization/RBAC, tenant/user isolation where applicable, secret handling, upload validation, tool/input boundaries, PII-sensitive logging, audit events, and dependency/configuration hardening.

## Phase 75 — Production Observability & Operations

Extend the reliability model into production operations: health/readiness, metrics, alert adapters, trace retention, operational dashboards, failure triage, runbooks, and safe telemetry/data retention.

## Phase 76 — Deployment & Release Readiness

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
- [ ] Conversation state works where enabled.
- [ ] Frontend/API supports the complete user journey.

## Reliability

- [ ] Every meaningful run has a trace.
- [ ] Evidence and provenance survive the execution path.
- [ ] Harness scenarios are replayable.
- [ ] Retrospectives are generated from execution facts.
- [ ] Reviewed findings can become regression scenarios.
- [ ] Claim/evidence grounding is measurable.
- [ ] Architecture variants can be benchmarked under equivalent conditions.
- [ ] Benchmark results are reproducible and comparable.

## Safety & operations

- [ ] No arbitrary remote code execution surface is reintroduced.
- [ ] Security boundaries are tested.
- [ ] Errors are explicit and diagnosable.
- [ ] Production telemetry is safe and bounded.
- [ ] Deployment and rollback are documented.

---

# 9. Immediate Execution Order

The project continues from the **actual implemented frontier**, not from repository cleanup:

```text
55 Reliability Foundation
        ↓
56 Harness + Replay
        ↓
57 Durable Reliability
        ↓
58 Evaluation
        ↓
59 Scenario-aware Evaluation
        ↓
60 Reviewed Retrospective → Regression
        ↓
61 Claim → Evidence Grounding
        ↓
62 Architecture Benchmark        ← NEXT
        ↓
63 Scenario / Benchmark Governance
        ↓
64 Benchmark Reporting
        ↓
65 Observability Productization
        ↓
66 Retrospective Engine
        ↓
67 Regression / Reliability Loop
        ↓
68–73 Complete Real Application Journey
        ↓
74–76 Enterprise / Production Readiness
        ↓
Provider Expansion
```

## Immediate next task

**Phase 62 — Agent Architecture Benchmark.**

Do not begin by adding another cloud provider or rewriting the application. First use the existing harness, observability, provenance, retrospective, evaluation, and claim/evidence contracts to create a controlled architecture-comparison framework.

The benchmark should answer:

> **Given the same problem and the same evidence, which agent architecture performs better, why, and what does it cost in reliability, latency, complexity, and execution?**
