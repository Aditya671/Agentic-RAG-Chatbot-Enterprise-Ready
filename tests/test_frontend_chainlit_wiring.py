from pathlib import Path


APP_PATH = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "agentic_rag_chatbot_enterprise_ready"
    / "frontend"
    / "app.py"
)


def _source() -> str:
    return APP_PATH.read_text(encoding="utf-8")


def test_chainlit_status_action_is_scoped_and_routes_through_surface():
    source = _source()
    assert '@cl.action_callback("check_indexing_status")' in source
    assert 'action.payload.get("task_id")' in source
    assert '"indexing_task_ids"' in source
    assert "surface.index_status(" in source
    assert "cl.Action(" in source
    assert 'name="check_indexing_status"' in source


def test_upload_confirmation_exposes_server_created_task_id():
    source = _source()
    assert 'upload_view.metadata.get("task_id")' in source
    assert 'payload={"task_id": task_id}' in source
    assert "_remember_indexing_task_id(task_id)" in source


def test_resume_hydrates_application_history_without_prompt_injection():
    source = _source()
    assert "ChainlitConversationStore" in source
    assert "surface.history(" in source
    assert 'cl.user_session.set("application_history"' in source
    assert "conversation_id, _actor_id()" in source


def test_application_surface_is_persistence_aware_for_question_execution():
    source = _source()
    assert "conversation_store=conversation_store" in source
    assert "build_application_runtime(agent, conversation_store=conversation_store)" in source
    assert "conversation_store = ChainlitConversationStore(get_data_layer())" in source
