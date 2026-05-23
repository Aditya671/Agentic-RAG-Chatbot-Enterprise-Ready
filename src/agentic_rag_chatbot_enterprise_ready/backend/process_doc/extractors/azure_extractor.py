import logging
from typing import Any, Dict, Optional
from pathlib import Path

try:
    from azure.core.credentials import AzureKeyCredential
    from azure.ai.documentintelligence import DocumentIntelligenceClient
    from azure.ai.documentintelligence.models import AnalyzeResult
    AZURE_AVAILABLE = True
except ImportError:
    AZURE_AVAILABLE = False

logger = logging.getLogger(__name__)

class AzureDocumentExtractor:
    """
    High-Fidelity Extraction & OCR using Azure Document Intelligence.
    Provides superior OCR, layout analysis (tables, columns), and pre-built models.
    """
    def __init__(self, endpoint: Optional[str] = None, key: Optional[str] = None):
        self.endpoint = endpoint
        self.key = key
        self.client = None
        if AZURE_AVAILABLE and self.endpoint and self.key:
            self.client = DocumentIntelligenceClient(
                endpoint=self.endpoint, 
                credential=AzureKeyCredential(self.key)
            )
        elif not AZURE_AVAILABLE:
            logger.warning("azure-ai-documentintelligence is not installed.")

    def extract_layout(self, file_path: Path) -> Dict[str, Any]:
        """
        Extracts document structure including tables and reading order.
        """
        logger.info(f"Extracting layout for {file_path.name} via Azure Document Intelligence")
        
        if not self.client:
            raise ValueError("Azure Document Intelligence client is not initialized. Please provide endpoint and key, and ensure azure-ai-documentintelligence is installed.")
            
        with open(file_path, "rb") as f:
            poller = self.client.begin_analyze_document(
                "prebuilt-layout", 
                analyze_request=f, 
                content_type="application/octet-stream"
            )
            
        result: AnalyzeResult = poller.result()
        
        tables = []
        if result.tables:
            for table in result.tables:
                cells = []
                for cell in table.cells:
                    cells.append({
                        "row_index": cell.row_index,
                        "column_index": cell.column_index,
                        "content": cell.content
                    })
                tables.append({"row_count": table.row_count, "column_count": table.column_count, "cells": cells})

        paragraphs = []
        if result.paragraphs:
            for para in result.paragraphs:
                paragraphs.append({
                    "role": getattr(para, 'role', None),
                    "content": para.content
                })

        return {
            "text": result.content,
            "tables": tables,
            "paragraphs": paragraphs
        }
