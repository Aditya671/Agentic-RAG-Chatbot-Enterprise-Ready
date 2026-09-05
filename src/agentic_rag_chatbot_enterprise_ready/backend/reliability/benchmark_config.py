"""Versioned benchmark configuration identity."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class BenchmarkConfig:
    """Explicit configuration that makes a benchmark run reproducible."""

    benchmark_id: str
    version: str
    scenario_set_version: str
    repetitions: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.benchmark_id.strip():
            raise ValueError("benchmark_id must be non-empty")
        if not self.version.strip():
            raise ValueError("version must be non-empty")
        if not self.scenario_set_version.strip():
            raise ValueError("scenario_set_version must be non-empty")
        if isinstance(self.repetitions, bool) or self.repetitions < 1:
            raise ValueError("repetitions must be >= 1")

    @property
    def identity(self) -> str:
        return f"{self.benchmark_id}@{self.version}::scenarios@{self.scenario_set_version}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "benchmark_id": self.benchmark_id,
            "version": self.version,
            "scenario_set_version": self.scenario_set_version,
            "repetitions": self.repetitions,
            "metadata": dict(self.metadata),
            "identity": self.identity,
        }
