# agentic_ai_system.py — Upgrade Report

## Scope

This is the first file in the requested sequential upgrade process. No other uploaded source file was modified or treated as completed.

Source:
- `agentic_ai_system.py`

Output:
- `agentic_ai_system_upgraded.py`
- `test_agentic_ai_system.py`
- `agentic_ai_system_upgrade.diff`

## Verification

- Python syntax compilation: PASS
- Regression tests: 37 passed

## Major defects fixed

1. Mutable constructor defaults:
   - `session_id=str(uuid.uuid4())`
   - `upload_root_dir=tempfile.mkdtemp(...)`
   - `conversation_thread=[]`
   - `blob_bytes={...}`
   were replaced with `None` defaults and per-instance initialization.

2. LlamaIndex memory duplication:
   - The original manually inserted the user message and then supplied the same history together with `user_msg` to `agent.run`.
   - Current LlamaIndex AgentWorkflow accepts a `memory` argument and owns the turn lifecycle. The upgraded implementation passes `memory=self.memory` and lets the framework add the turn.

3. Async bug:
   - `get_response()` previously did `await self.stream_response(...)` even though `stream_response()` returns an async generator.
   - It now normalizes the response directly.

4. Streaming bug:
   - The original iterated over response text character-by-character.
   - The upgraded implementation emits actual response chunks or the complete response text.

5. Nested event-loop patch:
   - Removed `nest_asyncio.apply()` from the execution path.
   - Async callers remain async; the synchronous bridge explicitly rejects calls made from a running event loop.

6. Conversation ordering:
   - The original sorted the caller's list in place and reversed it.
   - The upgrade creates a new chronological list and supports `Z` timestamps and naive timestamps safely.

7. Conversation summarization bug:
   - The original passed an integer into `__summarize_thread()` when the current conversation exceeded eight messages.
   - The upgrade passes the actual message slice.

8. Memory duplication:
   - `set_memory()` now rebuilds the memory from the supplied thread rather than repeatedly appending to an existing memory instance.

9. CSV startup failure:
   - The original always built `PandasQueryEngine`, even when the default blob payload was empty.
   - CSV engine creation is now conditional on the relevant index and non-empty CSV payload.

10. CSV date parsing:
    - Missing `createddate` / `activitydate` columns no longer crash an otherwise valid CSV.
    - Present date columns are parsed with `errors="coerce"`.

11. Upload path traversal:
    - Uploaded filenames are reduced to safe basename paths and constrained to the configured upload directory.

12. Tool construction:
    - Silent dummy-tool fallback was removed. Invalid tool configuration now fails explicitly rather than silently degrading the agent.

13. Retriever fallback bug:
    - The original attempted to construct `RetrieverTool` with a function as a retriever.
    - Invalid retrievers now fail explicitly.

14. GraphRAG initialization:
    - Removed the hardcoded placeholder document containing named individuals/company information.
    - GraphRAG now initializes without injecting fabricated/sample business data.

15. Azure credential duplication:
    - Reuses the credential owned by `AzureCredentialManager` when available instead of creating another `DefaultAzureCredential`.

16. Azure web-search tool:
    - Reuses the shared credential.
    - Avoids logging the full user query.
    - Selects an assistant message instead of blindly returning the first message.
    - Closes the project client when supported.

17. Input validation:
    - Added validation for user questions, queries, task IDs, temperature, top-k, index names, uploaded file content, and CSV bytes.

18. Guardrail contract:
    - Fixed the annotation/behavior mismatch. `guardrail_check()` now consistently returns `bool`.

19. Self-correction:
    - The original `"YES" in verdict` could treat `NO, but YES...` as positive.
    - The upgrade requires an exact `YES` verdict.

20. Response normalization:
    - Added robust extraction for strings, nested response objects, response text, blocks, and response generators.

## Modernization research

Current public package information checked on 2026-08-08:

- `llama-index-core` latest stable found: `0.14.23`, released 2026-06-24.
- `llama-index` latest stable found: `0.14.23`.
- `llama-index-experimental` latest stable found: `0.6.6`, released 2026-04-02.
- `azure-ai-projects` latest stable found: `2.3.0`, released 2026-07-01.

The upgrade keeps `PandasQueryEngine` in this file because `pandasai_system.py` is a separate uploaded file and is explicitly the next sequential unit. That prevents mixing two migration strategies in one change.

## Regression suite

37 tests cover:

- constructor default safety
- event-loop behavior
- response extraction
- timestamp parsing
- chronological conversation ordering
- input validation
- guardrails
- self-correction
- upload path security
- reasoning configuration
- token accounting
- streaming
- retriever metadata
- CSV loading
- optional date columns
- CSV validation
- task validation
- LlamaIndex memory usage
- source-level anti-regression checks

## Important limitation

The uploaded repository does not include the complete dependency lockfile/environment in this turn, and the sandbox does not have the project's Azure/LlamaIndex packages installed. Therefore the suite is dependency-isolated and validates the upgraded class behavior and contracts without making Azure calls.

Before production merge, run the regression suite in the real repository environment with the project's pinned dependencies and add integration tests for:
- Azure AI Search
- Azure AI Foundry agent
- Key Vault/RBAC
- Celery
- actual LlamaIndex FunctionAgent execution
- actual PandasQueryEngine
- uploaded-file indexing
- GraphRAG
- E2B
