"""Azure Document Intelligence extraction boundary."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

try:
    from azure.ai.documentintelligence import DocumentIntelligenceClient
    from azure.core.credentials import AzureKeyCredential
    AZURE_AVAILABLE = True
except ImportError:  # pragma: no cover - optional dependency
    AZURE_AVAILABLE = False

logger = logging.getLogger(__name__)


class AzureDocumentExtractor:
    """Extract layout, text, tables, and confidence from supported documents."""

    def __init__(self, endpoint: str | None = None, key: str | None = None, client: Any = None) -> None:
        self.endpoint = endpoint or os.getenv("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT")
        self.key = key or os.getenv("AZURE_DOCUMENT_INTELLIGENCE_API_KEY")
        self.client = client

        if self.client is not None:
            return
        if not AZURE_AVAILABLE:
            logger.warning("azure-ai-documentintelligence is not installed.")
            return
        if self.endpoint and self.key:
            self.client = DocumentIntelligenceClient(
                endpoint=self.endpoint,
                credential=AzureKeyCredential(self.key),
            )

    def extract_layout(self, file_path: Path) -> dict[str, Any]:
        if not isinstance(file_path, Path):
            file_path = Path(file_path)
        if not file_path.is_file():
            raise FileNotFoundError(file_path)
        if self.client is None:
            raise RuntimeError(
                "Azure Document Intelligence is not configured. Set "
                "AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT and AZURE_DOCUMENT_INTELLIGENCE_API_KEY."
            )

        with file_path.open("rb") as handle:
            poller = self.client.begin_analyze_document(
                "prebuilt-layout",
                analyze_request=handle,
                content_type="application/octet-stream",
            )
            result = poller.result()

        tables: list[dict[str, Any]] = []
        for table in result.tables or []:
            tables.append(
                {
                    "row_count": table.row_count,
                    "column_count": table.column_count,
                    "cells": [
                        {
                            "row_index": cell.row_index,
                            "column_index": cell.column_index,
                            "content": cell.content,
                        }
                        for cell in table.cells
                    ],
                }
            )

        paragraphs = [
            {
                "role": getattr(paragraph, "role", None),
                "content": paragraph.content,
            }
            for paragraph in (result.paragraphs or [])
        ]

        confidence_values: list[float] = []
        for page in result.pages or []:
            for word in getattr(page, "words", []) or []:
                confidence = getattr(word, "confidence", None)
                if isinstance(confidence, (int, float)) and 0.0 <= confidence <= 1.0:
                    confidence_values.append(float(confidence))

        confidence = (
            sum(confidence_values) / len(confidence_values)
            if confidence_values
            else 1.0
        )

        return {
            "text": result.content or "",
            "tables": tables,
            "paragraphs": paragraphs,
            "confidence": confidence,
        }

    def close(self) -> None:
        close = getattr(self.client, "close", None)
        if callable(close):
            close()
