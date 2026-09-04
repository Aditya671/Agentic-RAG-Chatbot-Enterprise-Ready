"""OpenCV preprocessing helpers for OCR-oriented image cleanup."""

from __future__ import annotations

import logging
from pathlib import Path

try:
    import cv2
    import numpy as np
    CV2_AVAILABLE = True
except ImportError:  # pragma: no cover - optional dependency
    CV2_AVAILABLE = False

logger = logging.getLogger(__name__)


class CVPreprocessor:
    """Deskew, denoise, and binarize scanned images when OpenCV is available."""

    def __init__(self, debug_mode: bool = False) -> None:
        self.debug_mode = debug_mode
        if not CV2_AVAILABLE:
            logger.warning("OpenCV/NumPy unavailable; CV preprocessing is disabled.")

    @staticmethod
    def _require_image(image: "np.ndarray") -> None:
        if not CV2_AVAILABLE:
            raise RuntimeError("OpenCV is not installed.")
        if not isinstance(image, np.ndarray) or image.size == 0:
            raise ValueError("cv_image must be a non-empty NumPy array.")
        if image.ndim not in {2, 3}:
            raise ValueError("cv_image must be a 2D grayscale or 3D color image.")

    def _get_skew_angle(self, cv_image: "np.ndarray") -> float:
        self._require_image(cv_image)
        gray = cv_image if cv_image.ndim == 2 else cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (9, 9), 0)
        thresh = cv2.threshold(
            blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
        )[1]
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (30, 5))
        dilated = cv2.dilate(thresh, kernel, iterations=5)
        contours, _ = cv2.findContours(
            dilated, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE
        )
        if not contours:
            return 0.0

        largest = max(contours, key=cv2.contourArea)
        angle = cv2.minAreaRect(largest)[-1]
        if angle < -45:
            angle = -(90 + angle)
        else:
            angle = -angle
        return float(angle) if abs(angle) > 0.5 else 0.0

    def deskew(self, cv_image: "np.ndarray", angle: float) -> "np.ndarray":
        self._require_image(cv_image)
        if not isinstance(angle, (int, float)) or not np.isfinite(angle):
            raise ValueError("angle must be a finite number.")
        height, width = cv_image.shape[:2]
        center = (width / 2.0, height / 2.0)
        matrix = cv2.getRotationMatrix2D(center, float(angle), 1.0)
        return cv2.warpAffine(
            cv_image,
            matrix,
            (width, height),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_REPLICATE,
        )

    def denoise_and_binarize(self, cv_image: "np.ndarray") -> "np.ndarray":
        self._require_image(cv_image)
        gray = cv_image if cv_image.ndim == 2 else cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)
        denoised = cv2.medianBlur(gray, 3)
        return cv2.adaptiveThreshold(
            denoised,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            11,
            2,
        )

    def process_image(self, file_path: Path) -> Path:
        """Return a cleaned image path, or the original path when unavailable."""
        if not isinstance(file_path, Path):
            file_path = Path(file_path)
        if not file_path.is_file():
            raise FileNotFoundError(file_path)
        if not CV2_AVAILABLE:
            return file_path

        try:
            image = cv2.imread(str(file_path), cv2.IMREAD_COLOR)
            if image is None:
                raise ValueError(f"Unable to decode image: {file_path}")

            angle = self._get_skew_angle(image)
            if angle:
                image = self.deskew(image, angle)
            cleaned = self.denoise_and_binarize(image)

            output_path = file_path.with_name(
                f"{file_path.stem}.cleaned{file_path.suffix}"
            )
            if not cv2.imwrite(str(output_path), cleaned):
                raise IOError(f"OpenCV could not write {output_path}")
            return output_path
        except Exception:
            logger.exception("CV preprocessing failed for %s", file_path)
            raise
