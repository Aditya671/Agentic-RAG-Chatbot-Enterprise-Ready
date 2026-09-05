from dataclasses import dataclass

import pytest

from agentic_rag_chatbot_enterprise_ready.backend.application_runtime import (
    ApplicationExecution,
    ApplicationRequest,
    ApplicationResult,
    Capability,
)
from agentic_rag_chatbot_enterprise_ready.backend.reliability import Evidence
from agentic_rag_chatbot_enterprise_ready.frontend.application_surface import (
    ApplicationSurface,
    present_execution,
    present_history,
)


@dataclass(frozen=True)
class Message:
    message_id: str = "m1"
    conversation_id: str = "c1"
    actor_id: str = "a1"
    role: str = "user"
    content: str = "hello"
    created_at: str = "2026-01-01T00:00:00+00:00"
    run_id: str | None = "r1"
    metadata: dict = None

    def __post_init__(self):
        if self.metadata is None:
            object.__setattr__(self, "metadata", {})


class FakeRuntime:
    def __init__(self):
        self.requests = []

    async def execute(self, request):
        self.requests.append(request)
        return ApplicationExecution(
            result=ApplicationResult(
                response_text="grounded answer",
                capability=request.capability,
                metadata={"status": "ok"},
                evidence=(Evidence(source="policy.pdf", locator="p1", metadata={"score": 0.9}),),
                run_id="run-1",
                conversation_id=request.conversation_id,
            ),
            trace=None,
        )

    async def history(self, conversation_id, actor_id, limit=100):
        return [Message()]


@pytest.mark.asyncio
async def test_question_surface_preserves_runtime_identity_and_evidence():
    runtime = FakeRuntime()
    surface = ApplicationSurface(runtime)

    view = await surface.question(
        "What is the policy?",
        session_id="s1",
        actor_id="a1",
        conversation_id="c1",
    )

    assert view.response_text == "grounded answer"
    assert view.run_id == "run-1"
    assert view.conversation_id == "c1"
    assert view.evidence[0].source == "policy.pdf"
    assert runtime.requests[0].capability is Capability.QUESTION


@pytest.mark.asyncio
async def test_upload_surface_uses_canonical_upload_capability():
    runtime = FakeRuntime()
    surface = ApplicationSurface(runtime)

    await surface.upload([{"name": "policy.pdf", "content": b"data"}], session_id="s1", actor_id="a1")

    assert runtime.requests[0].capability is Capability.UPLOAD
    assert runtime.requests[0].payload["uploaded_files"][0]["name"] == "policy.pdf"


@pytest.mark.asyncio
async def test_status_surface_preserves_task_identity():
    runtime = FakeRuntime()
    surface = ApplicationSurface(runtime)

    view = await surface.index_status("task-7", session_id="s1", actor_id="a1")

    assert view.capability == Capability.INDEX_STATUS.value
    assert runtime.requests[0].payload == {"task_id": "task-7"}


@pytest.mark.asyncio
async def test_history_surface_projects_provider_neutral_messages():
    runtime = FakeRuntime()
    surface = ApplicationSurface(runtime)

    view = await surface.history("c1", actor_id="a1")

    assert view.to_dict()["conversation_id"] == "c1"
    assert view.messages[0]["message_id"] == "m1"
    assert view.messages[0]["run_id"] == "r1"


def test_present_execution_does_not_drop_evidence():
    execution = ApplicationExecution(
        result=ApplicationResult(
            response_text="answer",
            capability=Capability.QUESTION,
            evidence=(Evidence(source="source", locator="p2", metadata={"kind": "pdf"}),),
            run_id="run-2",
        ),
        trace=None,
    )
    view = present_execution(execution)
    assert view.to_dict()["evidence"][0]["locator"] == "p2"


def test_present_history_is_serializable():
    view = present_history([Message()], "c1")
    payload = view.to_dict()
    assert payload["messages"][0]["role"] == "user"
