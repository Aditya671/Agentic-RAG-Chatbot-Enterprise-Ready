"""PII detection and anonymization boundary."""

from __future__ import annotations

import logging
from typing import Sequence

try:
    from presidio_analyzer import AnalyzerEngine, RecognizerResult
    from presidio_anonymizer import AnonymizerEngine
    from presidio_anonymizer.entities import OperatorConfig
    PRESIDIO_AVAILABLE = True
except ImportError:  # pragma: no cover - dependency-isolated environments
    PRESIDIO_AVAILABLE = False

logger = logging.getLogger(__name__)

DEFAULT_ENTITIES: tuple[str, ...] = (
    "CREDIT_CARD",
    "PHONE_NUMBER",
    "EMAIL_ADDRESS",
    "US_SSN",
    "PERSON",
)


class PIIRedactionError(RuntimeError):
    """Raised when configured PII redaction cannot be completed safely."""


class PIIRedactor:
    """Detect and replace configured PII entities using Microsoft Presidio.

    If Presidio is installed but a redaction operation fails, the processor fails
    closed instead of returning the unredacted source text.
    """

    def __init__(self, *, fail_if_unavailable: bool = True) -> None:
        self.fail_if_unavailable = fail_if_unavailable
        self.analyzer = AnalyzerEngine() if PRESIDIO_AVAILABLE else None
        self.anonymizer = AnonymizerEngine() if PRESIDIO_AVAILABLE else None
        if not PRESIDIO_AVAILABLE:
            message = "Presidio is not installed; PII redaction is unavailable."
            if fail_if_unavailable:
                logger.error(message)
            else:
                logger.warning(message)

    def redact(
        self,
        text: str,
        entities: Sequence[str] | None = None,
    ) -> str:
        if not isinstance(text, str):
            raise TypeError("text must be a string.")
        if not text.strip():
            return text

        if self.analyzer is None or self.anonymizer is None:
            if self.fail_if_unavailable:
                raise PIIRedactionError(
                    "PII redaction is unavailable because Presidio is not installed."
                )
            return text

        requested_entities = tuple(entities or DEFAULT_ENTITIES)
        if not requested_entities:
            raise ValueError("At least one PII entity must be configured.")

        try:
            results: list[RecognizerResult] = self.analyzer.analyze(
                text=text,
                entities=list(requested_entities),
                language="en",
            )
            if not results:
                return text

            operators = {
                entity: OperatorConfig(
                    "replace", {"new_value": f"<{entity}>"}
                )
                for entity in requested_entities
            }
            return self.anonymizer.anonymize(
                text=text,
                analyzer_results=results,
                operators=operators,
            ).text
        except Exception as exc:
            logger.exception("PII redaction failed")
            raise PIIRedactionError("PII redaction failed; source text was not released.") from exc
