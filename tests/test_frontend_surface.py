from dataclasses import dataclass
import pytest
from agentic_rag_chatbot_enterprise_ready.backend.application_runtime import ApplicationExecution, ApplicationResult, Capability
from agentic_rag_chatbot_enterprise_ready.backend.reliability import Evidence
from agentic_rag_chatbot_enterprise_ready.frontend.application_surface import ApplicationSurface, present_execution, present_history
@dataclass(frozen=True)
class Message:
    message_id: str = "m1"
    conversation_id: str = "c1"
    actor_id: str = "a1"
    role: str = "user"
    content: str = "hello"
    created_at: str = "2026-01-01T00:00:00+00:00"
    run_id: str | None = "r1"
    metadata: dict | None = None
class FakeRuntime:
    def __init__(self): self.requests=[]
    async def execute(self, request):
        self.requests.append(request)
        return ApplicationExecution(ApplicationResult("grounded answer", request.capability, {"status":"ok"}, (Evidence("policy.pdf", "p1", {"score":0.9}),), "run-1", request.conversation_id), None)
    async def history(self, conversation_id, actor_id, limit=100): return [Message()]
@pytest.mark.asyncio
async def test_question_surface_preserves_identity_and_evidence():
    runtime=FakeRuntime(); view=await ApplicationSurface(runtime).question("What is the policy?", session_id="s1", actor_id="a1", conversation_id="c1")
    assert view.run_id=="run-1" and view.conversation_id=="c1" and view.evidence[0].source=="policy.pdf"
    assert runtime.requests[0].capability is Capability.QUESTION
@pytest.mark.asyncio
async def test_upload_surface_uses_canonical_capability():
    runtime=FakeRuntime(); await ApplicationSurface(runtime).upload([{"name":"policy.pdf","content":b"data"}], session_id="s1", actor_id="a1")
    assert runtime.requests[0].capability is Capability.UPLOAD
@pytest.mark.asyncio
async def test_status_surface_preserves_task_identity():
    runtime=FakeRuntime(); view=await ApplicationSurface(runtime).index_status("task-7", session_id="s1", actor_id="a1")
    assert view.capability==Capability.INDEX_STATUS.value and runtime.requests[0].payload=={"task_id":"task-7"}
@pytest.mark.asyncio
async def test_history_surface_projects_messages():
    view=await ApplicationSurface(FakeRuntime()).history("c1", actor_id="a1")
    assert view.to_dict()["messages"][0]["message_id"]=="m1"
def test_present_execution_does_not_drop_evidence():
    execution=ApplicationExecution(ApplicationResult("answer", Capability.QUESTION, evidence=(Evidence("source","p2",{"kind":"pdf"}),), run_id="r2"), None)
    assert present_execution(execution).to_dict()["evidence"][0]["locator"]=="p2"
def test_present_history_is_serializable():
    assert present_history([Message()], "c1").to_dict()["messages"][0]["role"]=="user"
