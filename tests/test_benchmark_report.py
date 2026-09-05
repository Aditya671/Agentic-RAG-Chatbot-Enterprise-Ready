from __future__ import annotations

from dataclasses import replace

from agentic_rag_chatbot_enterprise_ready.backend.reliability import (
    ArchitectureAggregate,
    ArchitectureComparison,
    ArchitectureSpec,
    BenchmarkReporter,
)


def _aggregate(architecture_id: str, pass_rate: float, latency: float) -> ArchitectureAggregate:
    return ArchitectureAggregate(
        architecture=ArchitectureSpec(architecture_id=architecture_id, version="1"),
        runs=2,
        pass_rate=pass_rate,
        average_grounding_coverage=0.8,
        average_retrieval_relevance=0.9,
        average_latency_ms=latency,
        average_model_calls=2.0,
        average_tool_calls=1.0,
        average_retrieval_calls=1.0,
        average_input_tokens=100.0,
        average_output_tokens=50.0,
        average_estimated_model_cost=0.01,
        error_rate=0.0,
        average_provenance_completeness=1.0,
        repeatability_rate=1.0,
    )


def test_compare_reports_metric_deltas_without_composite_score() -> None:
    baseline = _aggregate("direct-rag", 0.75, 200.0)
    candidate = _aggregate("agentic-rag", 1.0, 150.0)

    comparisons = BenchmarkReporter.compare((baseline, candidate))

    assert len(comparisons) == 1
    comparison = comparisons[0]
    assert isinstance(comparison, ArchitectureComparison)
    assert comparison.pass_rate_delta == 0.25
    assert comparison.latency_ms_delta == -50.0
    assert not hasattr(comparison, "score")


def test_report_is_serializable_and_preserves_run_metrics() -> None:
    aggregate = _aggregate("direct-rag", 1.0, 100.0)
    report = BenchmarkReporter.build(())
    assert report.aggregates == ()
    assert report.to_dict() == {"runs": [], "aggregates": [], "comparisons": []}

    comparison_report = BenchmarkReporter.build(())
    assert comparison_report.to_dict()["runs"] == []

    # Aggregate-only comparison remains available independently of raw runs.
    assert BenchmarkReporter.compare((aggregate,)) == ()
