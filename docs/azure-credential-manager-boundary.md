# Azure credential manager boundary

`backend.credentials.azure_credential_manager` is the canonical Azure authentication and Key Vault secret-access implementation.

## Ownership

The canonical module owns:

- environment-aware Azure credential selection;
- local Azure CLI credential support;
- cloud `DefaultAzureCredential` support;
- Azure Key Vault client construction;
- environment-first secret resolution;
- required versus optional secret semantics;
- bounded local secret caching;
- explicit client and credential cleanup.

The historical `azure_credential_manager_upgraded.py` implementation is removed. New application code must import the canonical module instead of depending on an `upgraded` path.

## Compatibility boundary

This migration is intentionally an ownership cleanup. It preserves the public `AzureCredentialManager` class and its supported constructor/method behavior while removing the duplicate implementation path.

## Verification boundary

The maintained regression suite exercises the canonical file directly with dependency-isolated Azure SDK stubs. Tests do not require Azure credentials, a live Key Vault, or network access.

Live identity configuration, Key Vault permissions, secret rotation, and production cache policy remain deployment-level concerns.
