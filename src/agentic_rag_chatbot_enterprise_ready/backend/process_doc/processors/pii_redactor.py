"""PII detection and anonymization boundary."""

from __future__ import annotations

import logging
import re
from typing import Sequence

try:
    from presidio_analyzer import AnalyzerEngine, RecognizerResult
    from presidio_anonymizer import AnonymizerEngine
    from presidio_anonymizer.entities import OperatorConfig
    PRESIDIO_AVAILABLE = True
except ImportError:  # pragma: no cover - optional dependency
    PRESIDIO_AVAILABLE = False

logger = logging.getLogger(__name__)

DEFAULT_ENTITIES: tuple[str, ...] = (
    "CREDIT_CARD",
    "PHONE_NUMBER",
    "EMAIL_ADDRESS",
    "US_SSN",
    "PERSON",
)

_FALLBACK_PATTERNS = {
    "EMAIL_ADDRESS": re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I),
    "PHONE_NUMBER": re.compile(r"(?<!\d)(?:\+?\d[\d .()\-]{7,}\d)(?!\d)"),
    "CREDIT_CARD": re.compile(r"(?<!\d)(?:\d[ -]*?){13,19}(?!\d)"),
    "US_SSN": re.compile(r"(?<!\d)\d{3}-\d{2}-\d{4}(?!\d)"),
}


class PIIRedactionError(RuntimeError):
    """Raised when configured PII redaction cannot be completed safely."""


class PIIRedactor:
    """Detect and replace PII using Presidio or conservative local patterns.

    The local fallback intentionally covers only high-confidence machine-detectable
    identifiers. It does not claim to provide Presidio-equivalent person/entity
    recognition.
    """

    def __init__(self, *, fail_if_unavailable: bool = False) -> None:
        self.fail_if_unavailable = fail_if_unavailable
        self.analyzer = AnalyzerEngine() if PRESIDIO_AVAILABLE else None
        self.anonymizer = AnonymizerEngine() if PRESIDIO_AVAILABLE else None
        if not PRESIDIO_AVAILABLE:
            logger.warning("Presidio is unavailable; using conservative local PII patterns.")

    def redact(self, text: str, entities: Sequence[str] | None = None) -> str:
        if not isinstance(text, str):
            raise TypeError("text must be a string.")
        if not text.strip():
            return text

        requested_entities = tuple(entities or DEFAULT_ENTITIES)
        if not requested_entities:
            raise ValueError("At least one PII entity must be configured.")

        if self.analyzer is None or self.anonymizer is None:
            if self.fail_if_unavailable:
                raise PIIRedactionError(
                    "PII redaction is unavailable because Presidio is not installed."
                )
            return self._fallback_redact(text, requested_entities)

        try:
            results: list[RecognizerResult] = self.analyzer.analyze(
                text=text,
                entities=list(requested_entities),
                language="en",
            )
            if not results:
                return text
            operators = {
                entity: OperatorConfig("replace", {"new_value": f"<{entity}>"})
                for entity in requested_entities
            }
            return self.anonymizer.anonymize(
                text=text,
                analyzer_results=results,
                operators=operators,
            ).text
        except Exception as exc:
            logger.exception("PII redaction failed")
            raise PIIRedactionError(
                "PII redaction failed; source text was not released."
            ) from exc

    @staticmethod
    def _fallback_redact(text: str, entities: Sequence[str]) -> str:
        result = text
        for entity in entities:
            pattern = _FALLBACK_PATTERNS.get(entity)
            if pattern is not None:
                result = pattern.sub(f"<{entity}>", result)
        return result
