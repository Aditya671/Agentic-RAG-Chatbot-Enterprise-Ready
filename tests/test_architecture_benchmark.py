from __future__ import annotations

from dataclasses import dataclass

import pytest

from agentic_rag_chatbot_enterprise_ready.backend.reliability import (
    ArchitectureBenchmark,
    ArchitectureSpec,
    BenchmarkContext,
    Evidence,
    ExecutionEvent,
    HarnessCase,
)


@dataclass
class FakeArchitecture:
    spec: ArchitectureSpec
    tool_calls: int
    input_tokens: int = 100
    output_tokens: int = 25
    estimated_cost: float = 0.01

    async def execute(self, context: BenchmarkContext):
        evidence = context.available_evidence[:1]
        events = [
            ExecutionEvent(name="retrieval", phase="retrieval", attributes={"retrieved": 1}),
            ExecutionEvent(
                name="model.call",
                phase="model",
                attributes={
                    "input_tokens": self.input_tokens,
                    "output_tokens": self.output_tokens,
                    "estimated_cost": self.estimated_cost,
                },
            ),
        ]
        events.extend(ExecutionEvent(name="tool.call", phase="tool") for _ in range(self.tool_calls))
        return {"response_text": "revenue increased", "evidence": evidence, "events": events}


@pytest.mark.asyncio
async def test_benchmark_runs_architectures_against_same_case_and_evidence() -> None:
    evidence = Evidence(source_id="annual-report", source_type="document", relevance=0.9)
    context = BenchmarkContext(
        HarnessCase(
            case_id="revenue-001",
            question="Did revenue increase?",
            expected_text_contains=("revenue increased",),
            expected_evidence_source_ids=("annual-report",),
        ),
        available_evidence=(evidence,),
    )
    architectures = (
        FakeArchitecture(ArchitectureSpec("direct-rag", "1"), 0),
        FakeArchitecture(ArchitectureSpec("tool-aware", "1"), 2),
    )

    benchmark = ArchitectureBenchmark()
    results = await benchmark.run((context,), architectures)
    assert len(results) == 2
    assert all(result.metrics.passed for result in results)
    assert all(result.metrics.grounding_coverage == 1.0 for result in results)
    assert results[0].metrics.tool_calls == 0
    assert results[1].metrics.tool_calls == 2
    assert results[0].metrics.input_tokens == 100
    assert results[0].metrics.output_tokens == 25
    assert results[0].metrics.estimated_model_cost == 0.01
    assert all(result.metrics.provenance_completeness == 1.0 for result in results)

    aggregates = benchmark.aggregate(results)
    assert {item.architecture.architecture_id for item in aggregates} == {"direct-rag", "tool-aware"}


@pytest.mark.asyncio
async def test_benchmark_rejects_evidence_outside_shared_fixture() -> None:
    context = BenchmarkContext(
        HarnessCase("case-1", "question", expected_text_contains=("answer",)),
        available_evidence=(Evidence("allowed", "document"),),
    )

    @dataclass
    class BadArchitecture:
        spec: ArchitectureSpec = ArchitectureSpec("bad", "1")

        async def execute(self, context: BenchmarkContext):
            return {"response_text": "answer", "evidence": (Evidence("not-allowed", "document"),)}

    results = await ArchitectureBenchmark().run((context,), (BadArchitecture(),))
    assert results[0].harness_result.outcome == "error"
    assert "outside benchmark fixture" in results[0].harness_result.failures[0]


@pytest.mark.asyncio
async def test_repeated_runs_measure_response_repeatability() -> None:
    context = BenchmarkContext(HarnessCase("case-1", "question", expected_text_contains=("answer",)))

    @dataclass
    class StableArchitecture:
        spec: ArchitectureSpec = ArchitectureSpec("stable", "1")

        async def execute(self, context: BenchmarkContext):
            return {"response_text": "answer"}

    results = await ArchitectureBenchmark().run((context,), (StableArchitecture(),), repetitions=3)
    aggregate = ArchitectureBenchmark.aggregate(results)[0]
    assert aggregate.repeatability_rate == 1.0


def test_benchmark_requires_unique_architecture_identity() -> None:
    context = BenchmarkContext(HarnessCase("case-1", "question"))
    architecture = FakeArchitecture(ArchitectureSpec("same", "1"), 0)
    with pytest.raises(ValueError, match="architecture identity"):
        import asyncio

        asyncio.run(ArchitectureBenchmark().run((context,), (architecture, architecture)))
