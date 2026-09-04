# Runtime correctness — Phase 13

## Test-suite portability

The repository has accumulated migration-era tests that load generated files from machine-specific `/mnt/data` paths. Those tests are not portable to a fresh clone or GitHub Actions runner.

Phase 13 establishes repository-relative test execution as an explicit quality contract. The suite must exercise checked-in source or fixtures from the repository rather than relying on files created by an external assistant session.

This phase also prepares the next cleanup step: replace or retire migration-era tests that target superseded `*_upgraded.py` artifacts, while preserving coverage for the canonical runtime surface introduced in Phases 11–12.
