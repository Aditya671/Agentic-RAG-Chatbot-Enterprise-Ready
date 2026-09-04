# Runtime Correctness — Phase 22

## Canonical model registry

The maintained model registry is now the single source of truth for model identifiers, context limits, output limits, and reasoning capabilities.

### Changes

- Promoted `backend.orchestration.llm_models` to the canonical implementation.
- Added GPT-5.6 without changing the existing GPT-5.1 application default.
- Separated context-window limits from maximum output-token limits.
- Added explicit reasoning capability metadata and validation.
- Added model normalization and capability accessors.
- Moved regression coverage into the maintained top-level `tests/` suite.
- Removed the duplicate `llm_models_upgraded.py` implementation.
- Removed the obsolete file-local upgrade report and migration-era test.

### Compatibility

Existing public names remain available:

- `AIResponseMode`
- `AIModelTypes`
- `MODEL_TOKEN_LIMITS`
- `DEFAULT_REASONING_EFFORT`

Existing model identifiers remain unchanged, and GPT-5.1 remains the application default. Newer model support must be explicitly selected and deployed.

### Validation boundary

Model capability metadata is kept provider-neutral. Azure/OpenAI SDK construction remains owned by `llm_loader.py` rather than the model registry.

No local test suite was executed in this environment. CI remains authoritative.
