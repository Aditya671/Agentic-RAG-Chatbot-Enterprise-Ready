# Phase 77 — Deployment & Release Readiness

## Purpose

Define the production packaging and release gates without introducing a second application startup path or embedding secrets in the image.

## Canonical process

The maintained user-facing process is the packaged `agentic-rag` CLI with the existing Chainlit frontend:

```text
agentic-rag --frontend
```

The deterministic startup diagnostic is:

```text
agentic-rag --check
```

The deterministic release preflight is:

```text
agentic-rag --preflight
```

The container uses the same startup commands. No alternate frontend launcher is introduced.

## Container boundary

The repository now contains a minimal Python 3.12 container definition that:

- installs the package from `pyproject.toml`;
- runs as a non-root application user;
- exposes port `8000` for the Chainlit process;
- uses `agentic-rag --check` as the container healthcheck;
- keeps environment-specific credentials outside the image context.

`.dockerignore` excludes local environments, `.env`, `config.yml`, secret material, logs, and build/test artifacts from the image context.

## Configuration gate

Production configuration must be injected at runtime using the existing configuration loader and provider boundaries. Do not commit or bake into the image:

- OAuth client secrets or tokens;
- Azure credentials;
- database connection strings;
- API keys;
- private certificates;
- environment-specific `config.yml`.

The existing configuration validation remains authoritative for required index/LLM mappings and Azure Key Vault settings.

## Release preflight gate

Before building or promoting a release candidate, run:

```text
agentic-rag --preflight
```

This deterministic, cloud-free check verifies:

- required packaging assets are present;
- repository-local secret/config files are absent from the release tree;
- the existing startup import checks pass.

A failed preflight blocks promotion. The command does not contact Azure, OAuth, Cosmos, Chainlit, or any other external service.

## Release identity gate

Every promotion must produce an immutable `ReleaseManifest` containing:

- release identifier;
- exact 40-character source commit SHA;
- immutable container image SHA-256 digest;
- configuration version identifier;
- creation timestamp.

The manifest contains release identity only. Secrets, tokens, credentials, and raw configuration values are explicitly outside the contract.

Use the manifest as the handoff artifact between build, validation, promotion, and rollback. Do not identify a production release only by a mutable branch, tag, or floating image tag.

## Deterministic validation evidence

Target-environment validation results should be captured as a `ReleaseValidationReport` containing:

- the release identifier and exact source commit SHA;
- one bounded `ValidationGate` for each required release gate;
- one of `pass`, `fail`, `blocked`, or `not_run` for every gate;
- bounded operator detail only.

A report is eligible for promotion only when every recorded gate is `pass`. A `blocked` or `not_run` gate is never treated as an implicit success. The validation contract stores no credentials, tokens, prompts, request payloads, or raw cloud configuration values.

## Release sequence

1. Run `agentic-rag --preflight` on the intended release checkout.
2. Build the container from the intended commit.
3. Create and validate the immutable `ReleaseManifest` for that build.
4. Run `agentic-rag --check` in the release environment.
5. Start the container with production configuration supplied externally.
6. Verify liveness/readiness and the Chainlit endpoint.
7. Exercise a deterministic smoke path: authenticated question, supported upload, indexing submission/status, and conversation persistence where configured.
8. Inspect operational health, bounded metrics, alerts, and dashboard export.
9. Run the Phase 75 live ownership/security procedure against the target non-production environment before promotion.
10. Record the `ReleaseValidationReport`, validated release manifest, image digest, configuration version, and validation outcome.

## Rollback gate

Every release must retain the previous known-good `ReleaseManifest` and its corresponding validation report. Rollback means restoring that manifest's immutable image digest and configuration version rather than rebuilding from a moving branch.

After rollback, repeat:

- release preflight;
- startup check;
- liveness/readiness verification;
- authentication and ownership smoke test;
- one question path;
- one bounded upload/indexing path;
- operational dashboard/alert inspection;
- release-validation recording.

## Scale assumptions

The application runtime remains stateless with respect to request execution. Durable conversation, background-task, audit, and other persistence are delegated to their existing provider boundaries. In-memory operational metrics are process-local and therefore are diagnostic/collection primitives, not a replacement for a durable external metrics backend.

Horizontal scaling must therefore preserve the existing durable provider contracts and use an external metrics/telemetry sink when aggregate fleet-wide observability is required.

## Live validation boundary

GitHub-only engineering cannot claim the actual cloud deployment is production-verified. The authoritative validation still requires real OAuth, Chainlit, Cosmos/data-layer, Azure, and deployment credentials in the target environment.
