from __future__ import annotations

import pytest

from agentic_rag_chatbot_enterprise_ready.backend.application_runtime import (
    ApplicationRequest,
    ApplicationRuntime,
    Capability,
)
from agentic_rag_chatbot_enterprise_ready.backend.reliability.security import SecurityPolicy


@pytest.mark.asyncio
async def test_security_policy_requires_authenticated_principal() -> None:
    calls = 0

    async def question(_: ApplicationRequest) -> str:
        nonlocal calls
        calls += 1
        return "ok"

    runtime = ApplicationRuntime(
        {Capability.QUESTION: question},
        security_policy=SecurityPolicy(),
    )

    with pytest.raises(PermissionError, match="authenticated actor and session identity"):
        await runtime.execute(ApplicationRequest(question="hello"))
    assert calls == 0


@pytest.mark.asyncio
async def test_security_policy_blocks_capability_before_handler_execution() -> None:
    calls = 0

    async def question(_: ApplicationRequest) -> str:
        nonlocal calls
        calls += 1
        return "ok"

    runtime = ApplicationRuntime(
        {Capability.QUESTION: question},
        security_policy=SecurityPolicy(allowed_capabilities=frozenset({"upload"})),
    )

    with pytest.raises(PermissionError, match="capability is not allowed"):
        await runtime.execute(
            ApplicationRequest(
                question="hello",
                actor_id="actor-1",
                session_id="session-1",
            )
        )
    assert calls == 0


@pytest.mark.asyncio
async def test_security_policy_rejects_unsafe_upload_before_handler_execution() -> None:
    calls = 0

    async def upload(_: ApplicationRequest) -> str:
        nonlocal calls
        calls += 1
        return "accepted"

    runtime = ApplicationRuntime(
        {Capability.UPLOAD: upload},
        security_policy=SecurityPolicy(),
    )

    with pytest.raises(ValueError, match="unsupported upload extension"):
        await runtime.execute(
            ApplicationRequest(
                capability=Capability.UPLOAD,
                actor_id="actor-1",
                session_id="session-1",
                payload={"uploaded_files": [{"name": "payload.exe", "content": b"x"}]},
            )
        )
    assert calls == 0
