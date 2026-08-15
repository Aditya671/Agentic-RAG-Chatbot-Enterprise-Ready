# `reranker.py` — Upgrade Report

## Sequential status

This is **File 8** in the strict one-file-at-a-time sequence.

Completed:

1. `agentic_ai_system.py`
2. `code_interpreter.py`
3. `graph_rag.py`
4. `llm_loader.py`
5. `llm_models.py`
6. `pandasai_system.py`
7. `prompts.py`

This pass covers only `reranker.py`.

## Source baseline

The uploaded implementation is a small wrapper around LlamaIndex `LLMRerank`:

```python
from llama_index.core.postprocessor import LLMRerank
from llama_index.core.llms import LLM
```

and constructs:

```python
LLMRerank(
    choice_batch_size=choice_batch_size,
    top_n=top_n,
    llm=llm,
)
```

The current application calls it from `agentic_ai_system.py` with a smaller
GPT model and:

```text
top_n = min(5, similarity_top_k)
```

before attaching it to the Azure AI Search retriever as a node postprocessor.
That integration contract is preserved. fileciteturn28file8

## Current LlamaIndex verification

Web verification on **2026-08-08** confirms that the current stable
`llama-index-core` release is **0.14.23**, published June 24, 2026. PyPI also
lists Python >=3.10 for the current release line. citeturn0search0

The current LlamaIndex API still exposes `LLMRerank` as a node postprocessor
with:

- `top_n`
- `choice_batch_size`
- `llm`
- optional `choice_select_prompt`
- callback manager support

and its implementation performs second-stage selection over retrieved
`NodeWithScore` objects. citeturn1search1

Current LlamaIndex examples continue to use:

```python
LLMRerank(
    choice_batch_size=5,
    top_n=3,
    llm=...
)
```

and attach the result to the retrieval/reranking pipeline. citeturn1search0turn1search8

## Conclusion on API modernization

There is **no required breaking API migration** for this file.

The import already uses the modern namespaced API:

```python
from llama_index.core.postprocessor import LLMRerank
from llama_index.core.llms import LLM
```

That is preferable to historical paths such as:

```python
llama_index.indices.query.schema
```

or older `service_context`-based construction.

Therefore I did **not** replace `LLMRerank` with an unrelated reranking
framework simply to claim an upgrade.

The modernization is in the wrapper's validation, observability, configurability,
and regression behavior.

## Problems in the original implementation

### 1. No argument validation

The original code accepts:

```text
top_n = 0
top_n = -1
choice_batch_size = 0
choice_batch_size = -5
```

and even non-integer values.

Those errors are detected only later by the library or during retrieval.

The upgraded version validates these values before constructing LlamaIndex.

### 2. `llm=None` is not rejected explicitly

The original function relies on `LLMRerank` to fail.

The upgraded function fails immediately with:

```text
RerankerConfigurationError
```

This gives the caller a deterministic configuration error.

### 3. Broad exception handling without normalization

The original code:

```python
except Exception as e:
    logger.error(...)
    raise
```

does not add much operational value.

The upgraded version:

- logs the failure with a traceback
- does not log credentials
- preserves the original exception as `__cause__`
- raises a stable application-level `RuntimeError`

### 4. Logging uses f-strings

The old:

```python
logger.info(f"LLMRerank initialized with top_n={top_n}")
```

was replaced with parameterized logging:

```python
logger.info(
    "LlamaIndex LLMRerank initialized: top_n=%d, choice_batch_size=%d",
    top_n,
    choice_batch_size,
)
```

This is preferable for structured logging and avoids unnecessary interpolation.

### 5. No observability injection

The upgraded API accepts:

```python
callback_manager=...
```

when the application wants LlamaIndex callback/token/telemetry integration.

This is additive and optional, so existing callers continue to work.

### 6. No custom reranking prompt support

The current LlamaIndex API supports `choice_select_prompt`.

The upgraded wrapper exposes it as an optional keyword-only argument.

This allows the application to eventually introduce a PERE-specific reranking
prompt without modifying the module again.

### 7. Secrets remain outside this module

The reranker does not create or mutate:

```text
OPENAI_API_KEY
AZURE_OPENAI_API_KEY
```

The LLM is injected by the caller.

This is the correct dependency direction:

