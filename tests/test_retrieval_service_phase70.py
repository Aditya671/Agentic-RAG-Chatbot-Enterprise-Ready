from __future__ import annotations

import pytest

from agentic_rag_chatbot_enterprise_ready.backend.reliability import Evidence, RetrievalService


class FakeAgent:
    async def get_response(self, question: str):
        assert question == "What does the policy say?"
        return {
            "response_text": "The policy requires documented approval.",
            "response_metadata": {"sources": [{"id": "policy.pdf", "type": "uploaded_document", "page": 4, "score": 0.91, "content": "approval details"}]},
        }


@pytest.mark.asyncio
async def test_retrieval_service_preserves_answer_and_source_metadata():
    result = await RetrievalService(FakeAgent()).answer("What does the policy say?")
    assert result.response_text == "The policy requires documented approval."
    assert result.grounded is True
    assert result.evidence[0] == Evidence(
        source_id="policy.pdf", source_type="uploaded_document", locator="4", relevance=0.91,
        metadata={"id": "policy.pdf", "type": "uploaded_document", "page": 4, "score": 0.91},
    )
    assert "content" not in result.evidence[0].metadata


@pytest.mark.asyncio
async def test_retrieval_service_rejects_empty_answers():
    class EmptyAgent:
        async def get_response(self, question: str):
            return {"response_text": "", "response_metadata": []}

    with pytest.raises(ValueError, match="no response_text"):
        await RetrievalService(EmptyAgent()).answer("question")


@pytest.mark.asyncio
async def test_retrieval_service_reports_missing_evidence_without_fabricating_it():
    class UngroundedAgent:
        async def get_response(self, question: str):
            return {"response_text": "No supporting material was retrieved.", "response_metadata": []}

    result = await RetrievalService(UngroundedAgent()).answer("question")
    assert result.grounded is False
    assert result.evidence == ()
