import logging
from typing import List

try:
    from presidio_analyzer import AnalyzerEngine, RecognizerResult
    from presidio_anonymizer import AnonymizerEngine
    from presidio_anonymizer.entities import OperatorConfig
    PRESIDIO_AVAILABLE = True
except ImportError:
    PRESIDIO_AVAILABLE = False

logger = logging.getLogger(__name__)

class PIIRedactor:
    """
    Automatically detects and redacts sensitive Personally Identifiable Information
    using Microsoft Presidio.
    """
    def __init__(self):
        if PRESIDIO_AVAILABLE:
            # Set up the engines
            self.analyzer = AnalyzerEngine()
            self.anonymizer = AnonymizerEngine()
        else:
            logger.warning("Presidio is not installed. PII redaction will be a no-op.")
            self.analyzer = None
            self.anonymizer = None

    def redact(self, text: str, entities: List[str] = None) -> str:
        """
        Scans text and masks PII entities.
        """
        logger.info("Scanning and redacting PII from document using Presidio...")
        
        if not self.analyzer or not self.anonymizer:
            return text
            
        if not text.strip():
            return text

        try:
            # Default entities to scan if not provided
            if not entities:
                entities = ["CREDIT_CARD", "PHONE_NUMBER", "EMAIL_ADDRESS", "US_SSN", "PERSON"]
                
            # Analyze text for PII
            results: List[RecognizerResult] = self.analyzer.analyze(
                text=text,
                entities=entities,
                language='en'
            )
            
            if not results:
                return text
                
            # Define how to anonymize (replace with entity type e.g. <PERSON>)
            operators = {
                entity: OperatorConfig("replace", {"new_value": f"<{entity}>"})
                for entity in entities
            }
            
            # Anonymize
            anonymized_result = self.anonymizer.anonymize(
                text=text,
                analyzer_results=results,
                operators=operators
            )
            
            return anonymized_result.text
            
        except Exception as e:
            logger.error(f"Failed during PII redaction: {e}")
            return text # Fail open (return original text)
