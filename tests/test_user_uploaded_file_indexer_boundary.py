from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INDEXER = ROOT / "src/agentic_rag_chatbot_enterprise_ready/backend/indexer/user_uploaded_file_indexer.py"
HISTORICAL = ROOT / "src/agentic_rag_chatbot_enterprise_ready/backend/indexer/user_uploaded_file_indexer_upgraded.py"
LEGACY_TEST = ROOT / "src/agentic_rag_chatbot_enterprise_ready/backend/indexer/test_user_uploaded_file_indexer.py"
LEGACY_REPORT = ROOT / "src/agentic_rag_chatbot_enterprise_ready/backend/indexer/user_uploaded_file_indexer_upgrade_report.md"


def test_user_upload_indexer_has_one_maintained_implementation():
    source = INDEXER.read_text(encoding="utf-8")
    assert "class UserUploadedFileIndexer" in source
    assert "user_uploaded_file_indexer_upgraded" not in source
    assert HISTORICAL.exists() is False


def test_migration_artifacts_are_not_in_source_tree():
    assert LEGACY_TEST.exists() is False
    assert LEGACY_REPORT.exists() is False


def test_canonical_indexer_retains_worker_safe_boundaries():
    source = INDEXER.read_text(encoding="utf-8")
    assert "async def index_uploaded_files" in source
    assert "asyncio.to_thread" in source
    assert "_atomic_write_json" in source
    assert "compute_file_hash" in source


def test_reindex_decision_is_hash_and_version_aware():
    source = INDEXER.read_text(encoding="utf-8")
    assert "record.get(\"index_version\") != INDEX_VERSION" in source
    assert "record.get(\"hash\") != current_hash" in source


def test_celery_dependency_already_uses_canonical_import():
    tasks = (ROOT / "src/agentic_rag_chatbot_enterprise_ready/backend/tasks.py").read_text(
        encoding="utf-8"
    )
    assert "from backend.user_uploaded_file_indexer import UserUploadedFileIndexer" in tasks
    assert "user_uploaded_file_indexer_upgraded" not in tasks
