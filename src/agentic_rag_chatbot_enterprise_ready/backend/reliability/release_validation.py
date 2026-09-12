"""Deterministic release-validation evidence contract."""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import re


class ValidationStatus(StrEnum):
    """Allowed status for one release validation gate."""

    PASS = "pass"
    FAIL = "fail"
    BLOCKED = "blocked"
    NOT_RUN = "not_run"


_MAX_TEXT = 256
_SHA = re.compile(r"^[0-9a-fA-F]{40}$")


@dataclass(frozen=True, slots=True)
class ValidationGate:
    """Bounded result for one named deployment/release gate."""

    name: str
    status: ValidationStatus
    detail: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("gate name must be a non-empty string")
        if len(self.name) > _MAX_TEXT:
            raise ValueError("gate name exceeds the maximum length")
        if not isinstance(self.status, ValidationStatus):
            raise TypeError("gate status must be a ValidationStatus")
        if not isinstance(self.detail, str):
            raise TypeError("gate detail must be a string")
        if len(self.detail) > _MAX_TEXT:
            raise ValueError("gate detail exceeds the maximum length")


@dataclass(frozen=True, slots=True)
class ReleaseValidationReport:
    """Immutable, bounded evidence summary for one release candidate."""

    release_id: str
    commit_sha: str
    gates: tuple[ValidationGate, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.release_id, str) or not self.release_id.strip():
            raise ValueError("release_id must be a non-empty string")
        if len(self.release_id) > _MAX_TEXT:
            raise ValueError("release_id exceeds the maximum length")
        if not isinstance(self.commit_sha, str) or not _SHA.fullmatch(self.commit_sha):
            raise ValueError("commit_sha must be a 40-character hexadecimal SHA")
        if len(self.gates) > 32:
            raise ValueError("release validation gate limit exceeded")
        if any(not isinstance(gate, ValidationGate) for gate in self.gates):
            raise TypeError("gates must contain ValidationGate instances")

    @property
    def passed(self) -> bool:
        """Return whether every recorded gate passed and at least one gate exists."""
        return bool(self.gates) and all(gate.status is ValidationStatus.PASS for gate in self.gates)

    @property
    def blocked(self) -> bool:
        """Return whether any release gate remains blocked or unexecuted."""
        return any(
            gate.status in {ValidationStatus.BLOCKED, ValidationStatus.NOT_RUN}
            for gate in self.gates
        )


def validate_release_report(report: ReleaseValidationReport) -> ReleaseValidationReport:
    """Validate and return an immutable release-validation report."""
    if not isinstance(report, ReleaseValidationReport):
        raise TypeError("report must be a ReleaseValidationReport")
    return report
