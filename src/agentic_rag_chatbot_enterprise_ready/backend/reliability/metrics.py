"""Provider-neutral, bounded operational metrics primitives."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from threading import RLock
from typing import Mapping


@dataclass(frozen=True, slots=True)
class MetricSnapshot:
    """Immutable metric observation safe to export or inspect."""

    name: str
    metric_type: str
    value: float
    labels: Mapping[str, str] = field(default_factory=dict)


class InMemoryMetrics:
    """Deterministic in-memory metrics registry with bounded dimensions."""

    def __init__(
        self,
        *,
        max_metrics: int = 1000,
        max_labels_per_metric: int = 8,
        max_label_value_length: int = 64,
    ) -> None:
        for name, value in (
            ("max_metrics", max_metrics),
            ("max_labels_per_metric", max_labels_per_metric),
            ("max_label_value_length", max_label_value_length),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(f"{name} must be a positive integer")
        self.max_metrics = max_metrics
        self.max_labels_per_metric = max_labels_per_metric
        self.max_label_value_length = max_label_value_length
        self._values: dict[tuple[str, tuple[tuple[str, str], ...]], float] = {}
        self._types: dict[str, str] = {}
        self._lock = RLock()

    def increment(
        self,
        name: str,
        value: float = 1.0,
        *,
        labels: Mapping[str, str] | None = None,
    ) -> None:
        self._record(name, "counter", value, labels)

    def set_gauge(
        self,
        name: str,
        value: float,
        *,
        labels: Mapping[str, str] | None = None,
    ) -> None:
        self._record(name, "gauge", value, labels, replace=True)

    def snapshot(self) -> tuple[MetricSnapshot, ...]:
        with self._lock:
            rows = []
            for (name, label_items), value in sorted(self._values.items()):
                rows.append(
                    MetricSnapshot(
                        name=name,
                        metric_type=self._types[name],
                        value=value,
                        labels=dict(label_items),
                    )
                )
            return tuple(rows)

    def _record(
        self,
        name: str,
        metric_type: str,
        value: float,
        labels: Mapping[str, str] | None,
        *,
        replace: bool = False,
    ) -> None:
        normalized_name = self._normalize_name(name)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError("metric value must be numeric")
        if not math.isfinite(float(value)):
            raise ValueError("metric value must be finite")
        normalized_labels = self._normalize_labels(labels)
        key = (normalized_name, tuple(sorted(normalized_labels.items())))
        with self._lock:
            existing_type = self._types.get(normalized_name)
            if existing_type is not None and existing_type != metric_type:
                raise ValueError(
                    f"metric {normalized_name!r} is already registered as {existing_type}"
                )
            if key not in self._values and len(self._values) >= self.max_metrics:
                raise ValueError("metric cardinality limit exceeded")
            self._types[normalized_name] = metric_type
            current = self._values.get(key, 0.0)
            self._values[key] = float(value) if replace else current + float(value)

    @staticmethod
    def _normalize_name(name: str) -> str:
        if not isinstance(name, str) or not name.strip():
            raise ValueError("metric name must be a non-empty string")
        normalized = name.strip()
        if len(normalized) > 128:
            raise ValueError("metric name exceeds the maximum length")
        if not all(char.isalnum() or char in {"_", ".", "-"} for char in normalized):
            raise ValueError("metric name contains unsupported characters")
        return normalized

    def _normalize_labels(self, labels: Mapping[str, str] | None) -> dict[str, str]:
        if labels is None:
            return {}
        if not isinstance(labels, Mapping):
            raise TypeError("labels must be a mapping")
        if len(labels) > self.max_labels_per_metric:
            raise ValueError("metric label cardinality limit exceeded")
        normalized: dict[str, str] = {}
        for key, value in labels.items():
            if not isinstance(key, str) or not key.strip():
                raise ValueError("metric label names must be non-empty strings")
            if not isinstance(value, str):
                raise TypeError("metric label values must be strings")
            label_name = key.strip()
            label_value = value.strip()
            if not label_value:
                raise ValueError(f"metric label {label_name!r} must be non-empty")
            if len(label_name) > 64:
                raise ValueError("metric label name exceeds the maximum length")
            if len(label_value) > self.max_label_value_length:
                raise ValueError(
                    f"metric label {label_name!r} exceeds the maximum value length"
                )
            normalized[label_name] = label_value
        return normalized
