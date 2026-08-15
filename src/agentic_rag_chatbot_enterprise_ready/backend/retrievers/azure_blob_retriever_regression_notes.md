# Azure Blob File Retriever — Regression Test Suite

This package contains the upgraded `AzureBlobFileRetriever` and its regression suite.

## What was fixed

- Removed the constructor's mandatory network call to `container_client.exists()`.
- Fixed the connection-string constructor path so it can actually be used without supplying a container client.
- Added passwordless `account_url + credential` support.
- Preserved dependency injection for easy unit testing and cloud portability.
- Preserved filename-date selection semantics while making tie-breaking deterministic.
- Added extension normalization (`csv` and `.csv` both work).
- Added validation for invalid configuration, filenames, paths, and concurrency.
- Preserved stream position when converting a `BlobStream` to bytes.
- Removed `print()` side effects and switched to structured logging.
- Fixed saving to a filename in the current directory (`os.path.dirname()` can be empty).
- Forwarded date-selection and concurrency options through `get_and_save_latest`.
- Avoided eagerly materializing the complete blob listing before selection.
- Kept the existing public method names so downstream callers have a low-risk migration path.

## Regression coverage

The tests cover:

1. `BlobStream` byte/string/JSON conversion.
2. Stream-position preservation.
3. UTC normalization.
4. Filename date parsing.
5. Invalid filename dates.
6. Latest-by-filename-date selection.
7. Latest-by-`last_modified` fallback.
8. Case-insensitive extensions.
9. Missing matching blobs.
10. Prefix forwarding.
11. Download concurrency.
12. Blob metadata propagation.
13. Direct blob retrieval.
14. Constructor dependency injection.
15. Constructor validation.
16. Concurrency validation.
17. Local file writes.
18. Nested directory creation.
19. Latest-file save flow.
20. Deterministic tie-breaking.

## Running

Install the project dependencies, including `azure-storage-blob` and `pytest`, then run:

```bash
pytest -q
```

For the real application repository, these tests should be moved under the project's existing test convention (for example `tests/unit/`) and included in CI.

## Azure production note

Microsoft's current Python Blob Storage guidance recommends passwordless authentication with `DefaultAzureCredential` for production scenarios. The upgraded adapter therefore supports an injected credential without forcing a change on existing connection-string callers.
