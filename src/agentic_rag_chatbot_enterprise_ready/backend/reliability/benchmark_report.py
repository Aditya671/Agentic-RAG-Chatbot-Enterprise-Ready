"""Deterministic reporting and comparison for architecture benchmark runs."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable

from .benchmark import ArchitectureAggregate, ArchitectureBenchmark, ArchitectureBenchmarkRun, ArchitectureSpec


@dataclass(frozen=True, slots=True)
class ArchitectureComparison:
    """Pairwise metric deltas between two architecture aggregates."""

    baseline: ArchitectureSpec
    candidate: ArchitectureSpec
    pass_rate_delta: float
    grounding_coverage_delta: float
    retrieval_relevance_delta: float
    latency_ms_delta: float
    model_calls_delta: float
    tool_calls_delta: float
    retrieval_calls_delta: float
    input_tokens_delta: float
    output_tokens_delta: float
    estimated_model_cost_delta: float
    error_rate_delta: float
    provenance_completeness_delta: float
    repeatability_rate_delta: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class BenchmarkReport:
    """Serializable report containing run metrics, aggregates, and pairwise deltas."""

    runs: tuple[ArchitectureBenchmarkRun, ...]
    aggregates: tuple[ArchitectureAggregate, ...]
    comparisons: tuple[ArchitectureComparison, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "runs": [
                {
                    "scenario_id": run.scenario_id,
                    "architecture": asdict(run.architecture),
                    "run_index": run.run_index,
                    "metrics": asdict(run.metrics),
                }
                for run in self.runs
            ],
            "aggregates": [asdict(aggregate) for aggregate in self.aggregates],
            "comparisons": [comparison.to_dict() for comparison in self.comparisons],
        }


class BenchmarkReporter:
    """Build deterministic benchmark reports without inventing a composite score."""

    @staticmethod
    def build(results: Iterable[ArchitectureBenchmarkRun]) -> BenchmarkReport:
        runs = tuple(results)
        aggregates = ArchitectureBenchmark.aggregate(runs)
        comparisons = BenchmarkReporter.compare(aggregates)
        return BenchmarkReport(runs=runs, aggregates=aggregates, comparisons=comparisons)

    @staticmethod
    def compare(aggregates: Iterable[ArchitectureAggregate]) -> tuple[ArchitectureComparison, ...]:
        values = tuple(aggregates)
        comparisons: list[ArchitectureComparison] = []
        for index, baseline in enumerate(values):
            for candidate in values[index + 1 :]:
                comparisons.append(BenchmarkReporter._comparison(baseline, candidate))
        return tuple(comparisons)

    @staticmethod
    def _comparison(
        baseline: ArchitectureAggregate, candidate: ArchitectureAggregate
    ) -> ArchitectureComparison:
        return ArchitectureComparison(
            baseline=baseline.architecture,
            candidate=candidate.architecture,
            pass_rate_delta=candidate.pass_rate - baseline.pass_rate,
            grounding_coverage_delta=candidate.average_grounding_coverage - baseline.average_grounding_coverage,
            retrieval_relevance_delta=candidate.average_retrieval_relevance - baseline.average_retrieval_relevance,
            latency_ms_delta=candidate.average_latency_ms - baseline.average_latency_ms,
            model_calls_delta=candidate.average_model_calls - baseline.average_model_calls,
            tool_calls_delta=candidate.average_tool_calls - baseline.average_tool_calls,
            retrieval_calls_delta=candidate.average_retrieval_calls - baseline.average_retrieval_calls,
            input_tokens_delta=candidate.average_input_tokens - baseline.average_input_tokens,
            output_tokens_delta=candidate.average_output_tokens - baseline.average_output_tokens,
            estimated_model_cost_delta=candidate.average_estimated_model_cost - baseline.average_estimated_model_cost,
            error_rate_delta=candidate.error_rate - baseline.error_rate,
            provenance_completeness_delta=candidate.average_provenance_completeness - baseline.average_provenance_completeness,
            repeatability_rate_delta=candidate.repeatability_rate - baseline.repeatability_rate,
        )
