"""Deterministic local preflight checks for Phase 77 release candidates."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .backend.runtime import run_startup_checks


_SECRET_FILENAMES = {".env", "config.yml"}
_REQUIRED_FILES = ("pyproject.toml", "Dockerfile", "config.example.yml")


@dataclass(frozen=True, slots=True)
class PreflightCheck:
    """One bounded release-preflight result."""

    name: str
    passed: bool
    detail: str


@dataclass(frozen=True, slots=True)
class PreflightReport:
    """Deterministic aggregate of local Phase 77 release checks."""

    checks: tuple[PreflightCheck, ...]

    @property
    def passed(self) -> bool:
        return all(check.passed for check in self.checks)


def run_release_preflight(root: str | Path) -> PreflightReport:
    """Run local release checks without making cloud calls."""
    root_path = Path(root).resolve()
    checks: list[PreflightCheck] = []

    for relative in _REQUIRED_FILES:
        path = root_path / relative
        checks.append(
            PreflightCheck(
                name=f"file:{relative}",
                passed=path.is_file(),
                detail="present" if path.is_file() else "missing",
            )
        )

    unsafe = tuple(sorted(_iter_secret_files(root_path)))
    checks.append(
        PreflightCheck(
            name="secret-file-hygiene",
            passed=not unsafe,
            detail="clean" if not unsafe else ", ".join(unsafe),
        )
    )

    for name, passed, detail in run_startup_checks():
        checks.append(PreflightCheck(name=f"startup:{name}", passed=passed, detail=detail))

    return PreflightReport(checks=tuple(checks))


def _iter_secret_files(root: Path) -> Iterable[str]:
    """Return forbidden local secret/config filenames outside ignored directories."""
    excluded = {".git", ".venv", "__pycache__", "node_modules", "dist", "build"}
    for path in root.rglob("*"):
        if not path.is_file() or any(part in excluded for part in path.parts):
            continue
        if path.name in _SECRET_FILENAMES:
            yield str(path.relative_to(root))
