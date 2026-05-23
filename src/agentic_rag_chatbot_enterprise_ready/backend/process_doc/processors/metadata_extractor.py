import logging
from typing import Dict, Any, List
from pydantic import BaseModel, Field

try:
    from llama_index.core.program import LLMTextCompletionProgram
    from llama_index.llms.openai import OpenAI
    LLAMA_INDEX_AVAILABLE = True
except ImportError:
    LLAMA_INDEX_AVAILABLE = False

logger = logging.getLogger(__name__)

class DocumentMetadata(BaseModel):
    date: str = Field(description="The primary date mentioned in the document (YYYY-MM-DD), or 'Unknown'.")
    organizations: List[str] = Field(description="List of organizations or companies mentioned.")
    people: List[str] = Field(description="List of people mentioned.")
    document_summary: str = Field(description="A concise 1-2 sentence summary of the document.")

class LLMMetadataExtractor:
    """
    Uses LlamaIndex to accurately extract entities (Dates, Organization Names,
    Document Topics) with structured JSON outputs via Pydantic.
    """
    def __init__(self, llm=None):
        if not LLAMA_INDEX_AVAILABLE:
            logger.warning("LlamaIndex not available. Metadata extraction will use fallback.")
            self.llm = None
        else:
            self.llm = llm or OpenAI(model="gpt-3.5-turbo")
            self.program = LLMTextCompletionProgram.from_defaults(
                output_cls=DocumentMetadata,
                prompt_template_str=(
                    "Please extract the following information from the text:\n"
                    "Text: {text}\n"
                ),
                llm=self.llm,
                verbose=False,
            )

    def extract_metadata(self, text: str) -> Dict[str, Any]:
        """
        Extracts rich metadata via LLM prompts.
        """
        logger.info("Extracting metadata using LlamaIndex...")
        
        if not self.llm:
            return {"date": "Unknown", "organizations": [], "people": [], "document_summary": "Extraction unavailable."}
        
        try:
            # We use the first few thousand chars for metadata extraction to optimize cost
            snippet = text[:4000]
            result = self.program(text=snippet)
            return result.model_dump()
        except Exception as e:
            logger.error(f"Error extracting metadata: {e}")
            return {"error": str(e)}
