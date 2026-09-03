from backend.orchestration import AgentResponse, AgentRuntimeBoundary, RetrievalConfig


def test_orchestration_exports_are_stable() -> None:
    assert AgentResponse.__name__ == "AgentResponse"
    assert AgentRuntimeBoundary.__name__ == "AgentRuntimeBoundary"
    assert RetrievalConfig.__name__ == "RetrievalConfig"
