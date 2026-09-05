from __future__ import annotations

import pytest

from agentic_rag_chatbot_enterprise_ready.backend.application_runtime import (
    ApplicationRequest,
    ApplicationResult,
    ApplicationRuntime,
    Capability,
)
from agentic_rag_chatbot_enterprise_ready.backend.reliability import Evidence


@pytest.mark.asyncio
async def test_question_journey_normalizes_routes_records_evidence_and_returns_trace() -> None:
    evidence = Evidence(
        source_id="doc-1",
        source_type="document",
        locator="page-2",
        metadata={"provider": "fixture"},
    )

    def answer(request: ApplicationRequest) -> ApplicationResult:
        assert request.question == "What is the policy?"
        return ApplicationResult(
            response_text="The policy is documented on page 2.",
            capability=Capability.QUESTION,
            metadata={"mode": "grounded"},
            evidence=(evidence,),
        )

    runtime = ApplicationRuntime({Capability.QUESTION: answer})
    execution = await runtime.execute(
        ApplicationRequest(question="  What   is the policy?  ", session_id="session-1", actor_id="actor-1")
    )

    assert execution.result.response_text.startswith("The policy")
    assert execution.result.run_id == execution.trace.run_id
    assert len(execution.trace.evidence) == 1
    assert execution.trace.session_id == "session-1"
    assert execution.trace.actor_id == "actor-1"
    assert execution.trace.outcome == "success"
    assert [event.phase for event in execution.trace.events][:2] == ["execution", "normalization"]
    assert any(event.name == "capability.selected" for event in execution.trace.events)
    assert any(event.phase == "response" for event in execution.trace.events)


@pytest.mark.asyncio
async def test_explicit_upload_capability_does_not_require_question() -> None:
    seen: list[Capability] = []

    async def upload(request: ApplicationRequest) -> str:
        seen.append(Capability.UPLOAD)
        assert request.payload["file_id"] == "file-1"
        return "Upload accepted."

    runtime = ApplicationRuntime({Capability.UPLOAD: upload})
    execution = await runtime.execute(
        ApplicationRequest(capability=Capability.UPLOAD, payload={"file_id": "file-1"})
    )

    assert seen == [Capability.UPLOAD]
    assert execution.result.capability is Capability.UPLOAD
    assert execution.result.response_text == "Upload accepted."


def test_default_question_decision_is_deterministic() -> None:
    decision = ApplicationRuntime.decide(ApplicationRequest(question="hello"))

    assert decision.capability is Capability.QUESTION
    assert decision.reason == "default question capability"


def test_missing_question_is_rejected_without_implicit_ai_routing() -> None:
    with pytest.raises(ValueError, match="question is required"):
        ApplicationRuntime.decide(ApplicationRequest())


def test_invalid_capability_type_is_rejected() -> None:
    with pytest.raises(TypeError, match="capability must be a Capability"):
        ApplicationRuntime.decide(ApplicationRequest(capability="upload"))  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_handler_failure_is_recorded_before_error_is_re_raised() -> None:
    def failing(_: ApplicationRequest) -> str:
        raise RuntimeError("provider unavailable")

    runtime = ApplicationRuntime({Capability.QUESTION: failing})

    with pytest.raises(RuntimeError, match="provider unavailable"):
        await runtime.execute(ApplicationRequest(question="hello"))

    traces = list(runtime._observability.store.recent(1))
    assert traces[0].outcome == "error"
    assert any(event.name == "execution.error" for event in traces[0].events)
