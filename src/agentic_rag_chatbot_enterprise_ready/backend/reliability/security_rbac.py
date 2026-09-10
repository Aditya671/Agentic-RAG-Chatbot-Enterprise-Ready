"""Deterministic configurable RBAC policy construction."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .security import SecurityPolicy


DEFAULT_ROLE_CAPABILITIES = {
    "reader": frozenset({"question", "index_status"}),
    "uploader": frozenset({"question", "upload", "index_status"}),
    "admin": frozenset({"question", "upload", "index_status"}),
}


def build_security_policy(
    settings: Mapping[str, Any] | None = None,
    *,
    audit_sink=None,
) -> SecurityPolicy:
    """Build a validated policy from a deployment configuration mapping.

    Expected shape::

        {"roles": {"reader": ["question"], "uploader": ["question", "upload"]}}

    An omitted mapping uses the conservative built-in role catalog. Unknown
    capabilities are rejected instead of silently expanding the attack surface.
    """
    source = dict(settings or {})
    raw_roles = source.get("roles")
    if raw_roles is None:
        role_capabilities = dict(DEFAULT_ROLE_CAPABILITIES)
    else:
        if not isinstance(raw_roles, Mapping) or not raw_roles:
            raise ValueError("security.rbac.roles must be a non-empty mapping")
        role_capabilities: dict[str, frozenset[str]] = {}
        for role, capabilities in raw_roles.items():
            role_name = str(role).strip()
            if not role_name:
                raise ValueError("security role names must be non-empty")
            if not isinstance(capabilities, (list, tuple, set, frozenset)):
                raise TypeError(f"capabilities for role {role_name!r} must be a sequence")
            normalized = frozenset(str(item).strip() for item in capabilities)
            if not normalized or any(not item for item in normalized):
                raise ValueError(f"capabilities for role {role_name!r} must be non-empty")
            role_capabilities[role_name] = normalized

    capabilities = frozenset(
        str(item).strip()
        for item in source.get(
            "allowed_capabilities",
            ("question", "upload", "index_status"),
        )
    )
    if not capabilities or any(not item for item in capabilities):
        raise ValueError("security.rbac.allowed_capabilities must be non-empty")

    unknown = sorted(
        capability
        for values in role_capabilities.values()
        for capability in values
        if capability not in capabilities
    )
    if unknown:
        raise ValueError(
            "security.rbac contains capabilities outside allowed_capabilities: "
            + ", ".join(dict.fromkeys(unknown))
        )

    required_roles = {
        capability: frozenset(
            role for role, role_capabilities_set in role_capabilities.items()
            if capability in role_capabilities_set
        )
        for capability in capabilities
    }

    if any(not roles for roles in required_roles.values() if capabilities):
        # Every configured capability must have an explicit granting role.
        missing = sorted(
            capability for capability, roles in required_roles.items() if not roles
        )
        if missing:
            raise ValueError(
                "security.rbac has no granting role for capabilities: "
                + ", ".join(missing)
            )

    return SecurityPolicy(
        allowed_capabilities=capabilities,
        required_roles=required_roles,
        audit_sink=audit_sink,
    )
