# Agentic-RAG-Chatbot-Enterprise-Ready

An enterprise-oriented Agentic RAG application and agent-engineering workbench focused on **grounded answers, deterministic tool execution, evidence provenance, and measurable reliability**.

## What the project contains

### Agentic RAG application
- conversational interaction through the maintained frontend;
- document upload and indexing;
- Azure AI Search / LlamaIndex retrieval boundaries;
- structured CSV analysis through bounded deterministic operations;
- persistent conversation/data-layer integrations where configured;
- Azure-aware credential and provider boundaries.

### Agent engineering layer
The repository goes beyond a basic chatbot by treating every agent run as an engineering artifact:

```text
Request
  ↓
Agent execution
  ↓
Observability + Provenance
  ↓
Harness / Replay
  ↓
Evaluation
  ↓
Retrospective
  ↓
Reviewed Regression
  ↓
Claim → Evidence Grounding
```

The current implemented reliability frontier is **Phase 61 — Claim → Evidence Grounding**. The next planned capability is **Phase 62 — Agent Architecture Benchmark**, which will use controlled scenarios to compare agent architectures on answer quality, evidence quality, tool behavior, latency, cost, and failure handling.

## Reliability capabilities

The maintained reliability package includes:

- execution traces;
- evidence and provenance contracts;
- agent observability;
- deterministic scenario harnesses;
- replay support;
- retrospective analysis;
- scenario-aware evaluation;
- regression promotion;
- durable reliability storage;
- claim/evidence grounding evaluation.

These components are designed to remain provider-neutral and testable without requiring live cloud services.

## Engineering principles

1. **Evidence before confidence.** Answers should expose what supports them and where evidence is missing.
2. **Deterministic software before AI.** Use ordinary application logic for validation, filtering, calculations, persistence, and security boundaries.
3. **One canonical implementation.** Historical migration copies are not production runtime surfaces.
4. **Observable by design.** Agent decisions, retrieval, tools, evidence, failures, and outcomes should be diagnosable.
5. **Reproducible evaluation.** Known scenarios should be replayable so architectural changes can be compared rather than guessed at.
6. **No arbitrary code execution.** The retired remote sandbox/code-interpreter capability remains out of scope.
7. **Provider boundaries.** Cloud SDKs and infrastructure integrations stay behind explicit application contracts.

## Development roadmap

The authoritative roadmap is [`docs/PLAN.md`](docs/PLAN.md).

The current direction is:

```text
Phase 55–61  Reliability / Evidence Foundation   ✓
Phase 62     Agent Architecture Benchmark        →
Phase 63+    Benchmark governance + reporting
Phase 68+    Complete and harden the application
Later        Enterprise/provider extensions
```

## Validation

GitHub Actions is not used as the project's validation mechanism. Validation is based on local deterministic tests, contract tests, mocked integrations, static/import checks, and separately executed live-cloud integration checks where the required services and credentials exist.

Cloud-backed behavior is not considered production-verified solely because a dependency-isolated test passes.

## Security boundary

Retrieved documents, uploaded files, web results, and tool outputs are treated as **data**, not as trusted instructions. Tool execution and structured analysis must remain explicitly bounded by application contracts.

See [`docs/code-execution-retirement.md`](docs/code-execution-retirement.md) for the retired arbitrary-code-execution boundary.
