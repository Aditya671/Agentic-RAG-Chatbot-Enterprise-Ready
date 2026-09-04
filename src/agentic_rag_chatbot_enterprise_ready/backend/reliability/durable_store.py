"""Durable JSONL persistence for execution traces."""
from __future__ import annotations

import json
import os
from collections.abc import Iterable
from pathlib import Path
from threading import RLock

from .contracts import Evidence, EvidenceRecord, ExecutionEvent, ExecutionTrace, ProvenanceRecord


class JsonlReliabilityStore:
    """Append-only trace store with deterministic reload and bounded reads."""

    def __init__(self, path: str | os.PathLike[str]) -> None:
        if not path:
            raise ValueError("path must be non-empty")
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._by_id: dict[str, ExecutionTrace] = {}
        self._order: list[str] = []
        self._load()

    def save(self, trace: ExecutionTrace) -> None:
        if not isinstance(trace, ExecutionTrace):
            raise TypeError("trace must be an ExecutionTrace")
        payload = json.dumps(trace.to_dict(), ensure_ascii=False, separators=(",", ":"))
        with self._lock:
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(payload + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            if trace.run_id not in self._by_id:
                self._order.append(trace.run_id)
            self._by_id[trace.run_id] = trace

    def get(self, run_id: str) -> ExecutionTrace | None:
        with self._lock:
            return self._by_id.get(run_id)

    def recent(self, limit: int = 20) -> list[ExecutionTrace]:
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
            raise ValueError("limit must be a positive integer")
        with self._lock:
            return [self._by_id[key] for key in self._order[-limit:][::-1]]

    def __iter__(self) -> Iterable[ExecutionTrace]:
        with self._lock:
            return iter(tuple(self._by_id[key] for key in self._order))

    def _load(self) -> None:
        if not self.path.exists():
            return
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                try:
                    trace = self._deserialize(json.loads(line))
                except (TypeError, ValueError, json.JSONDecodeError) as exc:
                    raise ValueError(f"invalid reliability record at line {line_number}") from exc
                if trace.run_id not in self._by_id:
                    self._order.append(trace.run_id)
                self._by_id[trace.run_id] = trace

    @staticmethod
    def _deserialize(payload: dict) -> ExecutionTrace:
        if not isinstance(payload, dict) or not payload.get("run_id"):
            raise ValueError("record must contain run_id")
        events = [ExecutionEvent(**item) for item in payload.get("events", [])]
        evidence_records = []
        for item in payload.get("evidence", []):
            provenance = item["provenance"]
            evidence_records.append(
                EvidenceRecord(
                    Evidence(**item["evidence"]),
                    ProvenanceRecord(**{**provenance, "parent_ids": tuple(provenance.get("parent_ids", ())) }),
                )
            )
        return ExecutionTrace(
            run_id=payload["run_id"],
            started_at=payload.get("started_at") or "",
            finished_at=payload.get("finished_at"),
            events=events,
            evidence=evidence_records,
            outcome=payload.get("outcome", "running"),
            error=payload.get("error"),
        )
