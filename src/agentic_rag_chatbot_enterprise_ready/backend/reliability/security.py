"""Provider-neutral security contracts for application execution."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Mapping


@dataclass(frozen=True, slots=True)
class SecurityPrincipal:
    """Authenticated actor identity presented by an application adapter."""

    actor_id: str
    session_id: str
    tenant_id: str | None = None
    roles: frozenset[str] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        if not self.actor_id.strip():
            raise ValueError("actor_id must be non-empty")
        if not self.session_id.strip():
            raise ValueError("session_id must be non-empty")
        if self.tenant_id is not None and not self.tenant_id.strip():
            raise ValueError("tenant_id must be non-empty when provided")
        if any(not role.strip() for role in self.roles):
            raise ValueError("roles must contain non-empty strings")


@dataclass(frozen=True, slots=True)
class SecurityPolicy:
    """Deterministic capability and upload policy."""

    allowed_capabilities: frozenset[str] = frozenset(
        {"question", "upload", "index_status"}
    )
    required_roles: Mapping[str, frozenset[str]] = field(default_factory=dict)
    allowed_upload_extensions: frozenset[str] = frozenset({".pdf", ".txt", ".csv"})
    max_upload_size_bytes: int = 10 * 1024 * 1024

    def __post_init__(self) -> None:
        if self.max_upload_size_bytes < 1:
            raise ValueError("max_upload_size_bytes must be positive")

    def authorize(self, principal: SecurityPrincipal, capability: str) -> None:
        if capability not in self.allowed_capabilities:
            raise PermissionError(f"capability is not allowed: {capability}")
        required = self.required_roles.get(capability, frozenset())
        if required and not required.intersection(principal.roles):
            raise PermissionError(
                f"principal is not authorized for capability: {capability}"
            )

    def validate_uploads(self, uploads: Iterable[Mapping[str, object]]) -> None:
        for upload in uploads:
            name = upload.get("name")
            content = upload.get("content")
            if not isinstance(name, str) or not name.strip():
                raise ValueError("upload name must be a non-empty string")
            name = name.strip()
            if "\x00" in name or name in {".", ".."} or "/" in name or "\\" in name:
                raise ValueError("upload name must be a basename without path separators")
            extension = "." + name.rsplit(".", 1)[-1].lower() if "." in name else ""
            if extension not in self.allowed_upload_extensions:
                raise ValueError(f"unsupported upload extension: {extension or '<none>'}")
            if not isinstance(content, (bytes, bytearray)):
                raise TypeError("upload content must be bytes")
            if len(content) > self.max_upload_size_bytes:
                raise ValueError("upload exceeds the configured size limit")


def principal_from_request(
    actor_id: str | None,
    session_id: str | None,
    *,
    tenant_id: str | None = None,
    roles: Iterable[str] = (),
) -> SecurityPrincipal:
    if not actor_id or not session_id:
        raise PermissionError("authenticated actor and session identity are required")
    return SecurityPrincipal(
        actor_id=str(actor_id),
        session_id=str(session_id),
        tenant_id=str(tenant_id) if tenant_id else None,
        roles=frozenset(str(role) for role in roles),
    )
