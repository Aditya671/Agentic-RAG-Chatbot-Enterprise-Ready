# Phase 37 Summary

Phase 37 closes a concrete contract mismatch between the frontend and runtime retrieval settings.

The frontend previously permitted a `0` retrieval depth even though the maintained runtime requires at least one result. The setting is now normalized and presented as `1..30`.

No provider implementation or retrieval strategy was changed.
