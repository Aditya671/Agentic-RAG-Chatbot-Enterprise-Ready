# `pandasai_system.py` — Upgrade Report

## Sequential status

This is **File 6** in the strict one-file-at-a-time sequence.

Completed before this file:

1. `agentic_ai_system.py`
2. `code_interpreter.py`
3. `graph_rag.py`
4. `llm_loader.py`
5. `llm_models.py`

This pass covers only `pandasai_system.py`.

## Source basis

The uploaded file contains the PandasAI replacement for the CSV query engine. It currently imports:

```python
from pandasai import SmartDataframe
from pandasai_openai import AzureOpenAI as PandasAIAzureOpenAI
```

and constructs the LLM with:

```python
api_token=self.credential_manager.get_secret('aoai-api-key')
```

followed by:

```python
SmartDataframe(df, config={"llm": llm, "verbose": True})
```

The uploaded source is a focused replacement fragment inside `AsyncAgenticCSVChatEngine`, not a complete standalone module. Therefore the upgrade preserves that responsibility and provides a production adapter/builder that can be integrated into the existing engine without rewriting unrelated orchestration code.

## Current PandasAI baseline

Fresh web verification on 2026-08-08 found:

- `pandasai` **3.0.0** is the latest stable PyPI release.
- `pandasai-openai` **0.1.6** is the latest published OpenAI extension release.
- PandasAI 3.0 is a substantial architecture change from the 2.x line.

PyPI lists PandasAI 3.0.0 as the current stable release and requires Python >=3.8 and <3.12. citeturn1search2turn0search0

The PandasAI repository's 3.0.0 release notes explicitly mention an Azure OpenAI backend fix and other SmartDataframe/dataframe changes. citeturn2view0

## Major API modernization

### Old

```python
SmartDataframe(df, config={"llm": llm, "verbose": True})
```

### New preferred v3 API

```python
pai.DataFrame(df, config={...})
```

The adapter prefers:

```python
pai.DataFrame
```

and keeps:

```python
SmartDataframe
```

only as a compatibility fallback.

This is important because PandasAI 3.x moved toward the `pai.DataFrame` API while retaining some backwards compatibility. citeturn5search2

## Azure OpenAI integration

The uploaded code uses the separate `pandasai_openai` extension. That is still the appropriate extension boundary.

The current extension package is:

```text
pandasai-openai 0.1.6
```

PyPI lists 0.1.6 as its latest release. citeturn1search0

Current examples show:

```python
from pandasai_openai import AzureOpenAI
```

with Azure endpoint, API version, deployment name and token/key parameters. citeturn4search0

The upgraded implementation therefore does not create a second generic OpenAI client or reuse the LlamaIndex LLM object. PandasAI needs its own provider adapter.

## Critical security finding

PandasAI is not merely a passive query parser.

It generates code/SQL and executes the generated analysis.

That makes this:

```text
User
  ↓
PandasAI
  ↓
LLM-generated code/query
  ↓
Execution
```

a code-execution boundary.

The original code enabled verbose logging and did not configure privacy controls.

The upgraded default is:

```python
PandasAIConfig(
    verbose=False,
    enforce_privacy=True,
    max_retries=3,
    temperature=0.0,
)
```

PandasAI documentation describes privacy behavior around the dataframe information supplied to the LLM. The v2 documentation explicitly describes randomized samples and `enforce_privacy`; this remains an important enterprise design consideration. citeturn0search1

## Important limitation

`enforce_privacy=True` does not mean "no data ever leaves the process."

The LLM still needs enough schema/context to answer the query.

For enterprise deployment, data classification and access control must happen before a dataframe is exposed to PandasAI.

## Legacy `query()` contract preserved

Your existing agent code uses:

```python
self.csv_engine.query(q)
```

The upgraded adapter intentionally preserves that:

```python
PandasAIDataFrameEngine.query()
```

while internally calling:

```python
self.engine.chat(question)
```

It also exposes:

```python
chat()
```

for modern callers.

This avoids forcing another change into `agentic_ai_system.py`, which has already been completed and frozen in the requested sequence.

## Configuration hardening

The old code directly accessed:

```python
self.config.llms.get('aoai').get(...)
```

which can fail with opaque `AttributeError`s.

The new implementation validates:

