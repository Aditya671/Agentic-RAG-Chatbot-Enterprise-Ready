# Code-execution retirement boundary

The application does not support arbitrary Python execution, remote sandboxes, or generated-code execution as an agent capability.

## Supported behavior

The maintained agent surface is limited to application-owned capabilities such as:

- enterprise document retrieval;
- uploaded-file indexing and querying;
- internet search;
- optional GraphRAG;
- structured CSV analysis through the supported structured-query adapter.

Structured CSV analysis must remain a provider-backed query adapter. It must not be replaced with a generated-code execution engine merely to provide dataframe analysis.

## Compatibility behavior

Historical callers may still encounter the `CodeInterpreterSandbox` compatibility module or the compatibility no-op in `component_runtime.py`. These surfaces are compatibility artifacts, not supported capabilities. They must not construct a sandbox, expose `run_python`, or add a code-execution tool to the maintained agent registry.

The canonical runtime no longer carries coding-assistant state, code-interpreter construction, code-execution tool registration, or coding-specific prompt selection. New application code must not add a dependency on the remaining compatibility surfaces.

## Regression boundary

The repository keeps dependency-light tests that inspect the maintained agent builder and canonical runtime for executable behavior, alongside compatibility checks for the retired components. The retirement guarantee must not depend on Azure credentials, a live LLM, or a sandbox service.
