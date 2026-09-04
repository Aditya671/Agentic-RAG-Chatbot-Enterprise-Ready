"""Optional local NLP processing with stable return contracts."""

from __future__ import annotations

import logging
from typing import Any, Sequence

try:
    import torch
    from transformers import pipeline
    TRANSFORMERS_AVAILABLE = True
except ImportError:  # pragma: no cover - optional dependency
    TRANSFORMERS_AVAILABLE = False

logger = logging.getLogger(__name__)


class LocalNLPProcessor:
    """Run optional local zero-shot classification and NER."""

    def __init__(self, use_gpu: bool = True) -> None:
        self.device = 0 if use_gpu and TRANSFORMERS_AVAILABLE and torch.cuda.is_available() else -1
        self.classifier = None
        self.ner_pipeline = None

        if not TRANSFORMERS_AVAILABLE:
            logger.warning("Transformers/PyTorch unavailable; local NLP models are disabled.")
            return

        try:
            self.classifier = pipeline(
                "zero-shot-classification",
                model="valhalla/distilbart-mnli-12-3",
                device=self.device,
            )
            self.ner_pipeline = pipeline(
                "ner",
                model="dbmdz/bert-large-cased-finetuned-conll03-english",
                aggregation_strategy="simple",
                device=self.device,
            )
        except Exception:
            logger.exception("Failed to load local Hugging Face models")
            self.classifier = None
            self.ner_pipeline = None

    def classify_zero_shot(
        self,
        text: str,
        candidate_labels: Sequence[str],
    ) -> dict[str, Any]:
        if not isinstance(text, str) or not text.strip():
            raise ValueError("text must be a non-empty string.")
        labels = [str(label).strip() for label in candidate_labels if str(label).strip()]
        if not labels:
            raise ValueError("candidate_labels must contain at least one non-empty label.")

        if self.classifier is None:
            return {
                "predicted_label": labels[0],
                "score": 0.0,
                "all_scores": {label: 0.0 for label in labels},
            }

        try:
            result = self.classifier(text[:1500], labels)
            return {
                "predicted_label": result["labels"][0],
                "score": round(float(result["scores"][0]), 3),
                "all_scores": {
                    label: float(score)
                    for label, score in zip(result["labels"], result["scores"])
                },
            }
        except Exception:
            logger.exception("Local zero-shot classification failed")
            raise

    def extract_entities_local(self, text: str) -> dict[str, list[str]]:
        if not isinstance(text, str):
            raise TypeError("text must be a string.")
        if not text.strip() or self.ner_pipeline is None:
            return {"ORG": [], "LOC": [], "PER": [], "MISC": []}

        try:
            entities = self.ner_pipeline(text[:2000])
            extracted: dict[str, set[str]] = {
                "ORG": set(),
                "LOC": set(),
                "PER": set(),
                "MISC": set(),
            }
            for entity in entities:
                group = entity.get("entity_group")
                word = str(entity.get("word") or "").strip()
                if group in extracted and word:
                    extracted[group].add(word)
            return {key: sorted(values) for key, values in extracted.items()}
        except Exception:
            logger.exception("Local NER extraction failed")
            raise
