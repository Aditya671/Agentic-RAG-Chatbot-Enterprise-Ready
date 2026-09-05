# Agentic RAG — End-to-End Development Plan

**Status:** Active engineering roadmap  
**Current implemented frontier:** Phase 62 — Agent Architecture Benchmark foundation  
**Current work:** Phase 63 — Benchmark Dataset & Scenario Governance  
**Primary goal:** Build a complete Agentic RAG application together with the engineering system required to observe, replay, evaluate, benchmark, and improve it.

> This roadmap supersedes the previous application-only phase sequence. The repository has already progressed beyond basic runtime hardening: it now contains a reliability foundation, observability, provenance, harness/replay, retrospective analysis, scenario-aware evaluation, regression promotion, durable reliability storage, claim/evidence grounding, and a controlled architecture-benchmark foundation. Future work must build on those capabilities rather than restarting the project from application plumbing.

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

## Phase 62 — Agent Architecture Benchmark Foundation

Established a provider-neutral benchmark harness for comparing pluggable architecture adapters under the same scenario and evidence boundary.

The foundation captures comparable execution facts including:

- task/pass result;
- grounding and retrieval metrics;
- latency;
- model/tool/retrieval call counts;
- optional token and cost telemetry;
- provenance completeness;
- response fingerprints for repeatability;
- explicit evidence-boundary validation.

Architecture complexity is not treated as a quality score, and the benchmark does not invent a hidden composite winner.

This is the current implemented frontier.

---

# 4. Next Engineering Roadmap

## Phase 63 — Benchmark Dataset & Scenario Governance

**Objective:** Make benchmark scenarios a durable engineering asset rather than ad-hoc test code.

### Work

- versioned scenario definitions;
- scenario metadata and expected capabilities;
- immutable evidence fixtures;
- expected claims/evidence relationships;
- difficulty categories;
- failure/recovery scenarios;
- deterministic fixture isolation;
- scenario/version history through immutable identities;
- benchmark configuration identity;
- a self-contained dataset boundary tying scenarios to their fixtures.

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

### Work

- failure clustering;
- repeated tool/retrieval inefficiency detection;
- grounding failure analysis;
- latency/cost regression detection;
- recovery-path analysis;
- candidate regression generation;
- confidence and evidence attached to findings.

### Exit criteria

A failed or degraded run can produce an actionable, evidence-backed engineering finding without requiring an LLM to invent the failure reason.

---

## Phase 67 — Regression Promotion & Reliability Loop

**Objective:** Close the loop between benchmark/retrospective findings and future runtime changes.

### Flow

`run → observe → evaluate → benchmark → retrospect → propose → review → promote → replay`

### Exit criteria

A reviewed reliability finding can become a durable regression scenario and is automatically available to future replay/benchmark runs.

---

## Phase 68 — Complete the Real Agentic RAG Application

Only after the engineering loop is sufficiently stable should the application surface be completed as the canonical end-to-end product.

### Target flow

`question/upload → intent → retrieval/tool selection → bounded execution → evidence → grounded response → persistence`

The application must emit the same reliability contracts already established by the engineering system.

---

## Phase 69 — Production-Grade Retrieval & Indexing

Harden the retrieval/indexing path as a production subsystem rather than a demo integration.

### Work

- ingestion lifecycle;
- incremental updates;
- deterministic indexing behavior;
- retrieval diagnostics;
- metadata filtering;
- failure isolation;
- provenance preservation;
- benchmark coverage for retrieval quality.

---

## Phase 70 — Agent Tool Governance

Define explicit contracts around tools:

- capability registration;
- input validation;
- authorization boundaries;
- timeout/error behavior;
- deterministic tool telemetry;
- tool-selection evaluation;
- safe failure handling.

The agent should never gain capabilities merely because a library exposes them.

---

## Phase 71 — Multi-Provider Runtime Contracts

Only after the core architecture and benchmark system are stable should provider expansion be treated as a first-class concern.

### Principle

`requirement → contract → implementation → deterministic tests → integration validation → benchmark scenario → documentation`

Provider expansion must not become speculative abstraction work.

---

## Phase 72 — Security & Data Governance

Harden the system around:

- credential boundaries;
- tenant/data isolation;
- upload validation;
- prompt/input safety;
- output handling;
- provenance and auditability;
- secret-safe telemetry;
- retention/deletion behavior.

---

## Phase 73 — Application UX / API Surface

Complete the user-facing interfaces around the already-established backend contracts.

### Possible surfaces

- API endpoints;
- chat UI;
- upload workflow;
- execution history;
- evidence/provenance inspection;
- evaluation/benchmark views.

The interface must expose reliable system behavior rather than hide it.

---

## Phase 74 — Production Operations

Introduce the operational capabilities required for real deployments:

- deployment topology;
- configuration management;
- health/readiness checks;
- structured logging;
- alerting;
- capacity planning;
- failure recovery;
- operational runbooks.

---

## Phase 75 — Performance & Cost Engineering

Optimize only after benchmark evidence identifies meaningful bottlenecks.

### Measure before changing

- retrieval latency;
- model latency;
- token consumption;
- tool overhead;
- storage/query cost;
- concurrency behavior.

Optimization must be tied to measured regressions or bottlenecks, not intuition.

---

## Phase 76 — Enterprise Readiness

Final hardening for broader adoption:

- tenancy model;
- RBAC/authorization;
- auditability;
- compliance controls;
- data lifecycle;
- observability;
- reliability SLOs;
- disaster recovery;
- documented extension points.

---

# 5. Engineering Rules

These rules govern future phases.

## Rule 1 — Evidence Before Claims

Do not declare an architecture improvement without benchmark or execution evidence.

## Rule 2 — Same Inputs, Fair Comparison

Architecture comparisons must use the same scenario, evidence, tool availability, and evaluation rules.

## Rule 3 — Deterministic Facts First

Metrics should be derived from execution facts wherever possible. Do not ask an LLM to grade the system when a deterministic assertion can answer the question.

## Rule 4 — Complexity Is Not Quality

A multi-agent architecture is not inherently better than a direct retrieval pipeline.

## Rule 5 — Preserve Provenance

A useful answer without an inspectable evidence path is incomplete for this project.

## Rule 6 — Make Failure Reproducible

A reliability issue should become a scenario that can be replayed.

## Rule 7 — Review Before Promotion

Retrospective findings may propose regressions, but promotion into the durable benchmark/regression set is a reviewed action.

## Rule 8 — No Speculative Provider Expansion

Do not add providers or abstraction layers without a demonstrated requirement.

## Rule 9 — No Arbitrary Remote Code Execution

The retired code-interpreter path remains a deliberate safety boundary. Do not reintroduce arbitrary remote execution as a benchmark or application capability.

## Rule 10 — No Hidden Composite Score

Benchmark reporting may present multiple metrics and trade-offs. Do not collapse architecture quality into an unexplained scalar winner.

## Rule 11 — Version Benchmark Assets

Scenario definitions, evidence fixtures, and benchmark configurations are engineering inputs. Changes to them must be explicit and versioned so historical comparisons remain meaningful.

---

# 6. Definition of Done

The project is not complete merely because an agent answers a question.

A mature implementation should make it possible to answer:

1. What did the agent do?
2. Why did it do it?
3. What evidence did it use?
4. Which claims are grounded in that evidence?
5. What failed or degraded?
6. Can the run be replayed?
7. Can competing architectures be compared fairly?
8. Did a change improve reliability or merely increase complexity?
9. Can the finding become a reviewed regression?
10. Can the complete application operate on top of the same reliability contracts?

That is the engineering target for the repository.
