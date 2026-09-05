from pathlib import Path


APP = Path(__file__).parents[1] / "src" / "agentic_rag_chatbot_enterprise_ready" / "frontend" / "app.py"


def test_chainlit_message_callback_uses_application_surface_for_questions_and_uploads() -> None:
    source = APP.read_text(encoding="utf-8")
    assert "view = await _surface_question(surface, user_prompt, message)" in source
    assert "upload_view = await _surface_upload(surface, uploaded_files)" in source
    assert "await agentic_engine.run_agent_async(user_prompt)" not in source
    assert "await agentic_engine.upload_and_index_files(" not in source


def test_chainlit_evidence_renderer_consumes_application_view_evidence() -> None:
    source = APP.read_text(encoding="utf-8")
    assert "async def stream_answer_and_evidence(" in source
    assert "evidence = view.evidence" in source
    assert "_extract_citation_list(" not in source


def test_chainlit_identity_is_server_derived() -> None:
    source = APP.read_text(encoding="utf-8")
    assert "actor_id=_actor_id()" in source
    assert "session_id=str(cl.user_session.get(\"id\")" in source
    assert "conversation_id=_conversation_id(conversation_id)" in source
