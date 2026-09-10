import pytest

from agentic_rag_chatbot_enterprise_ready.backend.reliability.security import SecurityPrincipal
from agentic_rag_chatbot_enterprise_ready.backend.reliability.security_rbac import (
    build_security_policy,
)


def test_default_roles_are_conservative_and_deterministic() -> None:
    policy = build_security_policy()

    policy.authorize(
        SecurityPrincipal("reader-1", "session-1", roles=frozenset({"reader"})),
        "question",
    )
    with pytest.raises(PermissionError):
        policy.authorize(
            SecurityPrincipal("reader-1", "session-1", roles=frozenset({"reader"})),
            "upload",
        )


def test_configured_role_can_grant_upload() -> None:
    policy = build_security_policy(
        {
            "roles": {
                "analyst": ["question", "index_status"],
                "ingestor": ["question", "upload", "index_status"],
            }
        }
    )

    policy.authorize(
        SecurityPrincipal("actor-1", "session-1", roles=frozenset({"ingestor"})),
        "upload",
    )
    with pytest.raises(PermissionError):
        policy.authorize(
            SecurityPrincipal("actor-2", "session-2", roles=frozenset({"analyst"})),
            "upload",
        )


def test_rbac_rejects_unknown_capability() -> None:
    with pytest.raises(ValueError, match="outside allowed_capabilities"):
        build_security_policy(
            {"roles": {"reader": ["question", "delete_all_threads"]}}
        )


def test_rbac_requires_each_allowed_capability_to_have_a_role() -> None:
    with pytest.raises(ValueError, match="no granting role"):
        build_security_policy(
            {
                "allowed_capabilities": ["question", "upload"],
                "roles": {"reader": ["question"]},
            }
        )


def test_rbac_rejects_empty_role_configuration() -> None:
    with pytest.raises(ValueError):
        build_security_policy({"roles": {}})
