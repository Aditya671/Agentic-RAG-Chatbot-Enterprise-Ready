import logging
import base64
from typing import Dict, Any, List, Optional
from pathlib import Path

try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False

try:
    from langchain_core.messages import HumanMessage
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False

logger = logging.getLogger(__name__)

class MultiModalExtractor:
    """
    Extracts embedded charts, graphs, and images from documents and uses a
    Vision LLM to generate textual descriptions for better semantic search.
    """
    def __init__(self, vision_llm=None):
        """
        Initialize with a Langchain Vision LLM (e.g. ChatOpenAI with gpt-4o or gpt-4-vision-preview).
        """
        self.vision_llm = vision_llm

    def _get_image_description(self, image_bytes: bytes, image_ext: str) -> str:
        if not self.vision_llm:
            return "Vision LLM not configured."
            
        if not LANGCHAIN_AVAILABLE:
            return "Langchain not available for Vision LLM."

        base64_image = base64.b64encode(image_bytes).decode('utf-8')
        mime_type = f"image/{image_ext}" if image_ext != "jpg" else "image/jpeg"
        
        message = HumanMessage(
            content=[
                {"type": "text", "text": "Describe this image in detail. Focus on any charts, graphs, text, or key visual information."},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{mime_type};base64,{base64_image}"
                    },
                },
            ]
        )
        try:
            response = self.vision_llm.invoke([message])
            return response.content
        except Exception as e:
            logger.error(f"Error calling Vision LLM: {e}")
            return f"Error analyzing image: {e}"

    def extract_and_describe_images(self, file_path: Path) -> List[Dict[str, Any]]:
        """
        Finds images in the document and returns their visual descriptions.
        """
        logger.info(f"Extracting images from {file_path.name} for Multi-Modal analysis")
        
        extracted_data = []
        
        if not PYMUPDF_AVAILABLE:
            logger.warning("PyMuPDF (fitz) is not available. Returning empty image descriptions.")
            return extracted_data
            
        if file_path.suffix.lower() == ".pdf":
            try:
                doc = fitz.open(file_path)
                for page_num in range(len(doc)):
                    page = doc.load_page(page_num)
                    image_list = page.get_images(full=True)
                    
                    for img_index, img in enumerate(image_list):
                        xref = img[0]
                        base_image = doc.extract_image(xref)
                        image_bytes = base_image["image"]
                        image_ext = base_image["ext"]
                        
                        description = self._get_image_description(image_bytes, image_ext)
                        
                        extracted_data.append({
                            "image_id": f"page_{page_num+1}_img_{img_index}",
                            "page_number": page_num + 1,
                            "description": description,
                            "extension": image_ext
                        })
            except Exception as e:
                logger.error(f"Error extracting images from PDF {file_path}: {e}")
                
        else:
            # For other file types, one might use different extraction logic
            logger.info(f"Image extraction for non-PDF files ({file_path.suffix}) not fully implemented yet.")
            
        return extracted_data
