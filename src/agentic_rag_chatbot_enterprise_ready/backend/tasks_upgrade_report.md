# `tasks.py` — Upgrade Report

## File sequence

This is the next file after the completed:

1. `agentic_ai_system.py`
2. `code_interpreter.py`
3. `graph_rag.py`
4. `llm_loader.py`
5. `llm_models.py`
6. `pandasai_system.py`
7. `prompts.py`
8. `reranker.py`

This pass covers **only `tasks.py`**.

## Original implementation

The uploaded module creates a Celery application using Redis and defines one
task:

```python
@celery_app.task(name="tasks.index_files")
def index_files_task(...):
    indexer = UserUploadedFileIndexer(...)
    result = asyncio.run(
        indexer.index_uploaded_files(file_list=file_list)
    )
    return result
```

The original file also calls:

```python
load_dotenv(override=True)
```

and passes `memory=None` because the memory object cannot be serialized into a
Celery task. fileciteturn28file0

## Current Celery verification

Fresh web research on 2026-08-08 confirms the current stable Celery line is
**5.6**, with current documentation published in July 2026. citeturn0search0turn0search3

The current Celery documentation continues to support Redis as a stable broker
and result backend. citeturn0search5

Celery's current default concurrency model is prefork and is recommended for
most workloads; this is compatible with a synchronous task wrapping an async
operation via an isolated `asyncio.run()` boundary. citeturn0search2

## Major issue #1 — `load_dotenv(override=True)`

Original:

```python
load_dotenv(override=True)
```

This is dangerous in containers/CI/Kubernetes because a `.env` file can
overwrite environment variables that were intentionally injected by the
runtime.

Changed to:

```python
load_dotenv(override=False)
```

Runtime environment configuration therefore wins over local `.env` values.

## Major issue #2 — no explicit task serialization policy

The original task accepts a list plus strings/integers, but the Celery app does
not explicitly constrain serialization.

The upgraded application uses:

```python
task_serializer="json"
result_serializer="json"
accept_content=["json"]
```

This prevents accidental acceptance of pickle content and keeps the task
boundary explicit.

This is especially appropriate because the task should receive references to
files, not arbitrary Python objects or file contents.

## Major issue #3 — input validation

The original function accepts anything that Python can bind to the parameters.

The upgraded task validates:

### `file_list`

Must be:

```text
sequence[str]
```

and:

- non-empty
- not a string pretending to be a list
- no empty path values

### `root_dir`

Non-empty string.

### `index_name`

Non-empty string.

### `model`

Non-empty string.

### `similarity_top_k`

Positive integer.

This prevents malformed Celery messages from reaching the indexing layer.

## Major issue #4 — worker-local indexer creation

The original code correctly recognizes that the memory object cannot be sent
through Celery.

That design is preserved.

The upgraded task still creates:

```python
UserUploadedFileIndexer(...)
```

inside the worker and uses:

```python
memory=None
```

This is the correct dependency direction.

The task message contains configuration primitives; the worker constructs its
own service objects.

## Major issue #5 — explicit task lifecycle observability

Added:

```python
task_track_started=True
```

This is useful for file indexing because indexing is a long-running operation.
Celery documents `track_started` specifically for tasks where visibility into
the currently running state is useful. citeturn0search4

The task can therefore progress through:

```text
PENDING
   ↓
STARTED
   ↓
SUCCESS
```

or:

```text
PENDING
   ↓
STARTED
   ↓
FAILURE
```

## Major issue #6 — time limits

Added configurable:

```text
CELERY_INDEX_SOFT_TIME_LIMIT
CELERY_INDEX_TIME_LIMIT
```

with safe defaults:

```text
soft = 1800 seconds
hard = 2100 seconds
```

This prevents a corrupted file or pathological indexing operation from
holding a worker indefinitely.

The soft/hard distinction also gives future code an opportunity to clean up
before hard termination.

## Major issue #7 — deliberately did NOT enable automatic retries

This is an important decision.

It would be tempting to add:

```python
autoretry_for=(Exception,)
```

but that would be unsafe without knowing whether:

```python
UserUploadedFileIndexer.index_uploaded_files()
```

is idempotent.

If indexing partially succeeds and the worker retries, we could create:

