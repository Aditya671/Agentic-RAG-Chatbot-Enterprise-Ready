# `llm_models.py` — Upgrade Report

## Sequential status

This is **File 5** in the requested one-file-at-a-time upgrade sequence.

Completed:

1. `agentic_ai_system.py`
2. `code_interpreter.py`
3. `graph_rag.py`
4. `llm_loader.py`
5. **`llm_models.py` — completed in this pass**

The original file is a small model registry containing `AIResponseMode`, `AIModelTypes`, `MODEL_TOKEN_LIMITS`, and `DEFAULT_REASONING_EFFORT`. fileciteturn15file0

## What was wrong

The original file had no executable bugs in the conventional sense, but its metadata had become stale relative to the current model catalog.

### 1. GPT-5.6 was absent

The application currently stops at:

```text
gpt-5.1
```

even though the current OpenAI catalog recommends GPT-5.6 for new API usage. citeturn0search4turn0search6

I added:

```python
AIModelTypes.GPT56 = "gpt-5.6"
```

I deliberately did **not** change the existing default from GPT-5.1 to GPT-5.6. Adding a model and silently changing production behavior are two different operations.

## 2. Context limits were stale

The original registry assigned:

```text
GPT-4o       100,000
GPT-4.1      100,000
GPT-4.1-mini 100,000
GPT-5.1      180,000
```

These are not the current documented context windows.

Current verified values include:

- o4-mini: 200,000
- GPT-4o: 128,000
- GPT-4.1: 1,047,576
- GPT-4.1 mini: 1,047,576
- GPT-5.1: 400,000
- GPT-5.6: 1,050,000

OpenAI documents these values in the current model pages. citeturn1search2turn1search3turn1search0turn1search1turn0search0turn0search4

`MODEL_TOKEN_LIMITS` now points to the verified context-window mapping.

## 3. Separated context size from output size

The old file had only:

```python
MODEL_TOKEN_LIMITS
```

That creates ambiguity because a model's context window and maximum generated output are different concepts.

The upgrade adds:

```python
MODEL_CONTEXT_WINDOWS
MODEL_MAX_OUTPUT_TOKENS
```

and keeps:

```python
MODEL_TOKEN_LIMITS = MODEL_CONTEXT_WINDOWS
```

for backward compatibility.

This is especially important for the agent memory layer.

The upgraded `AsyncAgenticAiSystem` consumes `MODEL_TOKEN_LIMITS` when constructing memory. fileciteturn15file2

## 4. Reasoning metadata was mixed with application policy

The original:

```python
DEFAULT_REASONING_EFFORT
```

is an application policy, not necessarily the API's model default.

The upgrade keeps the policy mapping but separately introduces:

```python
REASONING_EFFORTS
```

which describes supported reasoning values.

This prevents the application from confusing:

```text
"What should our application use by default?"
```

with:

```text
"What does this model support?"
```

## 5. GPT-5.1 reasoning support

Current OpenAI documentation states GPT-5.1 supports:

```text
none
low
medium
high
```

and has a 400K context window and 128K maximum output. citeturn0search0

The registry now represents that capability explicitly.

## 6. GPT-5.6 reasoning support

Current OpenAI documentation states GPT-5.6 supports:

```text
none
low
medium
high
xhigh
max
```

with a 1.05M context window and 128K maximum output. citeturn0search4turn0search11

The registry now represents that capability explicitly.

## 7. Non-reasoning models

GPT-4.1 is documented as a non-reasoning model, with low latency and no reasoning step. citeturn1search0

GPT-4.1 mini has the same non-reasoning characteristic. citeturn1search1

The upgraded registry therefore explicitly identifies:

```python
NON_REASONING_MODELS
```

containing:

- GPT-4o
- GPT-4.1
- GPT-4.1 mini

This is safer than pretending every model accepts reasoning controls.

## 8. Model normalization

Added:

```python
normalize_model()
```

This provides one canonical conversion point for:

```python
AIModelTypes.GPT56
```

and:

```python
"gpt-5.6"
```

without requiring every consumer to implement its own conversion.

## 9. Capability accessors

Added:

```python
get_model_token_limit()
get_model_max_output_tokens()
get_default_reasoning_effort()
get_supported_reasoning_efforts()
is_reasoning_model()
```

This prevents consumers from reaching into dictionaries everywhere.

## 10. Reasoning validation

Added:

```python
validate_reasoning_effort()
```

Examples:

```python
validate_reasoning_effort("gpt-5.6", "xhigh")
```

is valid.

But:

```python
validate_reasoning_effort("gpt-5.1", "max")
```

raises a configuration error because GPT-5.1 does not expose `max`.

And:

```python
validate_reasoning_effort("gpt-4.1", "high")
```

raises because GPT-4.1 is non-reasoning.

## Compatibility

Existing names are retained:

```text
AIResponseMode
AIModelTypes
MODEL_TOKEN_LIMITS
DEFAULT_REASONING_EFFORT
```

Existing model IDs are unchanged.

The application default remains:

```text
GPT51
```

The new GPT-5.6 option is opt-in.

This is intentional because `llm_loader.py` uses `model.value` to resolve the model/deployment, and the application is currently Azure-oriented. Adding GPT-5.6 should not automatically force every deployed Azure environment to have a GPT-5.6 deployment.

## Regression testing

The regression suite contains **32 tests**.

Coverage includes:

- response mode compatibility
- existing model IDs
- GPT-5.6 availability
- context window completeness
- maximum output completeness
- verified context values
- verified output limits
- default reasoning policy
- reasoning capabilities
- non-reasoning model classification
- model normalization
- unknown model rejection
- context-limit accessors
- output-limit accessors
- default reasoning accessors
- reasoning model detection
- valid reasoning values
- case/whitespace normalization
- invalid reasoning values
- reasoning on non-reasoning models
- empty reasoning validation
- backwards-compatible context alias
- string-enum behavior
- duplicate model detection
- mapping-key integrity
- default-model stability
- non-reasoning policy integrity

## Final regression result

The suite should be executed against:

```text
test_llm_models.py
```

No external API calls are required because this file is pure model metadata.

## Important architectural observation

This file should remain a **model registry**, not become an SDK configuration dump.

Provider-specific configuration belongs in:

```text
llm_loader.py
```

while application/model capability metadata belongs here.

That separation will make future migrations significantly easier.

## Web research sources

Current OpenAI model catalog and guidance:

- GPT-5.6 model catalog and current recommendations. citeturn0search4turn0search6
- GPT-5.1 model capabilities. citeturn0search0
- GPT-4.1 model capabilities. citeturn1search0
- GPT-4.1 mini model capabilities. citeturn1search1
- GPT-4o model capabilities. citeturn1search3
- o4-mini model capabilities/deprecation status. citeturn1search2

## Files

Production implementation:

`llm_models_upgraded.py`

Regression suite:

`test_llm_models.py`

Upgrade report:

`llm_models_upgrade_report.md`
