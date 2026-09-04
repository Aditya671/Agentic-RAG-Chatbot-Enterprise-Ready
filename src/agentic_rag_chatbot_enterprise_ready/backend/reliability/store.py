"""In-memory persistence used by the reliability layer and deterministic tests."""
from __future__ import annotations

from collections import deque
from threading import RLock

from .contracts import ExecutionTrace


class InMemoryReliabilityStore:
    """Bounded, thread-safe trace store; replaceable by a durable adapter later."""

    def __init__(self, max_traces: int = 1000) -> None:
        if isinstance(max_traces, bool) or not isinstance(max_traces, int) or max_traces < 1:
            raise ValueError("max_traces must be a positive integer")
        self._traces = deque(maxlen=max_traces)
        self._by_id: dict[str, ExecutionTrace] = {}
        self._lock = RLock()

    def save(self, trace: ExecutionTrace) -> None:
        with self._lock:
            old = self._by_id.pop(trace.run_id, None)
            if old is not None:
                try:
                    self._traces.remove(old)
                except ValueError:
                    pass
            self._traces.append(trace)
            self._by_id[trace.run_id] = trace

    def get(self, run_id: str) -> ExecutionTrace | None:
        with self._lock:
            return self._by_id.get(run_id)

    def recent(self, limit: int = 20) -> list[ExecutionTrace]:
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
            raise ValueError("limit must be a positive integer")
        with self._lock:
            return list(self._traces)[-limit:][::-1]
