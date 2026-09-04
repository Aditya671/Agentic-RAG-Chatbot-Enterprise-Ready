# Phase 47 — Native Pandas Structured Query Migration

## Decision

The project no longer depends on `llama-index-experimental` for CSV analysis. Pandas is the maintained structured-data execution layer, pinned to `3.0.5` for the current Python 3.12/3.13 target.

## Why

The previous implementation delegated dataframe analysis to LlamaIndex's experimental `PandasQueryEngine`. Besides introducing a dependency constraint that conflicted with pandas 3, that model allowed an LLM-generated Python execution path that was unnecessary for the application's supported structured-data use cases.

## Runtime model

`IntegratedAsyncAgenticAiSystem`
→ `structured_csv_runtime.py`
→ `StructuredQueryEngine`
→ pandas

The LLM is used only to translate a natural-language request into a JSON operation plan. The executor validates:

- operation names;
- dataframe column names;
- aggregation names;
- filter operators;
- result limits.

Only allow-listed pandas operations execute. Generated Python is never evaluated and dataframe values are never treated as instructions.

## CSV ingestion improvements

The maintained runtime now:

- supports UTF-8 with BOM, UTF-8, and Latin-1 fallback;
- rejects empty CSV payloads;
- normalizes blank and duplicate column names;
- detects common date/datetime columns and converts valid values;
- preserves caller metadata.

## Dependency reconciliation

The same CI run that exposed the pandas conflict also exposed an independent Azure Search SDK conflict: `llama-index-vector-stores-azureaisearch==0.5.0` requires `azure-search-documents<12`. The project therefore pins `azure-search-documents==11.6.0`, which is a stable release in that compatible range. citeturn6search0turn6search2

## Verification boundary

The full GitHub Actions quality workflow remains authoritative for dependency resolution, source compilation, Ruff, tests, and wheel creation. Cloud integration with Azure services is not claimed by unit tests alone.
