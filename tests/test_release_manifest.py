import pytest

from agentic_rag_chatbot_enterprise_ready.backend.reliability import (
    ReleaseManifest,
    validate_release_manifest,
)


def _manifest() -> ReleaseManifest:
    return ReleaseManifest(
        release_id="release-2026-09-10.1",
        commit_sha="a" * 40,
        image_digest="sha256:" + "b" * 64,
        config_version="config-42",
        created_at="2026-09-10T05:15:00+00:00",
    )


def test_release_manifest_is_immutable_and_validated():
    manifest = _manifest()
    assert validate_release_manifest(manifest) is manifest
    with pytest.raises(AttributeError):
        manifest.release_id = "other"  # type: ignore[misc]


def test_release_manifest_rejects_invalid_commit_and_digest():
    with pytest.raises(ValueError, match="commit_sha"):
        ReleaseManifest("r1", "bad", "sha256:" + "b" * 64, "cfg", "now")
    with pytest.raises(ValueError, match="image_digest"):
        ReleaseManifest("r1", "a" * 40, "not-a-digest", "cfg", "now")


def test_release_manifest_contains_no_secret_fields():
    names = set(ReleaseManifest.__dataclass_fields__)  # type: ignore[attr-defined]
    assert not any("token" in name or "secret" in name or "password" in name for name in names)
