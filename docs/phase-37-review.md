# Phase 37 Review Notes

## Change

The Chainlit `set_model_top_k` setting now uses the same minimum supported by the backend runtime.

## Before

- persisted/UI normalization allowed `0`;
- the UI slider exposed `0`;
- the runtime rejected values below `1`.

## After

- normalization clamps to `1..30`;
- the UI exposes `1..30`;
- valid existing values are unchanged.

This is a boundary-alignment change only.
