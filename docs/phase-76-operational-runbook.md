# Phase 76 — Production Operational Runbook

## Purpose

Use the existing health, metrics, alerts, triage, and retrospective contracts to diagnose production behavior without inspecting or exporting prompts, request payloads, tokens, raw claims, or tenant-scoped user content.

## 1. First response

1. Check liveness/readiness. If readiness is failing, inspect the named dependency check and its bounded status/detail.
2. Inspect the current operational dashboard export for health, bounded metrics, active alerts, and triage priority.
3. Identify whether the condition is execution reliability, evidence/grounding, retrieval, response, or dependency related.
4. Prefer deterministic evidence already recorded by the runtime before changing configuration or code.

## 2. Alert handling

- **Critical:** treat as an operator-impacting condition. Confirm scope, preserve the current evidence/trace identifiers needed for internal investigation, and follow the applicable service escalation policy.
- **Warning:** investigate during the normal operational window and confirm whether the condition is transient or persistent.
- **Healthy:** no operational action is required solely from the alert evaluator.

The alert engine is a decision layer only; notification transport and paging remain deployment-specific.

## 3. Failure triage

Use the `FailureTriageEngine` output together with the corresponding retrospective finding. Do not infer root cause from an alert alone.

For infrastructure failures classified as retryable, verify dependency availability and idempotency before retrying. For terminal input/configuration failures, correct the invalid input or configuration rather than repeatedly retrying.

## 4. Safe dashboard/export rules

The operational dashboard is read-only and bounded. Export only aggregate health, bounded metrics, alert records, and sanitized triage summaries. Never add actor, session, tenant, prompt, token, raw claim, or request-content labels to exported metrics.

Do not turn the dashboard contract into a raw trace browser. Detailed traces remain behind the existing authenticated observability boundary.

## 5. Phase 75 live-validation handoff

When validating the production-like deployment, execute the previously defined authenticated ownership procedure:

1. deploy the current `main` build to the target non-production environment;
2. authenticate through the configured OAuth provider;
3. verify only non-secret identity/tenant/role metadata persists;
4. verify same-tenant ownership for conversation read/append/delete;
5. verify cross-actor or cross-tenant access is denied;
6. inspect actual Chainlit/Cosmos records;
7. confirm security audit records remain bounded and free of secrets.

This GitHub-only workflow does not claim that live cloud validation has been executed.

## 6. Escalation and recovery

Record the operational condition using the bounded alert/triage identifiers and relevant run identifiers already present in the internal telemetry system. Avoid copying request content into tickets or chat channels.

Before rollback, determine whether the issue is caused by application code, dependency availability, configuration, or data/input shape. For a code release regression, use the repository's existing regression/replay tooling to reproduce the behavior where practical before promoting a fix.

If rollback is required, follow the deployment artifact and rollback procedure established by Phase 77. Phase 76 does not invent a deployment mechanism.

## 7. Completion criteria

An incident is considered operationally stabilized when health/readiness is restored, active critical alerts clear, the failure condition is classified, and the resulting corrective action is captured without sensitive payloads.
