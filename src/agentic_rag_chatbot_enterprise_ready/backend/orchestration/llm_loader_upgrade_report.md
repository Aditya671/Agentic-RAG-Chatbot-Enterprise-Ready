# `llm_loader.py` — Upgrade Report

## Sequential status

This is **File 4** in the requested one-file-at-a-time upgrade sequence.

Completed before this file:

1. `agentic_ai_system.py`
2. `code_interpreter.py`
3. `graph_rag.py`

This pass covers only `llm_loader.py` and its regression suite.

## Source findings

The original file had several correctness and maintainability problems:

- mutable default: `additional_kwargs = {}`
- `AzureAICompletionsModel` imported but unused
- `AzureADTokenProvider` imported only in commented code
- Key Vault was required even for Azure AD authentication
- `index_config.embed` was accessed before checking whether `index_config` existed
- `index_config.llms.get("aoai").get(...)` could fail with an opaque `AttributeError`
- Azure AD token provider was created even when API-key authentication was requested
- Azure API-key authentication was not actually implemented
- OpenAI authentication was hard-wired to a Key Vault lookup before checking the environment
- timeout and temperature were not validated
- caller-owned `additional_kwargs` could be shared/mutated
- Azure deployment name was assumed to equal model name
- embedding timeout was hard-coded to `10.0`
- exception messages did not distinguish configuration failures from SDK construction failures
- logging used the older f-string style and was not structured
- unnecessary imports increased coupling

The source confirms that the original loader always constructs `AzureCredentialManager`, then uses `DefaultAzureCredential` for Azure, while the OpenAI path reads `openai_api_key_name` from Key Vault or `OPENAI_API_KEY`. fileciteturn13file17

## Current dependency research

Fresh web verification found:

### LlamaIndex

Current `llama-index` release verified:

- **0.14.23**

PyPI shows 0.14.23 uploaded June 24, 2026. citeturn1search2

### OpenAI LlamaIndex integration

Current verified release:

- **llama-index-llms-openai 0.7.10**

The release history shows 0.7.10 on July 21, 2026. citeturn0search4

### Azure OpenAI LlamaIndex integration

Current verified release:

- **llama-index-llms-azure-openai 0.5.5**

PyPI shows 0.5.5 as the current release in the checked repository. citeturn2search1

### Azure OpenAI embedding integration

Current verified release:

- **llama-index-embeddings-azure-openai 0.5.2**

PyPI shows 0.5.2 as the current release. citeturn2search0

### OpenAI Python SDK

The current official OpenAI Python repository reports:

- **openai 2.45.0**

and documents Azure OpenAI authentication using Azure endpoints and Entra token providers. citeturn0search1

## Important compatibility decision

The application currently imports:

```python
from llama_index.llms.azure_openai import AzureOpenAI
from llama_index.embeddings.azure_openai import AzureOpenAIEmbedding
```

The upgraded file keeps these interfaces rather than prematurely moving the application to the lower-level OpenAI SDK.

Reason:

`llm_loader.py` is the application's provider adapter. Keeping the LlamaIndex LLM abstraction here means the rest of the application remains independent of the underlying OpenAI client.

The current LlamaIndex ecosystem explicitly separates core from provider integrations. citeturn1search2

## Authentication model

The upgraded loader supports two Azure modes.

### Azure + Microsoft Entra ID

Default:

```python
load_llm(
    ...,
    use_azure=True,
    azure_openai_use_azure_ad=True,
)
```

Uses:

```text
DefaultAzureCredential
        ↓
get_bearer_token_provider
        ↓
AzureOpenAI / AzureOpenAIEmbedding
```

This retains the application's managed-identity behavior.

### Azure + API key

Supported explicitly:

```python
load_llm(
    ...,
    use_azure=True,
    azure_openai_use_azure_ad=False,
)
```

Key resolution:

```text
Azure OpenAI Key Vault secret
        ↓
AZURE_OPENAI_API_KEY
```

The secret value is never logged.

## Non-Azure OpenAI

Supported:

```python
load_llm(
    ...,
    use_azure=False,
)
```

Authentication resolution:

```text
Key Vault secret
      ↓
OPENAI_API_KEY
```

Environment-only operation is now valid; a Key Vault URL is not mandatory when the environment already provides the credential.

## Deployment handling

The original implementation assumed:

```text
deployment == model.value
```

The upgraded implementation preserves that as the default.

But it now supports explicit deployment configuration:

```yaml
llms:
  aoai:
    gpt-5.1: production-gpt51
```

or:

```yaml
llms:
  aoai:
    deployment-name: production-gpt51
```

Embedding deployment can similarly be overridden.

This avoids coupling application model identifiers to Azure deployment names.

## Reasoning model compatibility

The original special case:

```python
O4_MINI_HIGH
```

mapped to:

```text
o4-mini
reasoning_effort=high
```

That behavior is preserved.

However, the upgraded implementation uses:

```python
setdefault("reasoning_effort", "high")
```

so an explicit caller-provided value is not unexpectedly overwritten.

## Mutable-default fix

Original:

```python
additional_kwargs = {}
```

New:

```python
additional_kwargs: Optional[Mapping[str, Any]] = None
```

and a defensive copy is created per invocation.

This prevents state leaking between requests.

## Validation

Added explicit validation for:

- index name
- configured index
- temperature
- timeout
- additional kwargs
- Azure configuration
- embedding configuration
- API-key requirements

This changes failures from opaque `AttributeError`/SDK errors into meaningful configuration errors.

## Timeout behavior

LLM timeout is now configurable and validated.

Embedding timeout is also configurable.

Original embedding timeout was hard-coded to:

```text
10 seconds
```

The upgraded version uses the loader timeout configuration instead.

## Error handling

Introduced:

```python
LLMConfigurationError
```

This is intentionally a subclass of `ValueError` to preserve compatibility with callers that already expect configuration-related `ValueError`s.

SDK initialization failures are wrapped with safe, useful context while retaining the original exception as the cause.

## Logging

Logs now include:

- model
- index
- provider
- Azure deployment name

They do **not** include:

- API keys
- bearer tokens
- Key Vault secret values

## Regression suite

The new regression suite contains **29 tests** covering:

- missing index
- invalid index name
- timeout validation
- temperature validation
- kwargs validation
- mutable kwargs protection
- Azure managed identity
- Azure API-key mode
- Azure Key Vault API key
- missing Azure API key
- OpenAI environment key
- OpenAI Key Vault precedence
- missing OpenAI key
- O4-mini-high behavior
- explicit reasoning override
- Azure deployment override
- missing endpoint
- missing API version
- missing AOAI configuration
- Azure embedding
- Azure embedding API-key mode
- OpenAI embedding
- missing embedding key
- embedding deployment override
- LLM timeout propagation
- embedding timeout propagation
- secret-safe logging
- environment-only OpenAI operation
- environment-only Azure-key operation
- Azure AD without Key Vault
- Azure secret-name configuration
- model normalization

## Verification

The regression tests are dependency-isolated.

They do not:

- call Azure
- call OpenAI
- access Key Vault
- require a managed identity
- require a live endpoint

They verify the loader's contract at the provider boundary.

The final application should additionally have integration tests for:

- actual Azure Entra authentication
- actual Azure OpenAI deployment
- actual embedding deployment
- OpenAI API authentication
- Key Vault secret retrieval
- retry/429 behavior
- network timeout behavior
- model/deployment compatibility
- provider health checks

## Files

Production implementation:

`llm_loader_upgraded.py`

Regression suite:

`test_llm_loader.py`

This file should replace the current `llm_loader.py` after the dependency versions are pinned in the application's dependency manifest.
