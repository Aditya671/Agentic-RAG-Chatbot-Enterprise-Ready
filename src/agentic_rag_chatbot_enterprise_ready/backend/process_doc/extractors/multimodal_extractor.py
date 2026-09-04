"""PDF image extraction with optional vision-model descriptions."""

from __future__ import annotations

import base64
import logging
from pathlib import Path
from typing import Any

try:
    import fitz
    PYMUPDF_AVAILABLE = True
except ImportError:  # pragma: no cover - optional dependency
    PYMUPDF_AVAILABLE = False

try:
    from langchain_core.messages import HumanMessage
    LANGCHAIN_AVAILABLE = True
except ImportError:  # pragma: no cover - optional dependency
    LANGCHAIN_AVAILABLE = False

logger = logging.getLogger(__name__)


class MultiModalExtractor:
    """Extract PDF images and optionally describe them with a vision LLM."""

    def __init__(self, vision_llm: Any = None) -> None:
        self.vision_llm = vision_llm

    @staticmethod
    def _response_text(response: Any) -> str:
        content = getattr(response, "content", response)
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for block in content:
                if isinstance(block, str):
                    parts.append(block)
                elif isinstance(block, dict) and isinstance(block.get("text"), str):
                    parts.append(block["text"])
            return "\n".join(parts).strip()
        return str(content)

    def _get_image_description(self, image_bytes: bytes, image_ext: str) -> str:
        if not isinstance(image_bytes, bytes) or not image_bytes:
            raise ValueError("image_bytes must contain image data.")
        if not self.vision_llm or not LANGCHAIN_AVAILABLE:
            return "Vision LLM not configured."

        extension = image_ext.lower().lstrip(".")
        mime_type = "image/jpeg" if extension in {"jpg", "jpeg"} else f"image/{extension}"
        encoded = base64.b64encode(image_bytes).decode("ascii")
        message = HumanMessage(
            content=[
                {
                    "type": "text",
                    "text": (
                        "Describe this image factually. Focus on charts, graphs, visible text, "
                        "tables, and other information useful for document retrieval."
                    ),
                },
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime_type};base64,{encoded}"},
                },
            ]
        )
        try:
            return self._response_text(self.vision_llm.invoke([message]))
        except Exception:
            logger.exception("Vision LLM failed for extracted image")
            raise

    def extract_and_describe_images(self, file_path: Path) -> list[dict[str, Any]]:
        if not isinstance(file_path, Path):
            file_path = Path(file_path)
        if not file_path.is_file():
            raise FileNotFoundError(file_path)
        if not PYMUPDF_AVAILABLE:
            logger.warning("PyMuPDF is unavailable; no PDF images can be extracted.")
            return []
        if file_path.suffix.lower() != ".pdf":
            return []

        extracted_data: list[dict[str, Any]] = []
        try:
            with fitz.open(file_path) as document:
                for page_num, page in enumerate(document, start=1):
                    for image_index, image in enumerate(page.get_images(full=True)):
                        base_image = document.extract_image(image[0])
                        image_bytes = base_image.get("image")
                        image_ext = base_image.get("ext", "bin")
                        if not isinstance(image_bytes, bytes):
                            continue
                        description = self._get_image_description(image_bytes, image_ext)
                        extracted_data.append(
                            {
                                "image_id": f"page_{page_num}_img_{image_index}",
                                "page_number": page_num,
                                "description": description,
                                "extension": image_ext,
                            }
                        )
        except Exception:
            logger.exception("Image extraction failed for %s", file_path)
            raise
        return extracted_data
