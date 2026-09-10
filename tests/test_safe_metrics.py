import pytest

from agentic_rag_chatbot_enterprise_ready.backend.reliability import (
    InMemoryMetrics,
    MetricSnapshot,
)


def test_counter_and_gauge_snapshots_are_deterministic():
    metrics = InMemoryMetrics()
    metrics.increment("requests.total", labels={"capability": "question"})
    metrics.increment("requests.total", labels={"capability": "question"})
    metrics.set_gauge("queue.depth", 3, labels={"worker": "default"})

    assert metrics.snapshot() == (
        MetricSnapshot(
            "queue.depth", "gauge", 3.0, {"worker": "default"}
        ),
        MetricSnapshot(
            "requests.total", "counter", 2.0, {"capability": "question"}
        ),
    )


def test_metric_name_and_label_bounds_are_enforced():
    metrics = InMemoryMetrics(max_labels_per_metric=1, max_label_value_length=4)
    with pytest.raises(ValueError):
        metrics.increment("requests total")
    with pytest.raises(ValueError):
        metrics.increment("requests", labels={"a": "1", "b": "2"})
    with pytest.raises(ValueError):
        metrics.increment("requests", labels={"a": "12345"})


def test_metric_type_is_stable_and_cardinality_is_bounded():
    metrics = InMemoryMetrics(max_metrics=1)
    metrics.increment("requests.total")
    with pytest.raises(ValueError):
        metrics.set_gauge("requests.total", 1)
    with pytest.raises(ValueError):
        metrics.increment("other.total")


def test_metric_values_must_be_finite_numeric():
    metrics = InMemoryMetrics()
    with pytest.raises(TypeError):
        metrics.increment("requests", value=True)
    with pytest.raises(ValueError):
        metrics.increment("requests", value=float("nan"))
