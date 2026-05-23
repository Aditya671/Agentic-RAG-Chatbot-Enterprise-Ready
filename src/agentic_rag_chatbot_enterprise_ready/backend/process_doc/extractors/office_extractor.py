import logging
from typing import Dict, Any, List
from pathlib import Path

try:
    from unstructured.partition.auto import partition
    from unstructured.documents.elements import Element, Text, Table
    UNSTRUCTURED_AVAILABLE = True
except ImportError:
    UNSTRUCTURED_AVAILABLE = False

logger = logging.getLogger(__name__)

class OfficeDocumentExtractor:
    """
    Handles unstructured formats like .docx, .pptx, .eml, and .msg files.
    Utilizes the `unstructured` library to partition and extract meaningful chunks.
    """
    def __init__(self, chunking_strategy: str = "by_title"):
        self.chunking_strategy = chunking_strategy

    def process(self, file_path: Path) -> Dict[str, Any]:
        """
        Extracts content from Office and Email formats.
        """
        ext = file_path.suffix.lower()
        logger.info(f"Processing office/email document ({ext}): {file_path.name}")
        
        if not UNSTRUCTURED_AVAILABLE:
            raise ImportError(
                "The `unstructured` library is not installed. "
                "Please install it via `pip install unstructured[all-docs]`."
            )

        try:
            # Partition the document using unstructured's auto-partition
            elements: List[Element] = partition(filename=str(file_path))
            
            # Combine text and extract tables separately if needed
            full_text = []
            tables = []
            metadata_list = []
            
            for element in elements:
                if isinstance(element, Table):
                    tables.append({
                        "text": element.text,
                        "html": getattr(element.metadata, "text_as_html", None)
                    })
                elif isinstance(element, Text):
                    full_text.append(element.text)
                
                # Collect document metadata
                if hasattr(element, "metadata") and element.metadata:
                    metadata_list.append(element.metadata.to_dict())

            content = "\n\n".join(full_text)
            
            # Use the first element's metadata as a representative summary
            doc_metadata = metadata_list[0] if metadata_list else {}
            doc_metadata["format"] = ext
            
            return {
                "text": content,
                "tables": tables,
                "metadata": doc_metadata,
                "elements_count": len(elements)
            }
            
        except Exception as e:
            logger.error(f"Failed to process document {file_path}: {e}")
            raise
