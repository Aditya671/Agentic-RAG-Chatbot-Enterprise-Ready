# Runtime correctness — Phase 13

## Test-suite portability

Migration-era tests must execute against checked-in repository code or repository-relative fixtures. They must not depend on assistant-session paths such as `/mnt/data`, arbitrary workspaces, or a developer's local home directory.

Phase 13 establishes this as a quality contract around the canonical runtime and begins retiring tests that target superseded `*_upgraded.py` artifacts.