```text
duplicate chunks
duplicate documents
duplicate vector entries
duplicate index records
```

The current Celery documentation explicitly notes that late-ack/retry
strategies require idempotent tasks, and task redelivery can result in the task
being executed again. citeturn0search18

Therefore this file **does not invent an idempotency guarantee**.

Retries should be introduced only after the indexer's behavior is analyzed.

## Major issue #8 — deliberately did NOT enable `acks_late`

Same reasoning.

Celery documents that late acknowledgement can cause a task to execute twice
after worker failure and recommends it when the task is idempotent. citeturn0search4turn0search18

We do not yet have evidence from this file that indexing is idempotent.

Therefore:

```text
acks_late = default
```

is retained.

This is safer than pretending the index operation is safely replayable.

## Major issue #9 — task is bound

Changed from an ordinary task to:

```python
@celery_app.task(
    name=TASK_NAME,
    bind=True,
)
```

This does not change the external task name.

It gives us access to the Celery task context for future:

- retries
- progress updates
- task IDs
- request metadata
- structured task state

without requiring another breaking task API change.

## Major issue #10 — async boundary isolated

The original:

```python
asyncio.run(...)
```

is retained conceptually because Celery's default prefork worker executes this
synchronous task outside an application-managed event loop.

The call is isolated into:

```python
_run_async()
```

This makes the boundary explicit and testable.

We should **not** create an event loop during module import.

## Major issue #11 — result preserved

The upgraded task still returns the exact result from:

```python
index_uploaded_files()
```

rather than inventing a new response structure.

That protects the existing caller/result contract.

## Major issue #12 — no file content in Celery messages

The task accepts:

```text
file_list
root_dir
```

rather than:

```text
bytes
file objects
dataframes
memory objects
```

This is the correct architecture.

Celery messages should remain small and serialization-safe. File contents
should remain in durable/shared storage.

## Logging

Added structured parameterized logging:

```text
Starting uploaded-file indexing
Uploaded-file indexing completed
Uploaded-file indexing failed
```

The logs contain:

- number of files
- index name
- model

They do not log:

- file contents
- API keys
- credentials
- memory objects

## Regression suite

Added **50 regression tests** covering:

- Celery application defaults
- task registration
- task name compatibility
- JSON serialization
- Redis defaults
- result backend
- started-state tracking
- soft/hard time limits
- indexer construction
- `memory=None`
- argument propagation
- file-list copying
- invalid file lists
- empty paths
- invalid configuration strings
- invalid `similarity_top_k`
- async invocation
- result propagation
- indexing failures
- retry policy
- acknowledgment policy
- pickle rejection
- secret protection
- `.env` override behavior
- task typing
- async helper
- environment configuration
- task documentation
- validation-before-construction
- no global indexer
- public task name stability

## Verification

Final regression run:

```text
50 passed in 0.14s
```

**50/50 passed.**

The runtime emitted an unrelated spreadsheet-runtime warmup warning after
pytest completed, but pytest returned:

```text
returncode: 0
```

and all 50 tests passed.

## Deliverables

- `tasks_upgraded.py`
- `test_tasks.py`
- `tasks_upgrade_report.md`

## Production integration verification still required

Before replacing the real `tasks.py`, the complete application environment
should verify:

1. Celery 5.6.x
2. Redis broker connectivity
3. Redis result backend
4. actual `UserUploadedFileIndexer`
5. actual async indexing implementation
6. worker process startup
7. task serialization
8. task result serialization
9. large file-list behavior
10. worker crash/restart behavior
11. duplicate delivery behavior
12. partial indexing behavior
13. task timeout behavior
14. idempotency of `index_uploaded_files`
15. concurrent indexing of the same index

## Important next-level finding

The most important unresolved question is **not in `tasks.py` itself**:

> Is `UserUploadedFileIndexer.index_uploaded_files()` idempotent?

That determines whether we can safely introduce:

```text
acks_late
retry
worker-lost requeue
exponential backoff
```

The current Celery documentation explicitly warns that redelivery can execute a
task again, making idempotency critical for those configurations.
citeturn0search18turn0search14

I deliberately did not guess the answer.

That should be determined when we reach and analyze the indexer implementation
in its own sequential turn.
