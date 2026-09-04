"""Document classification with a deterministic result contract."""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field

try:
    from langchain_core.output_parsers import PydanticOutputParser
    from langchain_core.prompts import PromptTemplate
    from langchain_openai import ChatOpenAI
    LANGCHAIN_AVAILABLE = True
except ImportError:  # pragma: no cover - dependency-isolated environments
    LANGCHAIN_AVAILABLE = False

logger = logging.getLogger(__name__)


class ClassificationResult(BaseModel):
    document_type: str = Field(
        description="Detected document type, such as Invoice, Contract, HR Policy, Technical Manual, or General."
    )
    confidence_score: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence between 0.0 and 1.0.",
    )
    key_subjects: list[str] = Field(
        default_factory=list,
        description="Key subjects or topics covered by the document.",
    )


class DocumentClassifier:
    """Classify documents while exposing one stable confidence field."""

    def __init__(self, llm: Any = None) -> None:
        self.llm = None
        self.parser = None
        self.prompt = None

        if not LANGCHAIN_AVAILABLE:
            logger.warning("LangChain is unavailable; using deterministic fallback classification.")
            return

        self.llm = llm or ChatOpenAI(temperature=0, model="gpt-4o-mini")
        self.parser = PydanticOutputParser(pydantic_object=ClassificationResult)
        self.prompt = PromptTemplate(
            template=(
                "Analyze the following document text and classify its type, confidence, "
                "and key subjects.\n\n{format_instructions}\n\n"
                "Document Text (first 2000 chars):\n{text}"
            ),
            input_variables=["text"],
            partial_variables={"format_instructions": self.parser.get_format_instructions()},
        )

    @staticmethod
    def _fallback(text: str) -> dict[str, Any]:
        normalized = text.casefold()
        document_type = "Invoice" if "invoice" in normalized else "General Document"
        return {
            "document_type": document_type,
            "confidence": 0.5,
            "confidence_score": 0.5,
            "key_subjects": [],
        }

    def classify(self, text: str) -> dict[str, Any]:
        if not isinstance(text, str) or not text.strip():
            raise ValueError("text must be a non-empty string.")

        if self.llm is None:
            return self._fallback(text)

        try:
            result: ClassificationResult = (self.prompt | self.llm | self.parser).invoke(
                {"text": text[:2000]}
            )
            payload = result.model_dump()
            payload["confidence"] = payload["confidence_score"]
            return payload
        except Exception:
            logger.exception("Document classification failed")
            raise
