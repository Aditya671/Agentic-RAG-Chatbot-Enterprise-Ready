"""Deterministic release identity and validation contracts."""
from __future__ import annotations

from dataclasses import dataclass
import re


_SHA256 = re.compile(r"^[0-9a-fA-F]{64}$")
_MAX_TEXT = 128


@dataclass(frozen=True, slots=True)
class ReleaseManifest:
    """Immutable release record for deployment and rollback evidence."""

    release_id: str
    commit_sha: str
    image_digest: str
    config_version: str
    created_at: str

    def __post_init__(self) -> None:
        for name, value in (
            ("release_id", self.release_id),
            ("commit_sha", self.commit_sha),
            ("image_digest", self.image_digest),
            ("config_version", self.config_version),
            ("created_at", self.created_at),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")
            if len(value) > _MAX_TEXT:
                raise ValueError(f"{name} exceeds the maximum length")
        if not re.fullmatch(r"[0-9a-fA-F]{40}", self.commit_sha):
            raise ValueError("commit_sha must be a 40-character hexadecimal SHA")
        digest = self.image_digest.strip()
        if digest.startswith("sha256:"):
            digest = digest[7:]
        if not _SHA256.fullmatch(digest):
            raise ValueError("image_digest must contain a SHA-256 digest")


def validate_release_manifest(manifest: ReleaseManifest) -> ReleaseManifest:
    """Validate an immutable release record before promotion or rollback."""
    if not isinstance(manifest, ReleaseManifest):
        raise TypeError("manifest must be a ReleaseManifest")
    return manifest
