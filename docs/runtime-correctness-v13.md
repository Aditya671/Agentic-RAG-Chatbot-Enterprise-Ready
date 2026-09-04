# Runtime correctness — Phase 13

## Test-suite portability

Migration-era tests must execute against checked-in repository code or repository-relative fixtures. They must not depend on assistant-session paths such as `/mnt/data`, arbitrary workspaces, or a developer's local home directory.

This phase hardens the quality boundary around the now-canonical runtime and prepares retirement of superseded `*_upgraded.py` test artifacts without weakening coverage of the active application surface.
