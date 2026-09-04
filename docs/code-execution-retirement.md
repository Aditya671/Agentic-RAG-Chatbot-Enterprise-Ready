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

Historical callers may still encounter the `CodeInterpreterSandbox` compatibility module and the legacy coding-assistant setting on old runtime objects. These surfaces are compatibility artifacts, not supported capabilities. They must not construct a sandbox, expose `run_python`, or add a code-execution tool to the maintained agent registry.

New application code must not add a dependency on these compatibility surfaces. Any future removal of the remaining legacy setting should be performed as a dedicated compatibility-breaking cleanup after callers have migrated.

## Regression boundary

The repository keeps tests that inspect the maintained agent builder and compatibility implementation for executable behavior. Those tests are intentionally dependency-light: the retirement guarantee must not depend on Azure credentials, a live LLM, or a sandbox service.
