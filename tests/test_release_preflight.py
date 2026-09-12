from pathlib import Path

from agentic_rag_chatbot_enterprise_ready.release_preflight import (
    run_release_preflight,
)


def test_release_preflight_passes_required_repository_assets(tmp_path: Path) -> None:
    for name in ("pyproject.toml", "Dockerfile", "config.example.yml"):
        (tmp_path / name).write_text("fixture", encoding="utf-8")

    report = run_release_preflight(tmp_path)

    assert report.checks[0].passed is True
    assert report.checks[1].passed is True
    assert report.checks[2].passed is True
    assert report.checks[3].passed is True
    assert report.passed is False  # startup imports are intentionally absent in a tiny fixture tree


def test_release_preflight_detects_forbidden_config_files(tmp_path: Path) -> None:
    for name in ("pyproject.toml", "Dockerfile", "config.example.yml"):
        (tmp_path / name).write_text("fixture", encoding="utf-8")
    (tmp_path / ".env").write_text("SECRET=redacted", encoding="utf-8")

    report = run_release_preflight(tmp_path)

    hygiene = next(check for check in report.checks if check.name == "secret-file-hygiene")
    assert hygiene.passed is False
    assert ".env" in hygiene.detail
