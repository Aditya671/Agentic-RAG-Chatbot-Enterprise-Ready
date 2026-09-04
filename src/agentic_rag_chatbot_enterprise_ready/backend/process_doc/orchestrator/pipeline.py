"""Asynchronous document digitization pipeline with safe idempotency semantics."""

from __future__ import annotations

import asyncio
import hashlib
import logging
from pathlib import Path
from typing import Any

from ..extractors.azure_extractor import AzureDocumentExtractor
from ..extractors.multimodal_extractor import MultiModalExtractor
from ..extractors.office_extractor import OfficeDocumentExtractor
from ..processors.classifier import DocumentClassifier
from ..processors.graph_extractor import GraphEntityExtractor
from ..processors.metadata_extractor import LLMMetadataExtractor
from ..processors.pii_redactor import PIIRedactor
from .hitl_queue import HITLQueueManager

logger = logging.getLogger(__name__)


class DocumentDigitizationPipeline:
    """Orchestrate extraction, safety processing, enrichment, and review routing.

    A checksum is reserved only after successful processing. Failed extraction or
    enrichment therefore remains retryable instead of being incorrectly reported
    as already processed on the next attempt.
    """

    def __init__(self, db_path: str = "processed_docs.db") -> None:
        self.azure_extractor = AzureDocumentExtractor()
        self.office_extractor = OfficeDocumentExtractor()
        self.multimodal_extractor = MultiModalExtractor()
        self.classifier = DocumentClassifier()
        self.pii_redactor = PIIRedactor()
        self.metadata_extractor = LLMMetadataExtractor()
        self.graph_extractor = GraphEntityExtractor()
        self.hitl_queue = HITLQueueManager(db_path=db_path.replace("processed_docs", "hitl_queue"))
        self._processed_checksums: set[str] = set()
        self._processing_checksums: set[str] = set()

    @staticmethod
    def _calculate_checksum(file_path: Path) -> str:
        sha256 = hashlib.sha256()
        with file_path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                sha256.update(block)
        return sha256.hexdigest()

    def _reserve_checksum(self, checksum: str) -> bool:
        if checksum in self._processed_checksums or checksum in self._processing_checksums:
            return False
        self._processing_checksums.add(checksum)
        return True

    def _complete_checksum(self, checksum: str) -> None:
        self._processing_checksums.discard(checksum)
        self._processed_checksums.add(checksum)

    def _release_checksum(self, checksum: str) -> None:
        self._processing_checksums.discard(checksum)

    async def process_document_async(self, file_path: Path) -> dict[str, Any]:
        if not isinstance(file_path, Path):
            file_path = Path(file_path)
        file_path = file_path.expanduser().resolve()
        logger.info("Starting pipeline for document: %s", file_path.name)

        if not file_path.is_file():
            return {"status": "error", "reason": "file_not_found"}

        checksum = await asyncio.to_thread(self._calculate_checksum, file_path)
        if not self._reserve_checksum(checksum):
            return {"status": "skipped", "reason": "already_processed_or_in_progress"}

        try:
            ext = file_path.suffix.lower()
            if ext in {".pdf", ".jpg", ".jpeg", ".png"}:
                extracted_data = await asyncio.to_thread(
                    self.azure_extractor.extract_layout, file_path
                )
            elif ext in {".docx", ".pptx", ".eml", ".msg"}:
                extracted_data = await asyncio.to_thread(
                    self.office_extractor.process, file_path
                )
            else:
                logger.warning("Unsupported extension %s; attempting text extraction", ext)
                text = await asyncio.to_thread(
                    lambda: file_path.read_text(encoding="utf-8", errors="ignore")
                )
                extracted_data = {"text": text}

            raw_text = str(extracted_data.get("text") or "")
            confidence = extracted_data.get("confidence", 1.0)
            try:
                confidence = float(confidence)
            except (TypeError, ValueError):
                confidence = 0.0

            if not raw_text.strip() or not 0.0 <= confidence <= 1.0 or confidence < 0.7:
                self.hitl_queue.enqueue(file_path, "LOW_EXTRACTION_CONFIDENCE")
                self._release_checksum(checksum)
                return {"status": "queued_for_review", "confidence": confidence}

            safe_text = await asyncio.to_thread(self.pii_redactor.redact, raw_text)
            classification_task = asyncio.to_thread(self.classifier.classify, safe_text)
            metadata_task = asyncio.to_thread(
                self.metadata_extractor.extract_metadata, safe_text
            )
            graph_task = asyncio.to_thread(
                self.graph_extractor.extract_graph_data, safe_text
            )
            classification, metadata, graph_data = await asyncio.gather(
                classification_task, metadata_task, graph_task
            )

            images_data: list[dict[str, Any]] = []
            if ext == ".pdf":
                images_data = await asyncio.to_thread(
                    self.multimodal_extractor.extract_and_describe_images, file_path
                )

            result = {
                "status": "success",
                "document_length": len(safe_text),
                "classification": classification,
                "metadata": metadata,
                "graph_data": graph_data,
                "images_extracted": len(images_data),
            }
            self._complete_checksum(checksum)
            logger.info("Successfully finished processing %s", file_path.name)
            return result
        except Exception as exc:
            self._release_checksum(checksum)
            logger.exception("Document processing failed for %s", file_path)
            self.hitl_queue.enqueue(file_path, f"PROCESSING_FAILED: {exc}")
            return {"status": "queued_for_review", "error": str(exc)}
