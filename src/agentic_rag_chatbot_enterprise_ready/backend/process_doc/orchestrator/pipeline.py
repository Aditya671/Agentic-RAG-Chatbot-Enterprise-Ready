import logging
import hashlib
import asyncio
from pathlib import Path
from typing import Dict, Any

from ..extractors.azure_extractor import AzureDocumentExtractor
from ..extractors.office_extractor import OfficeDocumentExtractor
from ..extractors.multimodal_extractor import MultiModalExtractor
from ..processors.classifier import DocumentClassifier
from ..processors.pii_redactor import PIIRedactor
from ..processors.metadata_extractor import LLMMetadataExtractor
from ..processors.graph_extractor import GraphEntityExtractor
from .hitl_queue import HITLQueueManager

logger = logging.getLogger(__name__)

class DocumentDigitizationPipeline:
    """
    Orchestrates the end-to-end document digitization flow asynchronously.
    Handles idempotent processing, routing, redaction, extraction, and indexing.
    """
    def __init__(self, db_path: str = "processed_docs.db"):
        # Initialize components
        self.azure_extractor = AzureDocumentExtractor()
        self.office_extractor = OfficeDocumentExtractor()
        self.multimodal_extractor = MultiModalExtractor()
        
        self.classifier = DocumentClassifier()
        self.pii_redactor = PIIRedactor()
        self.metadata_extractor = LLMMetadataExtractor()
        self.graph_extractor = GraphEntityExtractor()
        self.hitl_queue = HITLQueueManager()
        
        # Local state to simulate DB check for idempotency
        self._processed_checksums = set()

    def _calculate_checksum(self, file_path: Path) -> str:
        """Calculates SHA-256 checksum of a file."""
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for block in iter(lambda: f.read(4096), b""):
                sha256.update(block)
        return sha256.hexdigest()

    def _is_already_processed(self, file_path: Path) -> bool:
        """Checks idempotency using file checksums."""
        checksum = self._calculate_checksum(file_path)
        # In a real app, this queries a database table
        if checksum in self._processed_checksums:
            return True
        self._processed_checksums.add(checksum)
        return False

    async def process_document_async(self, file_path: Path) -> Dict[str, Any]:
        """
        Main asynchronous entry point for processing a document.
        Executes CPU-bound processors in separate threads.
        """
        logger.info(f"Starting pipeline for document: {file_path.name}")
        
        if not file_path.exists():
            return {"status": "error", "reason": "file_not_found"}
        
        if self._is_already_processed(file_path):
            logger.info("Document already processed. Skipping.")
            return {"status": "skipped", "reason": "already_processed"}

        ext = file_path.suffix.lower()
        extracted_data = {}

        # 1. Extraction Phase
        try:
            if ext in ['.pdf', '.jpg', '.jpeg', '.png']:
                # Run sync extraction in thread
                extracted_data = await asyncio.to_thread(self.azure_extractor.extract_layout, file_path)
            elif ext in ['.docx', '.pptx', '.eml', '.msg']:
                extracted_data = await asyncio.to_thread(self.office_extractor.process, file_path)
            else:
                logger.warning(f"Unsupported extension {ext}, attempting basic text read.")
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    extracted_data = {"text": f.read()}
        except Exception as e:
            logger.error(f"Extraction failed: {e}")
            self.hitl_queue.enqueue(file_path, f"EXTRACTION_FAILED: {str(e)}")
            return {"status": "queued_for_review", "error": str(e)}
        
        raw_text = extracted_data.get("text", "")
        # Azure often returns high-quality text, if 'confidence' is provided we use it
        confidence = extracted_data.get("confidence", 1.0) 

        # 2. Quality Check & HITL Routing
        if not raw_text.strip() or confidence < 0.7:
            logger.warning(f"Low confidence ({confidence}) or empty text. Routing to HITL queue.")
            self.hitl_queue.enqueue(file_path, "LOW_EXTRACTION_CONFIDENCE")
            return {"status": "queued_for_review"}

        # 3. Processing Phase (Parallelized using asyncio.gather where possible)
        try:
            # Classify
            classification_task = asyncio.to_thread(self.classifier.classify, raw_text)
            
            # Redact PII (needs to run first before metadata/graph to protect data)
            safe_text = await asyncio.to_thread(self.pii_redactor.redact, raw_text)
            
            # Extract Metadata (LLM) using safe_text
            metadata_task = asyncio.to_thread(self.metadata_extractor.extract_metadata, safe_text)
            
            # Graph Entity Extraction using safe_text
            graph_task = asyncio.to_thread(self.graph_extractor.extract_graph_data, safe_text)
            
            # Execute AI extractions concurrently
            classification, metadata, graph_data = await asyncio.gather(
                classification_task, metadata_task, graph_task
            )
            
            # Multi-modal (optional, based on file type)
            images_data = []
            if ext == '.pdf':
                 images_data = await asyncio.to_thread(
                     self.multimodal_extractor.extract_and_describe_images, file_path
                 )

            # 4. Storage & Indexing Phase
            # Here you would call your Indexer (e.g., LlamaIndex, Azure AI Search)
            
            logger.info(f"Successfully finished processing {file_path.name}")
            
            return {
                "status": "success",
                "document_length": len(safe_text),
                "classification": classification,
                "metadata": metadata,
                "graph_data": graph_data,
                "images_extracted": len(images_data)
            }
            
        except Exception as e:
            logger.error(f"Processing failed: {e}")
            self.hitl_queue.enqueue(file_path, f"PROCESSING_FAILED: {str(e)}")
            return {"status": "queued_for_review", "error": str(e)}