```text
LLM configuration
       ↓
llm_loader.py
       ↓
LLM instance
       ↓
reranker.py
       ↓
LLMRerank
```

The reranker should not know how Azure credentials are obtained.

## Important architecture finding

The current architecture calls this a "Neural Reranker":

```text
LLM
 ↓
LLMRerank
```

Technically, this is an **LLM-based reranker**, not a neural cross-encoder
reranker in the usual retrieval-system sense.

That distinction matters.

Current LlamaIndex documentation describes `LLMRerank` as an LLM-based
postprocessor that asks the LLM to select relevant nodes. citeturn1search1

Therefore the component should conceptually be treated as:

```text
Stage 1:
Azure AI Search hybrid retrieval
        ↓
Stage 2:
LLM-based reranking
        ↓
Stage 3:
Response synthesis
```

not:

```text
Embedding retriever
        ↓
Cross-encoder neural reranker
```

## Cost/latency implication

LLM reranking is substantially more expensive than local/vector similarity
ranking because it makes LLM calls for candidate batches.

LlamaIndex's own discussion of LLM reranking describes the second-stage pattern:
use initial embedding retrieval to reduce the candidate set, then apply LLM
reranking rather than asking the LLM to rank the entire corpus. citeturn1search7

Your existing architecture already follows the right basic pattern:

```text
similarity_top_k = 20
        ↓
LLMRerank
        ↓
top_n = min(5, similarity_top_k)
```

This is a sensible starting point.

## Important future optimization

The application currently loads:

```text
GPT-4.1-mini
```

for reranking.

That is a reasonable compatibility choice, but this file should not hardcode the
model. The model selection belongs in `agentic_ai_system.py` / `llm_loader.py`,
which has already been upgraded.

The reranker should remain model-agnostic.

## Current integration compatibility

The upgraded implementation preserves:

```python
initialize_reranker(
    llm=rerank_llm,
    top_n=reranker_top_n,
)
```

so the completed `agentic_ai_system.py` does not need to be reopened.

The existing upgraded agent still does:

```python
top_n = min(5, self.similarity_top_k)
return initialize_reranker(
    llm=rerank_llm,
    top_n=top_n,
)
```

which remains compatible. fileciteturn28file18

## Regression suite

Added **32 regression tests** covering:

- default configuration
- custom `top_n`
- custom batch size
- `top_n > batch_size`
- `batch_size > top_n`
- zero values
- negative values
- non-integer values
- `None` LLM
- callback manager forwarding
- custom reranking prompt
- constructor failure normalization
- original exception preservation
- environment credential safety
- secret-safe logging
- current LlamaIndex import path
- removal of legacy import paths
- removal of `service_context`
- no environment mutation
- no hardcoded API keys
- parameterized logging
- explicit exception propagation
- type annotations
- application default compatibility
- optional-argument forwarding

## Verification

Full regression execution:

```text
32 passed in 0.09s
```

**32/32 passed.**

The tests are dependency-isolated and make no Azure or LLM calls.

## Deliverables

- `reranker_upgraded.py`
- `test_reranker.py`
- `reranker_upgrade_report.md`

## Production verification still required

Before upgrading the project's actual dependency lock to the latest
`llama-index-core`, run an integration test using the repository's complete
dependency set.

The current PyPI release is:

```text
llama-index-core == 0.14.23
```

and it requires Python >=3.10. citeturn0search0

The real integration test should verify:

1. Azure OpenAI LLM construction from `llm_loader.py`
2. Azure AI Search retrieval
3. 20 candidate nodes
4. LLMRerank with `top_n=5`
5. correct `NodeWithScore` ordering
6. scores are preserved/updated as expected
7. empty retrieval results
8. fewer than `top_n` candidates
9. LLM failure
10. timeout behavior
11. callback/token accounting
12. end-to-end answer quality

## One deliberate non-change

I did **not** replace LLMRerank with a local cross-encoder such as a
Sentence-Transformers model in this file.

That would change the application's model architecture and dependency footprint.
It should be evaluated as a separate retrieval experiment against the current
LLM reranker, using measurable metrics such as:

- Recall@K
- MRR
- NDCG@K
- answer faithfulness
- latency
- cost/query

That experiment belongs after the current baseline is stable, not as an
unverified replacement inside this file.