- `config.llms`
- `config.llms.aoai`
- Azure endpoint
- API version
- deployment
- API key
- credential manager contract
- dataframe type
- dataframe non-emptiness
- query input

Failures are normalized into `PandasAIConfigurationError` or `PandasAIQueryError`.

## API-key handling

Resolution order:

```text
Configured Key Vault secret
        ↓
AZURE_OPENAI_API_KEY
```

The secret is passed directly to the PandasAI Azure adapter.

It is not inserted into process-wide environment state.

It is never logged.

## Deployment handling

The old implementation assumes:

```text
Azure deployment == selected_model.value
```

The new implementation preserves that as a fallback but supports:

```yaml
llms:
  aoai:
    pandasai-gpt-5.1: some-deployment
```

or:

```yaml
llms:
  aoai:
    pandasai-deployment-name: some-deployment
```

This separates application model identifiers from Azure deployment identifiers.

## CSV handling

The builder accepts bytes and loads them using the application's existing Latin-1 compatibility behavior.

It no longer hard-requires:

```text
createddate
activitydate
```

Those columns are parsed only when present.

This preserves the regression fix already introduced in `agentic_ai_system.py`.

## Empty-data handling

The upgraded builder rejects:

- empty bytes
- CSVs with headers but no rows
- empty DataFrames

This prevents creation of a useless PandasAI session.

## Error handling

The original code simply logged:

```text
Failed to create PandasAI engine
```

and re-raised the raw exception.

The new API distinguishes:

```text
PandasAIConfigurationError
PandasAIQueryError
PandasAISystemError
```

This makes failures observable and testable.

## Dependency compatibility

The adapter intentionally supports both:

```text
PandasAI 3.x → pai.DataFrame
```

and:

```text
older compatibility environments → SmartDataframe
```

but the project should pin PandasAI 3.0.0 once the real repository environment is verified.

PandasAI 3.0 specifically addressed compatibility with newer pandas/numpy versions that were problematic for the 2.x line. citeturn1search3

## Regression suite

The suite contains **33 regression tests** covering:

- current `pai.DataFrame` API
- Azure OpenAI construction
- Key Vault API key resolution
- environment API key fallback
- missing API key
- missing Azure configuration
- endpoint validation
- API version validation
- deployment override
- model normalization
- empty DataFrame
- invalid DataFrame type
- legacy `query()` contract
- modern `chat()` alias
- empty query
- query error normalization
- CSV loading
- date-column parsing
- CSVs without date columns
- empty CSV
- CSV with headers/no rows
- invalid CSV input type
- configuration defaults
- retry validation
- temperature validation
- privacy enabled by default
- verbose disabled by default
- retry propagation
- secret-safe logging
- no environment secret mutation
- API-key constructor compatibility
- removal of legacy `PandasQueryEngine`
- current PandasAI dataframe API
- scalar response normalization
- `None` response normalization
- custom Key Vault secret names

## Verification

Final regression execution:

```text
33 passed in 0.10s
```

**33/33 passed.**

The suite is dependency-isolated and does not make Azure/OpenAI requests.

A real integration run is still required before production merge.

## Production integration tests still required

Run against the actual project environment:

1. PandasAI 3.0.0
2. pandas version used by the repository
3. pandasai-openai 0.1.6
4. actual Azure OpenAI deployment
5. actual Key Vault secret
6. real Salesforce CSV
7. real numeric aggregation
8. date filtering
9. group-by analysis
10. joins/cross-table analysis if used
11. chart generation if exposed
12. malicious prompt/code-generation cases
13. concurrent user sessions
14. large CSV performance
15. memory pressure
16. generated-code execution isolation

## Important architecture/security follow-up

For this application, PandasAI should not be considered equivalent to a normal deterministic pandas utility.

The correct production boundary is:

```text
User Query
    ↓
Agent
    ↓
CSV/PandasAI Tool
    ↓
PandasAI
    ↓
LLM-generated SQL/code
    ↓
Sandboxed execution
    ↓
Result
```

The existing E2B component is already a dedicated sandbox layer in this application. The next architecture pass should determine whether PandasAI can be configured to use a sandboxed executor rather than executing generated code directly in the application process.

Do not expose arbitrary untrusted user data/prompts to a local PandasAI execution environment without that decision.

## Deliverables

- `pandasai_system_upgraded.py`
- `test_pandasai_system.py`
- `pandasai_system_upgrade_report.md`
