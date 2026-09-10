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

The container uses the same commands. No alternate frontend launcher is introduced.

## Container boundary

The repository now contains a minimal Python 3.12 container definition that:

- installs the package from `pyproject.toml`;
- runs as a non-root application user;
- exposes port `8000` for the Chainlit process;
- uses `agentic-rag --check` as the container healthcheck;
- keeps environment-specific credentials outside the image.

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

## Release sequence

1. Build the container from the intended commit.
2. Run `agentic-rag --check` in the release environment.
3. Start the container with production configuration supplied externally.
4. Verify liveness/readiness and the Chainlit endpoint.
5. Exercise a deterministic smoke path: authenticated question, supported upload, indexing submission/status, and conversation persistence where configured.
6. Inspect operational health, bounded metrics, alerts, and dashboard export.
7. Run the Phase 75 live ownership/security procedure against the target non-production environment before promotion.
8. Record the release commit, image digest, configuration version, and validation result.

## Rollback gate

Every release must retain the previous known-good image digest and configuration version. Rollback means restoring those immutable artifacts rather than rebuilding from a moving branch.

After rollback, repeat:

- startup check;
- liveness/readiness verification;
- authentication and ownership smoke test;
- one question path;
- one bounded upload/indexing path;
- operational dashboard/alert inspection.

## Scale assumptions

The application runtime remains stateless with respect to request execution. Durable conversation, background-task, audit, and other persistence are delegated to their existing provider boundaries. In-memory operational metrics are process-local and therefore are diagnostic/collection primitives, not a replacement for a durable external metrics backend.

Horizontal scaling must therefore preserve the existing durable provider contracts and use an external metrics/telemetry sink when aggregate fleet-wide observability is required.

## Live validation boundary

GitHub-only engineering cannot claim the actual cloud deployment is production-verified. The authoritative validation still requires real OAuth, Chainlit, Cosmos/data-layer, Azure, and deployment credentials in the target environment.
