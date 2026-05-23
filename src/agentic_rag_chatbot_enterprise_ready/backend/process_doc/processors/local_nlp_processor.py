import logging
from typing import Dict, Any, List

try:
    from transformers import pipeline
    import torch
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False

logger = logging.getLogger(__name__)

class LocalNLPProcessor:
    """
    Executes advanced Natural Language Processing tasks locally using PyTorch and
    Hugging Face Transformers. Ideal for secure, zero-shot classification and Named Entity
    Recognition (NER) without relying on external cloud APIs.
    """
    def __init__(self, use_gpu: bool = True):
        self.device = 0 if use_gpu and TRANSFORMERS_AVAILABLE and torch.cuda.is_available() else -1
        
        self.classifier = None
        self.ner_pipeline = None

        if TRANSFORMERS_AVAILABLE:
            logger.info("Initializing Local NLP Models... This may take a moment.")
            try:
                # Fast, lightweight zero-shot classification model
                self.classifier = pipeline(
                    "zero-shot-classification",
                    model="valhalla/distilbart-mnli-12-3",
                    device=self.device
                )
                
                # Standard pre-trained NER for basic entities (Locations, Organizations, People)
                self.ner_pipeline = pipeline(
                    "ner", 
                    model="dbmdz/bert-large-cased-finetuned-conll03-english", 
                    aggregation_strategy="simple",
                    device=self.device
                )
            except Exception as e:
                logger.error(f"Failed to load local HuggingFace models: {e}")
        else:
            logger.warning("Transformers/PyTorch not installed. Local NLP falls back to basic logic.")

    def classify_zero_shot(self, text: str, candidate_labels: List[str]) -> Dict[str, Any]:
        """
        Classifies document text locally against dynamic candidate labels.
        """
        if not self.classifier:
            return {"predicted_label": candidate_labels[0] if candidate_labels else "Unknown", "score": 0.0}
            
        logger.debug("Running local Zero-Shot Classification")
        try:
            # Truncate to first 1500 chars to avoid memory exhaustion on local GPU/CPU
            result = self.classifier(text[:1500], candidate_labels)
            return {
                "predicted_label": result["labels"][0],
                "score": round(result["scores"][0], 3),
                "all_scores": dict(zip(result["labels"], result["scores"]))
            }
        except Exception as e:
            logger.error(f"Local classification failed: {e}")
            return {"error": str(e)}

    def extract_entities_local(self, text: str) -> Dict[str, List[str]]:
        """
        Extracts named entities locally via Transformer-based NER.
        """
        if not self.ner_pipeline:
            return {"ORG": [], "LOC": [], "PER": []}

        logger.debug("Running local Named Entity Recognition")
        try:
            # Chunking might be required for very long texts, evaluating snippet here
            entities = self.ner_pipeline(text[:2000])
            
            extracted = {"ORG": set(), "LOC": set(), "PER": set(), "MISC": set()}
            for entity in entities:
                ent_group = entity.get("entity_group")
                word = entity.get("word")
                if ent_group in extracted and word:
                    extracted[ent_group].add(word)
                    
            # Convert sets back to lists
            return {k: list(v) for k, v in extracted.items()}
            
        except Exception as e:
            logger.error(f"Local NER extraction failed: {e}")
            return {"error": str(e)}
