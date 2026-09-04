# Runtime Correctness — v36

## Scope

This phase consolidates regression coverage for the retired code-execution boundary.

## Changes

- removes the duplicate `test_code_execution_removed.py` suite;
- keeps the maintained retirement coverage in `test_code_execution_boundary.py`;
- replaces the stale component-runtime expectation that treated the retired path as an exception-based fail-open flow;
- adds behavioral coverage proving the compatibility component does not invoke its initializer and emits only the retirement warning;
- adds behavioral coverage proving the legacy compatibility class rejects construction.

## Boundary contract

Arbitrary code execution remains unsupported. The compatibility component is a
no-op that never constructs a sandbox, while the legacy compatibility class
fails explicitly if instantiated.

This phase changes test ownership and correctness only; it does not restore or
expand code-execution capability.

## Validation

Focused regression tests are included. Local test execution is not claimed;
repository CI remains authoritative for full test, lint, and build verification.
