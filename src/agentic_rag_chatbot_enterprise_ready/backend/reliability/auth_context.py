"""Small provider-neutral authentication context helpers."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class AuthContext:
    """Minimal authenticated identity safe to propagate into application code."""

    actor_id: str
    tenant_id: str | None = None
    roles: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        if not self.actor_id.strip():
            raise ValueError("actor_id must be non-empty")
        if self.tenant_id is not None and not self.tenant_id.strip():
            raise ValueError("tenant_id must be non-empty when provided")
        if any(not role.strip() for role in self.roles):
            raise ValueError("roles must contain non-empty strings")


def extract_auth_context(user: Any) -> AuthContext:
    """Extract only non-secret identity attributes from a Chainlit user."""
    if user is None:
        raise PermissionError("authenticated user is required")

    metadata: Mapping[str, Any] = getattr(user, "metadata", {}) or {}
    actor_id = getattr(user, "identifier", None)
    if not isinstance(actor_id, str) or not actor_id.strip():
        raise PermissionError("authenticated actor identity is required")

    tenant_id = metadata.get("tenant_id")
    if tenant_id is not None:
        tenant_id = str(tenant_id)

    raw_roles = metadata.get("roles") or ()
    roles = frozenset(str(role) for role in raw_roles if str(role).strip())
    return AuthContext(actor_id=actor_id, tenant_id=tenant_id, roles=roles)
