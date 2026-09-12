import pytest

from agentic_rag_chatbot_enterprise_ready.backend.reliability import (
    ReleaseValidationReport,
    ValidationGate,
    ValidationStatus,
    validate_release_report,
)


def test_release_validation_report_passes_only_when_all_gates_pass():
    report = ReleaseValidationReport(
        release_id="rel-1",
        commit_sha="a" * 40,
        gates=(
            ValidationGate("preflight", ValidationStatus.PASS),
            ValidationGate("startup", ValidationStatus.PASS),
        ),
    )
    assert report.passed is True
    assert report.blocked is False
    assert validate_release_report(report) is report


def test_release_validation_report_tracks_blocked_and_not_run_gates():
    report = ReleaseValidationReport(
        release_id="rel-2",
        commit_sha="b" * 40,
        gates=(ValidationGate("cloud", ValidationStatus.BLOCKED),),
    )
    assert report.passed is False
    assert report.blocked is True


def test_release_validation_report_rejects_empty_or_invalid_identity():
    with pytest.raises(ValueError, match="release_id"):
        ReleaseValidationReport("", "c" * 40, ())
    with pytest.raises(ValueError, match="commit_sha"):
        ReleaseValidationReport("rel-3", "not-a-sha", ())


def test_release_validation_contract_bounds_gate_detail_and_count():
    with pytest.raises(ValueError, match="detail"):
        ValidationGate("startup", ValidationStatus.FAIL, "x" * 257)
    gates = tuple(
        ValidationGate(f"gate-{index}", ValidationStatus.NOT_RUN)
        for index in range(33)
    )
    with pytest.raises(ValueError, match="gate limit"):
        ReleaseValidationReport("rel-4", "d" * 40, gates)
