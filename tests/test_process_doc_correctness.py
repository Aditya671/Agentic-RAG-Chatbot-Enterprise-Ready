from __future__ import annotations

from pathlib import Path

import pytest

from backend.process_doc.orchestrator.hierarchical_indexer import HierarchicalIndexer
from backend.process_doc.orchestrator.hitl_queue import HITLQueueManager
from backend.process_doc.orchestrator.pipeline import DocumentDigitizationPipeline
from backend.process_doc.processors.classifier import DocumentClassifier
from backend.process_doc.processors.pii_redactor import PIIRedactor


class _Extractor:
    def __init__(self) -> None:
        self.calls = 0

    def extract_layout(self, path: Path) -> dict:
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("transient extraction failure")
        return {"text": "Invoice for Alice at alice@example.com", "confidence": 0.95}


class _OfficeExtractor:
    def process(self, path: Path) -> dict:
        return {"text": "Invoice for Alice at alice@example.com", "confidence": 0.95}


class _NoopMultiModal:
    def extract_and_describe_images(self, path: Path) -> list[dict]:
        return []


class _Classifier:
    def classify(self, text: str) -> dict:
        return {"document_type": "Invoice", "confidence": 0.9, "confidence_score": 0.9, "key_subjects": []}


class _Metadata:
    def extract_metadata(self, text: str) -> dict:
        return {"date": "Unknown", "organizations": [], "people": [], "document_summary": "test"}


class _Graph:
    def extract_graph_data(self, text: str) -> dict:
        return {"nodes": [], "relationships": []}


def test_failed_pipeline_attempt_remains_retryable(tmp_path: Path) -> None:
    document = tmp_path / "document.txt"
    document.write_text("retry me", encoding="utf-8")

    pipeline = DocumentDigitizationPipeline(db_path=str(tmp_path / "processed.db"))
    extractor = _Extractor()
    pipeline.azure_extractor = extractor
    pipeline.office_extractor = _OfficeExtractor()
    pipeline.multimodal_extractor = _NoopMultiModal()
    pipeline.classifier = _Classifier()
    pipeline.metadata_extractor = _Metadata()
    pipeline.graph_extractor = _Graph()

    first = __import__("asyncio").run(pipeline.process_document_async(document))
    second = __import__("asyncio").run(pipeline.process_document_async(document))

    assert first["status"] == "queued_for_review"
    assert second["status"] == "success"
    assert extractor.calls == 2


def test_hitl_resolution_is_single_use(tmp_path: Path) -> None:
    queue = HITLQueueManager(str(tmp_path / "hitl.db"))
    item_id = queue.enqueue(tmp_path / "document.txt", "manual review")

    assert queue.resolve_review(item_id, {"approved": True}) is True
    assert queue.resolve_review(item_id, {"approved": False}) is False
    assert queue.get_pending_reviews() == []


def test_pii_fallback_redacts_high_confidence_identifiers() -> None:
    redactor = PIIRedactor()
    result = redactor.redact("Contact alice@example.com or +1 212-555-0199")

    assert "alice@example.com" not in result
    assert "<EMAIL_ADDRESS>" in result


def test_classifier_exposes_pipeline_confidence_contract() -> None:
    classifier = DocumentClassifier()
    result = classifier.classify("ordinary text")

    assert 0.0 <= result["confidence"] <= 1.0
    assert result["confidence"] == result["confidence_score"]


def test_hierarchical_index_uses_typed_parent_child_relationships() -> None:
    indexer = HierarchicalIndexer()
    nodes = indexer.construct_hierarchy(
        "doc-1",
        "report.pdf",
        [{"page_num": 1, "text": "page", "tables": [{"value": 1}]}],
        {"source": "test"},
    )

    assert len(nodes) == 3
    parent, page, table = nodes
    assert page.parent_node is not None
    assert page.parent_node.node_id == parent.node_id
    assert table.parent_node is not None
    assert table.parent_node.node_id == page.node_id
    assert len(parent.child_nodes or []) == 1
    assert len(page.child_nodes or []) == 1
