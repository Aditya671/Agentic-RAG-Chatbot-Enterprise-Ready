import logging
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

try:
    from langchain_core.prompts import PromptTemplate
    from langchain_core.output_parsers import PydanticOutputParser
    from langchain_openai import ChatOpenAI
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False

logger = logging.getLogger(__name__)

class ClassificationResult(BaseModel):
    document_type: str = Field(description="The detected type of the document (e.g., Invoice, Contract, HR Policy, Technical Manual, General).")
    confidence_score: float = Field(description="A confidence score between 0.0 and 1.0 representing how certain the model is about the classification.")
    key_subjects: list[str] = Field(description="A list of 2-4 key subjects or topics covered in the document.")

class DocumentClassifier:
    """
    Zero-shot classification to route documents to specific processing pipelines
    based on their detected type using LangChain and LLMs.
    """
    def __init__(self, llm=None):
        if not LANGCHAIN_AVAILABLE:
            logger.warning("LangChain not available. Classifier will use fallback logic.")
            self.llm = None
        else:
            self.llm = llm or ChatOpenAI(temperature=0, model="gpt-4o-mini")
            self.parser = PydanticOutputParser(pydantic_object=ClassificationResult)
            self.prompt = PromptTemplate(
                template="Analyze the following document text and classify its type, confidence, and key subjects.\n\n{format_instructions}\n\nDocument Text (first 2000 chars):\n{text}\n",
                input_variables=["text"],
                partial_variables={"format_instructions": self.parser.get_format_instructions()},
            )

    def classify(self, text: str) -> Dict[str, Any]:
        """
        Classifies the document text.
        """
        logger.info("Classifying document content using LLM...")
        
        if not self.llm:
            guessed_type = "Invoice" if "invoice" in text.lower() else "General Document"
            return {"document_type": guessed_type, "confidence": 0.5, "key_subjects": []}

        # Analyze only the beginning of the text to save tokens and time
        snippet = text[:2000]
        
        try:
            chain = self.prompt | self.llm | self.parser
            result: ClassificationResult = chain.invoke({"text": snippet})
            return result.model_dump()
        except Exception as e:
            logger.error(f"Error classifying document: {e}")
            return {"document_type": "Error", "confidence": 0.0, "key_subjects": []}
