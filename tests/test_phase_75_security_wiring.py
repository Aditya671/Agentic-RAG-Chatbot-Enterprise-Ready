from pathlib import Path


APP_PATH = Path("src/agentic_rag_chatbot_enterprise_ready/frontend/app.py")


def test_chainlit_does_not_persist_oauth_token_or_raw_claims() -> None:
    source = APP_PATH.read_text(encoding="utf-8")
    assert 'metadata["id_token"]' not in source
    assert 'metadata["claims"]' not in source
    assert 'metadata["tenant"]' in source


def test_chainlit_constructs_security_policy_for_application_runtime() -> None:
    source = APP_PATH.read_text(encoding="utf-8")
    assert 'from backend.reliability.security import SecurityPolicy' in source
    assert 'security_policy=_security_policy()' in source
    assert 'required_roles={"upload": required_upload_roles}' in source


def test_chainlit_requires_authenticated_identity_before_agent_creation() -> None:
    source = APP_PATH.read_text(encoding="utf-8")
    guard = 'raise PermissionError("authenticated actor and session identity are required")'
    assert source.count(guard) >= 1
    assert '_actor_id()' in source


def test_security_policy_is_centralized_in_application_runtime() -> None:
    runtime_path = Path("src/agentic_rag_chatbot_enterprise_ready/backend/application_runtime.py")
    source = runtime_path.read_text(encoding="utf-8")
    assert "SecurityPolicy" in source
    assert "self._security_policy.authorize" in source
    assert "self._security_policy.validate_uploads" in source
