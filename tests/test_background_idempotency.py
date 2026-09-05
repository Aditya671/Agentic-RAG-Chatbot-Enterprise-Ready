import pytest

from agentic_rag_chatbot_enterprise_ready.backend.reliability import (
    ArtifactIdentity,
    BackgroundTask,
    FailureClass,
    InMemoryArtifactIdempotencyStore,
    InMemoryBackgroundTaskStore,
    TaskStatus,
    artifact_identities_from_paths,
    artifact_idempotency_key,
    build_artifact_identity,
    classify_failure,
    normalize_artifact_filename,
)


SHA256 = "A" * 64


def test_artifact_identity_is_deterministic():
    first = build_artifact_identity("/tmp/policy.pdf", SHA256)
    second = build_artifact_identity("policy.pdf", SHA256.lower())

    assert first == second
    assert len(first.artifact_id) == 64
    assert first.checksum == SHA256.lower()


def test_artifact_identity_changes_when_content_changes():
    first = build_artifact_identity("policy.pdf", "a" * 64)
    second = build_artifact_identity("policy.pdf", "b" * 64)
    assert first.artifact_id != second.artifact_id


def test_artifact_identity_changes_when_logical_filename_changes():
    first = build_artifact_identity("policy.pdf", SHA256)
    second = build_artifact_identity("pricing.pdf", SHA256)
    assert first.artifact_id != second.artifact_id


def test_filename_normalization_does_not_use_directory_as_identity():
    assert normalize_artifact_filename("uploads\\2026/policy.pdf") == "policy.pdf"


def test_idempotency_key_is_operation_and_scope_scoped():
    artifact = build_artifact_identity("policy.pdf", SHA256)
    index_key = artifact_idempotency_key(artifact, scope="portfolio")
    delete_key = artifact_idempotency_key(artifact, operation="delete", scope="portfolio")
    other_index = artifact_idempotency_key(artifact, scope="capitalraising")
    assert index_key != delete_key
    assert index_key != other_index
    assert index_key.endswith(artifact.artifact_id)


def test_artifact_identities_require_hashes():
    with pytest.raises(ValueError, match="missing checksum"):
        artifact_identities_from_paths(["policy.pdf"], {})


def test_failure_classification_is_deterministic():
    assert classify_failure(ValueError("bad upload")) is FailureClass.TERMINAL
    assert classify_failure(TypeError("bad payload")) is FailureClass.TERMINAL
    assert classify_failure(FileNotFoundError("missing")) is FailureClass.TERMINAL
    assert classify_failure(PermissionError("denied")) is FailureClass.TERMINAL
    assert classify_failure(RuntimeError("broker unavailable")) is FailureClass.RETRYABLE


@pytest.mark.asyncio
async def test_task_store_preserves_task_correlation():
    store = InMemoryBackgroundTaskStore()
    task = BackgroundTask(
        task_id="celery-123",
        artifact_ids=("artifact-1",),
        status=TaskStatus.RUNNING,
        run_id="run-123",
    )

    await store.put(task)
    assert await store.get("celery-123") == task


@pytest.mark.asyncio
async def test_idempotency_store_returns_prior_result():
    store = InMemoryArtifactIdempotencyStore()
    result = {"status": "completed", "indexed": ["policy.pdf"]}

    await store.put("v1:portfolio:index:artifact-1", result)
    assert await store.get("v1:portfolio:index:artifact-1") == result
    assert await store.get("v1:portfolio:index:missing") is None


def test_background_task_defaults_are_explicit():
    task = BackgroundTask(task_id="t1", artifact_ids=("a1",))
    assert task.status is TaskStatus.QUEUED
    assert task.attempt == 1
    assert task.error_class is None


def test_artifact_identity_is_frozen_contract():
    artifact = ArtifactIdentity("id", "policy.pdf", SHA256.lower())
    with pytest.raises(AttributeError):
        artifact.artifact_id = "other"
