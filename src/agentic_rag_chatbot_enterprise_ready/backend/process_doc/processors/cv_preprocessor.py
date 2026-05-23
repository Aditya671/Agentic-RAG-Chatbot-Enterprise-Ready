import logging
from pathlib import Path
from typing import Optional, Tuple

try:
    import cv2
    import numpy as np
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

logger = logging.getLogger(__name__)

class CVPreprocessor:
    """
    Advanced Computer Vision pre-processing using OpenCV.
    Provides logic to clean up scanned images (deskewing, noise reduction, binarization)
    before OCR to dramatically improve text extraction quality.
    """
    def __init__(self, debug_mode: bool = False):
        self.debug_mode = debug_mode
        if not CV2_AVAILABLE:
            logger.warning("OpenCV (cv2) or Numpy not installed. CV preprocessing will act as a pass-through.")

    def _get_skew_angle(self, cv_image: np.ndarray) -> float:
        """Calculates the skew angle of the document in the image."""
        # Convert to grayscale and apply Gaussian blur
        gray = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (9, 9), 0)
        
        # Threshold the image
        thresh = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
        
        # Apply morphological operations to dilate text blocks
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (30, 5))
        dilate = cv2.dilate(thresh, kernel, iterations=5)
        
        # Find all contours
        contours, _ = cv2.findContours(dilate, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        
        # Find largest contour and surround in min area box
        if not contours:
            return 0.0
            
        contours = sorted(contours, key=cv2.contourArea, reverse=True)
        largest_contour = contours[0]
        min_area_rect = cv2.minAreaRect(largest_contour)
        
        angle = min_area_rect[-1]
        if angle < -45:
            angle = -(90 + angle)
        else:
            angle = -angle
            
        # Return 0 if the angle is very small to avoid unnecessary rotation artifacts
        return angle if abs(angle) > 0.5 else 0.0

    def deskew(self, cv_image: np.ndarray, angle: float) -> np.ndarray:
        """Rotates the image by the given angle to deskew it."""
        (h, w) = cv_image.shape[:2]
        center = (w // 2, h // 2)
        m = cv2.getRotationMatrix2D(center, angle, 1.0)
        deskewed = cv2.warpAffine(
            cv_image, m, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE
        )
        return deskewed

    def denoise_and_binarize(self, cv_image: np.ndarray) -> np.ndarray:
        """Applies adaptive thresholding and median blur to reduce noise."""
        gray = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)
        
        # Median blur to remove salt and pepper noise
        denoised = cv2.medianBlur(gray, 3)
        
        # Adaptive Gaussian Thresholding
        binary = cv2.adaptiveThreshold(
            denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
        )
        return binary

    def process_image(self, file_path: Path) -> Optional[Path]:
        """
        Main entry point for pre-processing an image file.
        Returns the path to the cleaned image or None if CV is unavailable/failed.
        """
        if not CV2_AVAILABLE:
            return file_path
            
        logger.info(f"Applying CV Pre-processing to {file_path.name}")
        
        try:
            image = cv2.imread(str(file_path))
            if image is None:
                logger.error(f"Failed to load image for pre-processing: {file_path}")
                return file_path

            # Deskewing
            angle = self._get_skew_angle(image)
            if abs(angle) > 0:
                logger.debug(f"Deskewing image by {angle:.2f} degrees")
                image = self.deskew(image, angle)

            # Binarization & Denoising
            clean_image = self.denoise_and_binarize(image)

            # Save the pre-processed image to a temporary path
            output_path = file_path.with_name(f"cleaned_{file_path.name}")
            cv2.imwrite(str(output_path), clean_image)
            return output_path
            
        except Exception as e:
            logger.error(f"CV Pre-processing failed: {e}")
            return file_path
