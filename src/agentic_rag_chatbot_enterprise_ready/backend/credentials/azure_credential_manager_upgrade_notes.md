# AzureCredentialManager — Upgrade & Regression Notes

## Source

Original uploaded module: `azure_credential_manager.py`.

## Major fixes

1. Centralized and explicit credential selection.
2. Preserved local Azure CLI behavior for backward compatibility.
3. Added an opt-in path to use the current developer-optimized `DefaultAzureCredential` locally.
4. Production/cloud environments use `DefaultAzureCredential`.
5. Added Key Vault URL validation.
6. Added secret-name validation before network access.
7. Added typed `SecretNotFoundError`.
8. Preserved environment-variable-first behavior, but made it configurable.
9. Added bounded in-process secret caching to reduce repeated Key Vault calls.
10. Added explicit cache invalidation.
11. Added optional secret retrieval (`required=False`).
12. Avoided logging secret values.
13. Added Azure error translation while preserving the original exception as the cause.
14. Added resource cleanup through `close()`.
15. Added dependency injection for credentials and SecretClient, making tests network-free.
16. Added type annotations and structured logging.

## Current package baseline verified from public sources

- `azure-identity` stable: 1.25.3.
- `azure-keyvault-secrets` stable: 4.11.0.
- `azure-identity` 1.26.x was still prerelease in the public release history checked for this upgrade, so the stable line was used rather than a beta.
- Key Vault Secrets 4.11.0 uses Key Vault service API version 2025-07-01 by default.

## Authentication decision

The original module explicitly chose `AzureCliCredential` for local environments. That behavior is retained by default.

Current Microsoft guidance says teams using multiple development tools should prefer a developer-optimized `DefaultAzureCredential`; therefore the upgraded manager exposes:

```python
AzureCredentialManager.get_credential(
    environment="local",
    use_cli_for_local=False,
)
```

or the equivalent constructor option.

For production, `DefaultAzureCredential` is used so managed identity/environment/workload credentials can be discovered without embedding credentials in code.

## Regression suite

20 tests cover:

- environment precedence
- environment override control
- Key Vault retrieval
- caching
- cache invalidation
- cache expiry
- optional/required secrets
- invalid secret names
- Key Vault URL validation
- local CLI credential selection
- local DefaultAzureCredential selection
- production DefaultAzureCredential selection
- credential injection
- client lifecycle
- no-Key-Vault behavior
- per-call cache control
- invalid cache configuration

Run:

```bash
pytest -q test_azure_credential_manager.py
```

## Repository-level follow-up

When the full application repository is available, integration tests should verify:

- Key Vault RBAC permissions
- Managed Identity authentication
- Azure CLI authentication
- secret rotation behavior
- cache behavior during rotation
- multi-tenant access requirements
- Key Vault throttling/retry behavior
- application startup with unavailable Key Vault
- application startup with missing required secrets
- secret access metrics without secret-value logging
